"""Tests for SynthesisEngine and SynthesisAnalysis (Phase 3).

Coverage areas
--------------
* ``SynthesisEngine`` import and re-export
* ``SynthesisEngine._filter_candidates()`` — unconstrained, single flag,
  combined flags, no-match
* ``SynthesisEngine.synthesize()`` — returns empty on no candidates, returns
  list of (TopologySpec, SizingResult) pairs, results sorted ascending by score
* ``SynthesisEngine._score()`` — formula components individually verified
* ``SynthesisEngine._size_topology()`` — returns a SizingResult with valid fields
* ``SynthesisAnalysis`` import and re-export
* ``SynthesisAnalysis.initialize()`` — parses spec XML, loads library dir,
  raises on missing spec file
* ``SynthesisAnalysis.compute()`` — populates results, logs warning on empty
* ``SynthesisAnalysis.write()`` — creates JSON summary + candidate CKT files
* ``SynthesisAnalysis`` raises ``RuntimeError`` (not ``NotImplementedError``)
  when calling compute() / write() before initialize()
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path

import pytest

from ckt_io.circuit_info_parser import Specifications
from core.device import TechType
from sizing.result import ExpectedPerformance, SizingResult
from synthesis.engine import SynthesisEngine
from synthesis.library import TopologyLibrary, TopologySpec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"
SPEC_XML = DATA_DIR / "CircuitParameterAndSpecifications.xml"


def _spec(**kw) -> TopologySpec:
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


def _lib_4() -> TopologyLibrary:
    """4-entry library covering all 2×2 category combinations."""
    lib = TopologyLibrary()
    lib.add(_spec(id=1, name="os_se",  num_stages=1, is_complementary=False, is_fully_differential=False))
    lib.add(_spec(id=2, name="os_fd",  num_stages=1, is_complementary=True,  is_fully_differential=True))
    lib.add(_spec(id=3, name="ts_se",  num_stages=2, is_complementary=False, is_fully_differential=False,
                  has_cascode={"tc1": True}))
    lib.add(_spec(id=4, name="ts_fd",  num_stages=2, is_complementary=True,  is_fully_differential=True,
                  has_cascode={"tc1": True, "load1": True}))
    return lib


def _engine(lib=None, complementary=None, fully_differential=None) -> SynthesisEngine:
    if lib is None:
        lib = _lib_4()
    specs = Specifications(complementary=complementary, fully_differential=fully_differential)
    return SynthesisEngine(library=lib, specifications=specs)


# ---------------------------------------------------------------------------
# Imports & re-exports
# ---------------------------------------------------------------------------

class TestImports:
    def test_engine_direct_import(self):
        from synthesis.engine import SynthesisEngine
        assert SynthesisEngine is not None

    def test_engine_re_exported_from_synthesis(self):
        from synthesis import SynthesisEngine
        assert SynthesisEngine is not None

    def test_analysis_direct_import(self):
        from synthesis.analysis import SynthesisAnalysis
        assert SynthesisAnalysis is not None

    def test_analysis_re_exported_from_synthesis(self):
        from synthesis import SynthesisAnalysis
        assert SynthesisAnalysis is not None


# ---------------------------------------------------------------------------
# SynthesisEngine._filter_candidates()
# ---------------------------------------------------------------------------

class TestFilterCandidates:
    def test_no_constraints_returns_all(self):
        engine = _engine()
        assert len(engine._filter_candidates()) == 4

    def test_complementary_false_filters(self):
        engine = _engine(complementary=False)
        results = engine._filter_candidates()
        assert all(not s.is_complementary for s in results)
        assert len(results) == 2

    def test_complementary_true_filters(self):
        engine = _engine(complementary=True)
        results = engine._filter_candidates()
        assert all(s.is_complementary for s in results)
        assert len(results) == 2

    def test_fully_differential_false_filters(self):
        engine = _engine(fully_differential=False)
        results = engine._filter_candidates()
        assert len(results) == 2
        assert all(not s.is_fully_differential for s in results)

    def test_fully_differential_true_filters(self):
        engine = _engine(fully_differential=True)
        results = engine._filter_candidates()
        assert len(results) == 2

    def test_combined_criteria_returns_single(self):
        engine = _engine(complementary=True, fully_differential=True)
        results = engine._filter_candidates()
        assert len(results) == 2   # ids 2 and 4

    def test_combined_criteria_no_match(self):
        engine = _engine(complementary=True, fully_differential=False)
        results = engine._filter_candidates()
        assert results == []

    def test_filter_results_sorted_by_id(self):
        engine = _engine(complementary=False)
        ids = [s.id for s in engine._filter_candidates()]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# SynthesisEngine._size_topology()
# ---------------------------------------------------------------------------

class TestSizeTopology:
    def test_returns_sizing_result(self):
        engine = _engine()
        topo = _spec(num_stages=1)
        result = engine._size_topology(topo)
        assert isinstance(result, SizingResult)

    def test_returns_non_none(self):
        engine = _engine()
        assert engine._size_topology(_spec()) is not None

    def test_gain_scales_with_stages(self):
        engine = _engine()
        r1 = engine._size_topology(_spec(num_stages=1))
        r2 = engine._size_topology(_spec(num_stages=2))
        assert r2.performance.gain_db > r1.performance.gain_db

    def test_area_scales_with_cascode(self):
        engine = _engine()
        r_plain  = engine._size_topology(_spec(has_cascode={}))
        r_casc   = engine._size_topology(_spec(has_cascode={"tc1": True}))
        assert r_casc.performance.total_area_um2 > r_plain.performance.total_area_um2

    def test_power_scales_with_stages(self):
        engine = _engine()
        r1 = engine._size_topology(_spec(num_stages=1))
        r2 = engine._size_topology(_spec(num_stages=2))
        assert r2.performance.power_mw > r1.performance.power_mw

    def test_solver_status_is_stub(self):
        engine = _engine()
        result = engine._size_topology(_spec())
        assert result.solver_status == "stub"


# ---------------------------------------------------------------------------
# SynthesisEngine._compute_scores()
# ---------------------------------------------------------------------------

class TestScore:
    """Tests for the equal-weight min-max normalised scoring.

    C++ ref: AutomaticSizing/src/ConstraintProgram/SearchSpace.cpp line 957
        cost_ = normedGain + normedPower + normedArea
                + normedTransitFrequency + normedSlewRate
    """

    def _make_pair(self, gain_db=80.0, power_mw=1.0,
                   transit_freq_mhz=10.0, area_um2=1000.0):
        result = SizingResult(
            solver_status="stub",
            performance=ExpectedPerformance(
                gain_db=gain_db,
                power_mw=power_mw,
                transit_freq_mhz=transit_freq_mhz,
                total_area_um2=area_um2,
            ),
        )
        return (_spec(), result)

    def test_equal_population_scores_half(self):
        """When all candidates are identical every score term is 0.5 each."""
        engine = _engine()
        pairs = [self._make_pair() for _ in range(3)]
        scores = engine._compute_scores(pairs)
        # 4 normalised terms at 0.5 each + slew stub 0.5 = 2.5
        assert all(math.isclose(s, 2.5) for s in scores)

    def test_higher_gain_lower_score(self):
        """Higher gain → lower normalised gain contribution → lower score."""
        engine = _engine()
        good = self._make_pair(gain_db=80.0)
        bad  = self._make_pair(gain_db=60.0)
        s_good, s_bad = engine._compute_scores([good, bad])
        assert s_good < s_bad

    def test_lower_area_lower_score(self):
        """Smaller area → lower normalised area contribution → lower score."""
        engine = _engine()
        small = self._make_pair(area_um2=500.0)
        large = self._make_pair(area_um2=2000.0)
        s_small, s_large = engine._compute_scores([small, large])
        assert s_small < s_large

    def test_lower_power_lower_score(self):
        """Lower power → lower normalised power contribution → lower score."""
        engine = _engine()
        low  = self._make_pair(power_mw=0.5)
        high = self._make_pair(power_mw=2.0)
        s_low, s_high = engine._compute_scores([low, high])
        assert s_low < s_high

    def test_higher_frequency_lower_score(self):
        """Higher transit frequency → inverted norm → lower score."""
        engine = _engine()
        slow = self._make_pair(transit_freq_mhz=1.0)
        fast = self._make_pair(transit_freq_mhz=100.0)
        s_slow, s_fast = engine._compute_scores([slow, fast])
        assert s_fast < s_slow

    def test_empty_pairs_returns_empty_list(self):
        """Guard clause: an empty population returns [] without divide-by-zero."""
        engine = _engine()
        assert engine._compute_scores([]) == []


# ---------------------------------------------------------------------------
# SynthesisEngine.synthesize()
# ---------------------------------------------------------------------------

class TestSynthesize:
    def test_returns_list(self):
        engine = _engine()
        results = engine.synthesize()
        assert isinstance(results, list)

    def test_each_item_is_tuple_spec_sizing(self):
        engine = _engine()
        for item in engine.synthesize():
            assert isinstance(item[0], TopologySpec)
            assert isinstance(item[1], SizingResult)

    def test_empty_library_returns_empty(self):
        empty_lib = TopologyLibrary()
        engine = SynthesisEngine(empty_lib, Specifications())
        assert engine.synthesize() == []

    def test_no_match_returns_empty(self):
        # Library has no complementary+fd entries
        lib = TopologyLibrary()
        lib.add(_spec(id=1, is_complementary=False, is_fully_differential=False))
        specs = Specifications(complementary=True, fully_differential=True)
        engine = SynthesisEngine(lib, specs)
        assert engine.synthesize() == []

    def test_results_sorted_ascending_score(self):
        engine = _engine()
        results = engine.synthesize()
        scores = engine._compute_scores(results)
        assert scores == sorted(scores)

    def test_synthesize_no_match_logs_warning(self, caplog):
        lib = TopologyLibrary()
        lib.add(_spec(id=1, is_complementary=False))
        specs = Specifications(complementary=True)
        engine = SynthesisEngine(lib, specs)
        with caplog.at_level(logging.WARNING, logger="synthesis.engine"):
            engine.synthesize()
        assert any("no candidates" in msg.lower() for msg in caplog.messages)

    def test_synthesize_count_matches_filter(self):
        engine = _engine(complementary=False)
        results = engine.synthesize()
        # 2 topologies have is_complementary=False
        assert len(results) == 2


# ---------------------------------------------------------------------------
# SynthesisAnalysis
# ---------------------------------------------------------------------------

class TestSynthesisAnalysis:
    """Integration tests for SynthesisAnalysis using real XML fixtures."""

    def _make_args(self, **kw) -> argparse.Namespace:
        defaults = dict(
            xml_spec_file=str(SPEC_XML),
            xml_tech_file=None,
            library_dir=None,
            output_dir=None,
        )
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_analysis_imports(self):
        from synthesis.analysis import SynthesisAnalysis
        assert SynthesisAnalysis is not None

    @pytest.mark.slow
    def test_initialize_no_longer_raises_not_implemented(self):
        # Slow (~20 s): with library_dir=None this fully generates a fresh
        # topology library via TopologyLibraryGenerator. Marker added in
        # Week 9 Phase 5; run with `pytest -m slow` to include.
        from synthesis.analysis import SynthesisAnalysis
        args = self._make_args()
        analysis = SynthesisAnalysis(args)
        # Should not raise NotImplementedError; may raise other errors
        try:
            analysis.initialize()
        except NotImplementedError:
            pytest.fail("initialize() still raises NotImplementedError")
        except Exception:
            pass  # any other exception is acceptable here

    def test_initialize_missing_spec_file_raises_value_error(self):
        from synthesis.analysis import SynthesisAnalysis
        args = self._make_args(xml_spec_file=None)
        analysis = SynthesisAnalysis(args)
        with pytest.raises(ValueError, match="xml-spec-file"):
            analysis.initialize()

    def test_initialize_nonexistent_spec_file_raises(self):
        from synthesis.analysis import SynthesisAnalysis
        args = self._make_args(xml_spec_file="/nonexistent/spec.xml")
        analysis = SynthesisAnalysis(args)
        with pytest.raises(FileNotFoundError):
            analysis.initialize()

    def test_compute_no_longer_raises_not_implemented(self, tmp_path):
        """compute() should not raise NotImplementedError (may raise RuntimeError)."""
        from synthesis.analysis import SynthesisAnalysis
        args = self._make_args()
        analysis = SynthesisAnalysis(args)
        try:
            analysis.compute()
        except NotImplementedError:
            pytest.fail("compute() still raises NotImplementedError")
        except Exception:
            pass

    def test_write_no_longer_raises_not_implemented(self, tmp_path):
        """write() should not raise NotImplementedError (may raise RuntimeError)."""
        from synthesis.analysis import SynthesisAnalysis
        args = self._make_args()
        analysis = SynthesisAnalysis(args)
        try:
            analysis.write()
        except NotImplementedError:
            pytest.fail("write() still raises NotImplementedError")
        except Exception:
            pass

    def test_compute_before_initialize_raises_runtime(self):
        from synthesis.analysis import SynthesisAnalysis
        args = self._make_args()
        analysis = SynthesisAnalysis(args)
        with pytest.raises(RuntimeError):
            analysis.compute()

    def test_write_before_compute_raises_runtime(self, tmp_path):
        from synthesis.analysis import SynthesisAnalysis
        args = self._make_args(output_dir=str(tmp_path))
        analysis = SynthesisAnalysis(args)
        # Inject library + specs but skip compute
        analysis.library = _lib_4()
        analysis.specifications = Specifications()
        with pytest.raises(RuntimeError):
            analysis.write()

    def test_full_pipeline_with_pre_built_library(self, tmp_path):
        """initialize+compute+write end-to-end with a pre-built library dir."""
        from synthesis.analysis import SynthesisAnalysis

        # Build a tiny library on disk
        lib_dir = tmp_path / "lib"
        lib = _lib_4()
        lib.to_directory(str(lib_dir))

        out_dir = tmp_path / "out"
        args = self._make_args(library_dir=str(lib_dir), output_dir=str(out_dir))
        analysis = SynthesisAnalysis(args)
        analysis.initialize()
        analysis.compute()
        analysis.write()

        assert (out_dir / "synthesis_results.json").exists()

    def test_write_creates_json_with_rank_field(self, tmp_path):
        """synthesis_results.json entries must have a 'rank' field."""
        from synthesis.analysis import SynthesisAnalysis

        lib_dir = tmp_path / "lib"
        _lib_4().to_directory(str(lib_dir))
        out_dir = tmp_path / "out"
        args = self._make_args(library_dir=str(lib_dir), output_dir=str(out_dir))

        analysis = SynthesisAnalysis(args)
        analysis.initialize()
        analysis.compute()
        analysis.write()

        data = json.loads((out_dir / "synthesis_results.json").read_text())
        assert len(data) > 0
        assert all("rank" in entry for entry in data)

    def test_write_creates_candidate_ckt_files(self, tmp_path):
        """write() must create one .ckt file per result in candidates/."""
        from synthesis.analysis import SynthesisAnalysis

        lib_dir = tmp_path / "lib"
        _lib_4().to_directory(str(lib_dir))
        out_dir = tmp_path / "out"
        args = self._make_args(library_dir=str(lib_dir), output_dir=str(out_dir))

        analysis = SynthesisAnalysis(args)
        analysis.initialize()
        analysis.compute()
        analysis.write()

        ckt_files = list((out_dir / "candidates").rglob("*.ckt"))
        assert len(ckt_files) == len(analysis.results)

    def test_compute_logs_warning_when_no_candidates(self, tmp_path, caplog):
        """compute() must emit a WARNING when synthesize() finds nothing."""
        from synthesis.analysis import SynthesisAnalysis

        # Library has only non-complementary entries; spec requires complementary
        lib_dir = tmp_path / "lib"
        lib = TopologyLibrary()
        lib.add(_spec(id=1, is_complementary=False))
        lib.to_directory(str(lib_dir))

        out_dir = tmp_path / "out"
        args = self._make_args(library_dir=str(lib_dir), output_dir=str(out_dir))
        analysis = SynthesisAnalysis(args)
        analysis.initialize()
        # Override specs to force complementary=True (no match)
        analysis.specifications = Specifications(complementary=True)

        with caplog.at_level(logging.WARNING, logger="synthesis.analysis"):
            analysis.compute()

        assert any("no" in msg.lower() for msg in caplog.messages)

    def test_results_sorted_best_first_in_json(self, tmp_path):
        """synthesis_results.json must be ordered rank 1, 2, … with non-decreasing scores."""
        from synthesis.analysis import SynthesisAnalysis

        lib_dir = tmp_path / "lib"
        _lib_4().to_directory(str(lib_dir))
        out_dir = tmp_path / "out"
        args = self._make_args(library_dir=str(lib_dir), output_dir=str(out_dir))
        analysis = SynthesisAnalysis(args)
        analysis.initialize()
        analysis.compute()
        analysis.write()

        data = json.loads((out_dir / "synthesis_results.json").read_text())
        scores = [e["score"] for e in data]
        assert scores == sorted(scores)
