"""Tests for `partitioning.analysis` (Week 9 Phase 4 wiring).

Previously asserted the stubs raised `NotImplementedError`; now exercises
the wired pipeline end-to-end against the bundled `AutomaticSizing`
fixture (which ships the `CircuitParameterAndSpecifications.xml` the
partitioner needs).
"""
from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from partitioning.analysis import PartitioningAnalysis
from partitioning.result import PartitionResult


def _make_args(inputs_dir: Path, **overrides) -> argparse.Namespace:
    src = inputs_dir / "AutomaticSizing"
    defaults = dict(
        circuit_netlist=str(src / "cascodedSymmetricalCMOSOTA.hspice"),
        device_types_file=str(src / "deviceTypes.xcat"),
        hspice_mapping_file=str(src / "HSpiceMapping.xcat"),
        hspice_supplynet_file=str(src / "supplyNets.xcat"),
        xml_circuit_information_file=str(src / "CircuitParameterAndSpecifications.xml"),
        xml_structrec_library_file=None,
        output_file=None,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestPartitioningAnalysisLifecycle:
    def test_initialize_no_longer_raises_not_implemented(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "p.xml"))
        try:
            PartitioningAnalysis(args).initialize()
        except NotImplementedError:
            pytest.fail("PartitioningAnalysis.initialize() still raises NotImplementedError")

    def test_initialize_populates_inputs(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "p.xml"))
        a = PartitioningAnalysis(args)
        a.initialize()
        assert a.circuit is not None
        assert a.structure_circuits is not None
        assert a.circuit_params is not None

    def test_initialize_missing_circuit_params_raises(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir,
                          xml_circuit_information_file=None,
                          output_file=str(tmp_path / "p.xml"))
        with pytest.raises(ValueError, match="xml-circuit-information-file"):
            PartitioningAnalysis(args).initialize()

    def test_compute_before_initialize_raises_runtime(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "p.xml"))
        with pytest.raises(RuntimeError, match="not initialised"):
            PartitioningAnalysis(args).compute()

    def test_compute_produces_partition_result(self, inputs_dir, tmp_path):
        args = _make_args(inputs_dir, output_file=str(tmp_path / "p.xml"))
        a = PartitioningAnalysis(args)
        a.initialize(); a.compute()
        assert isinstance(a.partition, PartitionResult)
        assert a.partition.total > 0

    def test_write_produces_valid_xml(self, inputs_dir, tmp_path):
        out = tmp_path / "partition.xml"
        args = _make_args(inputs_dir, output_file=str(out))
        a = PartitioningAnalysis(args)
        a.initialize(); a.compute(); a.write()
        assert out.exists()
        root = ET.parse(out).getroot()
        # PartitionXMLWriter root tag should be Partitioning-something
        assert root.tag  # at minimum, the tree parses


# ---------------------------------------------------------------------------
# PartitioningAnalysis._resolve_lib_dir helper
# ---------------------------------------------------------------------------

class TestResolveLibDir:
    """Static helper that accepts either a directory or an
    `AnalogLibrary.xml` file path; `None` falls through to the
    bundled-XML default."""

    def test_returns_dir_when_given_directory(self, tmp_path):
        assert PartitioningAnalysis._resolve_lib_dir(str(tmp_path)) == tmp_path

    def test_returns_parent_when_given_file(self, tmp_path):
        f = tmp_path / "AnalogLibrary.xml"
        f.write_text("<root/>")
        assert PartitioningAnalysis._resolve_lib_dir(str(f)) == tmp_path

    def test_returns_none_when_given_none(self):
        assert PartitioningAnalysis._resolve_lib_dir(None) is None
