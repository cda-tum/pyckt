"""Tests for `recognition.analysis` (Week 9 Phase 4 wiring).

These tests previously asserted the stubs raised `NotImplementedError`;
they now exercise the wired pipelines end-to-end against the bundled
fixtures from `tests/data/inputs/`.
"""
from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from recognition.analysis import RuleGenAnalysis, StructRecAnalysis


def _make_args(inputs_dir: Path, **overrides) -> argparse.Namespace:
    """Build a namespace pointing at the bundled Partitioning fixture set."""
    src = inputs_dir / "Partitioning"
    defaults = dict(
        circuit_netlist=str(src / "cascodedSymmetricalCMOSOTA.hspice"),
        device_types_file=str(src / "deviceTypes.xcat"),
        hspice_mapping_file=str(src / "HSpiceMapping.xcat"),
        hspice_supplynet_file=str(src / "supplyNets.xcat"),
        xml_structrec_library_file=None,
        output_file=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# StructRecAnalysis
# ---------------------------------------------------------------------------

class TestStructRecCompositeParity:
    """§8c regression: bottom-up recognition must reproduce acst's composite
    grouping on the cascoded symmetrical OTA — top-level structures are two
    cascode current mirrors, two differential pairs, and two simple
    (bias) current mirrors, with no spurious level shifter."""

    def test_top_level_structures_match_acst(self, inputs_dir, tmp_path):
        from collections import Counter

        src = inputs_dir / "StructureRecognition"
        args = _make_args(
            inputs_dir,
            circuit_netlist=str(src / "input.ckt"),
            device_types_file=str(src / "deviceTypes.xcat"),
            hspice_mapping_file=str(src / "HSpiceMapping.xcat"),
            hspice_supplynet_file=str(src / "supplyNets.xcat"),
            output_file=str(tmp_path / "sr.xml"),
        )
        analysis = StructRecAnalysis(args)
        analysis.initialize()

        tops = Counter(
            s.name for s in analysis.structure_circuits.structures_without_parents
        )
        assert tops == {
            "MosfetCascodeCurrentMirror": 2,
            "MosfetDifferentialPair": 2,
            "MosfetSimpleCurrentMirror": 2,
        }
        # the spurious level shifter the old greedy matcher produced is gone
        assert "MosfetLevelShifter" not in tops


class TestStructRecAnalysisLifecycle:
    def test_initialize_no_longer_raises_not_implemented(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "sr.xml"))
        analysis = StructRecAnalysis(args)
        try:
            analysis.initialize()
        except NotImplementedError:
            pytest.fail("StructRecAnalysis.initialize() still raises NotImplementedError")

    def test_initialize_populates_structure_circuits(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "sr.xml"))
        analysis = StructRecAnalysis(args)
        analysis.initialize()
        assert analysis.structure_circuits is not None
        assert analysis.structure_circuits.total_structures > 0

    def test_initialize_missing_circuit_raises_value_error(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, circuit_netlist=None,
                          output_file=str(tmp_path / "sr.xml"))
        with pytest.raises(ValueError, match="circuit-netlist"):
            StructRecAnalysis(args).initialize()

    def test_compute_before_initialize_raises_runtime(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "sr.xml"))
        with pytest.raises(RuntimeError, match="not initialised"):
            StructRecAnalysis(args).compute()

    def test_write_produces_valid_xml(self, inputs_dir, tmp_path):
        out = tmp_path / "sr.xml"
        args = _make_args(inputs_dir, output_file=str(out))
        a = StructRecAnalysis(args)
        a.initialize(); a.compute(); a.write()
        assert out.exists()
        root = ET.parse(out).getroot()
        assert root.tag == "StructureRecognitionResult"


# ---------------------------------------------------------------------------
# RuleGenAnalysis
# ---------------------------------------------------------------------------

class TestRuleGenAnalysisLifecycle:
    def test_initialize_no_longer_raises_not_implemented(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "r.xml"))
        try:
            RuleGenAnalysis(args).initialize()
        except NotImplementedError:
            pytest.fail("RuleGenAnalysis.initialize() still raises NotImplementedError")

    def test_compute_populates_rules(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "r.xml"))
        a = RuleGenAnalysis(args)
        a.initialize(); a.compute()
        assert isinstance(a.rules, list)
        assert len(a.rules) > 0

    def test_compute_before_initialize_raises_runtime(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "r.xml"))
        with pytest.raises(RuntimeError, match="not initialised"):
            RuleGenAnalysis(args).compute()

    def test_write_produces_valid_xml(self, inputs_dir, tmp_path):
        out = tmp_path / "rules.xml"
        args = _make_args(inputs_dir, output_file=str(out))
        a = RuleGenAnalysis(args)
        a.initialize(); a.compute(); a.write()
        assert out.exists()
        root = ET.parse(out).getroot()
        assert root.tag == "SizingRules"
        assert len(root.findall("Rule")) == len(a.rules)


# ---------------------------------------------------------------------------
# _resolve_lib_dir helper — directory / file / None branches
# ---------------------------------------------------------------------------

class TestResolveLibDir:
    """`recognition.analysis._resolve_lib_dir` accepts either a directory
    or an `AnalogLibrary.xml` file path; `None` falls through to the
    bundled-XML default."""

    def test_returns_dir_when_given_directory(self, tmp_path):
        from recognition.analysis import _resolve_lib_dir
        assert _resolve_lib_dir(str(tmp_path)) == tmp_path

    def test_returns_parent_when_given_file(self, tmp_path):
        from recognition.analysis import _resolve_lib_dir
        f = tmp_path / "AnalogLibrary.xml"
        f.write_text("<root/>")
        assert _resolve_lib_dir(str(f)) == tmp_path

    def test_returns_none_when_given_none(self):
        from recognition.analysis import _resolve_lib_dir
        assert _resolve_lib_dir(None) is None


# ---------------------------------------------------------------------------
# write()-before-initialize RuntimeError paths
# ---------------------------------------------------------------------------

class TestRecognitionWriteRuntimeError:
    """`write()` must refuse to run before its preceding lifecycle step
    has populated the required state — even when called in isolation
    (without going through `initialize()` first)."""

    def _bare_args(self):
        return argparse.Namespace(
            circuit_netlist=None, device_types_file=None,
            hspice_mapping_file=None, hspice_supplynet_file=None,
            xml_structrec_library_file=None,
            output_file="/tmp/should_not_be_written.xml",
        )

    def test_structrec_write_before_initialize_raises(self):
        a = StructRecAnalysis(self._bare_args())
        with pytest.raises(RuntimeError, match="not initialised"):
            a.write()

    def test_rulegen_write_before_anything_raises(self):
        a = RuleGenAnalysis(self._bare_args())
        # Both .rules empty AND .structure_circuits is None → the
        # "nothing to write" branch.
        with pytest.raises(RuntimeError, match="nothing to write"):
            a.write()
