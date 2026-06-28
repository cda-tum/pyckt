"""Tests for the public Python API (``pyckt.api`` / re-exported from ``pyckt``).

These call the API functions directly — *not* through ``cli.run`` — so
they lock in the typed signatures and the optional-output behaviour that make
the functions usable from notebooks and pipelines.

The structure-recognition / rulegen / partitioning paths are fast; the sizing
and full topology-library paths are marked ``slow``.
"""
from __future__ import annotations

import pytest

import pyckt
from core.device import TechType
from synthesis.library import TopologyLibrary, TopologySpec
from tests.conftest import INPUTS_DIR

_SR = INPUTS_DIR / "StructureRecognition"
_PART = INPUTS_DIR / "Partitioning"
_SIZE = INPUTS_DIR / "AutomaticSizing"
_PARAMS = INPUTS_DIR.parent / "CircuitParameterAndSpecifications.xml"


def _topology_spec(**kw) -> TopologySpec:
    defaults = dict(
        id=1,
        name="topo",
        num_stages=1,
        is_complementary=False,
        is_fully_differential=False,
        input_tech=TechType.N,
        has_cascode={},
    )
    defaults.update(kw)
    return TopologySpec(**defaults)


def _small_library() -> TopologyLibrary:
    """4-entry library covering all 2x2 category combinations — mirrors
    ``tests/test_synthesis.py::_lib_4`` so the API test exercises the same
    fast, pre-built-library path instead of the ~20s in-memory generation."""
    lib = TopologyLibrary()
    lib.add(_topology_spec(id=1, name="os_se", num_stages=1,
                            is_complementary=False, is_fully_differential=False))
    lib.add(_topology_spec(id=2, name="os_fd", num_stages=1,
                            is_complementary=True, is_fully_differential=True))
    lib.add(_topology_spec(id=3, name="ts_se", num_stages=2,
                            is_complementary=False, is_fully_differential=False,
                            has_cascode={"tc1": True}))
    lib.add(_topology_spec(id=4, name="ts_fd", num_stages=2,
                            is_complementary=True, is_fully_differential=True,
                            has_cascode={"tc1": True, "load1": True}))
    return lib


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

class TestPublicSurface:
    def test_top_level_reexports(self):
        for name in (
            "recognize", "generate_rules", "partition", "size",
            "synthesize", "generate_topology_library",
        ):
            assert hasattr(pyckt, name), f"pyckt.{name} not exported"
            assert callable(getattr(pyckt, name))

    def test_api_module_all(self):
        from pyckt import api
        assert set(api.__all__) == set(pyckt.__all__)


# ---------------------------------------------------------------------------
# recognize
# ---------------------------------------------------------------------------

class TestRecognize:
    def test_returns_structure_overlay(self):
        result = pyckt.recognize(
            circuit=_SR / "input.ckt",
            device_types=_SR / "deviceTypes.xcat",
            mapping=_SR / "HSpiceMapping.xcat",
            supply_nets=_SR / "supplyNets.xcat",
        )
        from recognition.model import StructureCircuits
        assert isinstance(result, StructureCircuits)
        assert result.total_structures > 0

    def test_accepts_path_and_str(self):
        # str paths must work identically to Path objects
        result = pyckt.recognize(
            circuit=str(_SR / "input.ckt"),
            device_types=str(_SR / "deviceTypes.xcat"),
            mapping=str(_SR / "HSpiceMapping.xcat"),
            supply_nets=str(_SR / "supplyNets.xcat"),
        )
        assert result.total_structures > 0

    def test_no_output_writes_nothing(self, tmp_path):
        # output defaults to None → nothing written anywhere
        pyckt.recognize(
            circuit=_SR / "input.ckt",
            device_types=_SR / "deviceTypes.xcat",
            mapping=_SR / "HSpiceMapping.xcat",
            supply_nets=_SR / "supplyNets.xcat",
        )
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("fmt", ["native", "acst"])
    def test_output_is_written_when_requested(self, tmp_path, fmt):
        out = tmp_path / "rec.xml"
        result = pyckt.recognize(
            circuit=_SR / "input.ckt",
            device_types=_SR / "deviceTypes.xcat",
            mapping=_SR / "HSpiceMapping.xcat",
            supply_nets=_SR / "supplyNets.xcat",
            output=out,
            output_format=fmt,
        )
        assert out.exists() and out.stat().st_size > 0
        # the in-memory object is returned regardless of the written format
        assert result.total_structures > 0


# ---------------------------------------------------------------------------
# generate_rules
# ---------------------------------------------------------------------------

class TestGenerateRules:
    def test_returns_rule_list(self):
        rules = pyckt.generate_rules(
            circuit=_SR / "input.ckt",
            device_types=_SR / "deviceTypes.xcat",
            mapping=_SR / "HSpiceMapping.xcat",
            supply_nets=_SR / "supplyNets.xcat",
        )
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_acst_format_writes_pairlibrary(self, tmp_path):
        out = tmp_path / "lib.xml"
        rules = pyckt.generate_rules(
            circuit=_SR / "input.ckt",
            device_types=_SR / "deviceTypes.xcat",
            mapping=_SR / "HSpiceMapping.xcat",
            supply_nets=_SR / "supplyNets.xcat",
            structure_name="MyOpAmp",
            output=out,
            output_format="acst",
        )
        assert out.exists()
        # returned value is still the native rule list, not the pairLibrary
        assert isinstance(rules, list)


# ---------------------------------------------------------------------------
# partition
# ---------------------------------------------------------------------------

class TestPartition:
    def test_returns_partition_result(self):
        result = pyckt.partition(
            circuit=_PART / "cascodedSymmetricalCMOSOTA.hspice",
            device_types=_PART / "deviceTypes.xcat",
            mapping=_PART / "HSpiceMapping.xcat",
            supply_nets=_PART / "supplyNets.xcat",
            circuit_params=_PARAMS,
        )
        from partitioning.result import PartitionResult
        assert isinstance(result, PartitionResult)


# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------

class TestSynthesize:
    def _synthesize(self, tmp_path, **kw):
        lib_dir = tmp_path / "lib"
        _small_library().to_directory(str(lib_dir))
        return pyckt.synthesize(
            spec=_PARAMS,
            tech_file=_SIZE / "TechnologyFile.xml",
            library_dir=lib_dir,
            **kw,
        )

    def test_returns_ranked_synthesis_candidates(self, tmp_path):
        candidates = self._synthesize(tmp_path)
        assert isinstance(candidates, list)
        assert len(candidates) > 0

        from pyckt.api import SynthesisCandidate
        from sizing.result import SizingResult
        from synthesis.library import TopologySpec

        for candidate in candidates:
            assert isinstance(candidate, SynthesisCandidate)
            assert isinstance(candidate.topology, TopologySpec)
            assert isinstance(candidate.sizing, SizingResult)
            assert isinstance(candidate.score, float)

    def test_ranked_best_first_with_sequential_rank(self, tmp_path):
        candidates = self._synthesize(tmp_path)
        # rank is 1-based and matches each candidate's position
        assert [c.rank for c in candidates] == list(range(1, len(candidates) + 1))
        # scores are non-decreasing (lower is better, best first)
        scores = [c.score for c in candidates]
        assert scores == sorted(scores)

    def test_synthesis_candidate_is_importable_from_top_level(self):
        # the dataclass is part of the public surface, not just an internal detail
        assert pyckt.SynthesisCandidate is not None

    def test_no_output_dir_writes_nothing(self, tmp_path):
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        self._synthesize(work_dir)
        # only the library dir created inside _synthesize should exist
        assert sorted(p.name for p in work_dir.iterdir()) == ["lib"]

    def test_output_dir_writes_json_summary(self, tmp_path):
        out = tmp_path / "out"
        self._synthesize(tmp_path, output_dir=out)
        assert (out / "synthesis_results.json").exists()


# ---------------------------------------------------------------------------
# size (slow — runs the CP-SAT solver)
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestSize:
    def test_returns_sizing_result_and_writes_netlist(self, tmp_path):
        out = tmp_path / "sized.xml"
        result = pyckt.size(
            circuit=_SIZE / "cascodedSymmetricalCMOSOTA.hspice",
            device_types=_SIZE / "deviceTypes.xcat",
            mapping=_SIZE / "HSpiceMapping.xcat",
            supply_nets=_SIZE / "supplyNets.xcat",
            tech_file=_SIZE / "TechnologyFile.xml",
            circuit_params=_SIZE / "CircuitParameterAndSpecifications.xml",
            timeout=5,
            output=out,
        )
        from sizing.result import SizingResult
        assert isinstance(result, SizingResult)
        assert out.exists()
        # sizing also writes the sized HSpice netlist beside the XML
        assert out.with_suffix(".sized.hspice").exists()


# ---------------------------------------------------------------------------
# generate_topology_library (slow — full HL2–HL5 sweep)
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestGenerateTopologyLibrary:
    def test_in_memory_only(self, tmp_path):
        lib = pyckt.generate_topology_library()
        from synthesis.library import TopologyLibrary
        assert isinstance(lib, TopologyLibrary)
        assert lib.size() > 100
        # output_dir defaulted to None → nothing written
        assert list(tmp_path.iterdir()) == []

    def test_writes_acst_layout_when_output_dir_given(self, tmp_path):
        lib = pyckt.generate_topology_library(
            output_dir=tmp_path, output_format="acst"
        )
        assert lib.size() > 100
        for cat in ("SingleOutputOpAmps", "FullyDifferentialOpAmps",
                    "ComplementaryOpAmps"):
            assert (tmp_path / cat).is_dir()
