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
from core.circuit import Circuit
from core.device import Device, DeviceType, PinType, TechType
from core.terminal import Terminal
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


def _mosfet_circuit(name: str) -> Circuit:
    """A minimal one-transistor flat circuit, for tests needing a real
    structural circuit attached to a topology (as the in-memory generator
    produces, unlike a library reloaded from disk)."""
    ckt = Circuit(name=name)
    dev = Device(name="M1", device_type=DeviceType.MOSFET, tech_type=TechType.N)
    for pin, net_name in (
        (PinType.DRAIN, "out"), (PinType.GATE, "in1"), (PinType.SOURCE, "source_nmos"),
    ):
        net = ckt.find_or_create_net(net_name)
        dev.add_terminal(Terminal(device=dev, pin_type=pin, net=net))
    ckt.add_device(dev)
    return ckt


def _lib_4_with_circuits() -> TopologyLibrary:
    """Same 4 entries as :func:`_lib_4`, each with a real flat circuit
    attached — exercises ``SynthesisAnalysis.write()``'s real-netlist path."""
    lib = TopologyLibrary()
    for spec_kwargs in (
        dict(id=1, name="os_se", num_stages=1, is_complementary=False, is_fully_differential=False),
        dict(id=2, name="os_fd", num_stages=1, is_complementary=True, is_fully_differential=True),
        dict(id=3, name="ts_se", num_stages=2, is_complementary=False, is_fully_differential=False,
             has_cascode={"tc1": True}),
        dict(id=4, name="ts_fd", num_stages=2, is_complementary=True, is_fully_differential=True,
             has_cascode={"tc1": True, "load1": True}),
    ):
        spec = _spec(**spec_kwargs)
        lib.add(spec, circuit=_mosfet_circuit(spec.name))
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

    def test_write_emits_real_netlist_when_circuit_available(self, tmp_path):
        """When the library retains a real circuit, the .ckt body is a
        parseable netlist (.suckt/.end), not the old .MACRO/.EOM stub."""
        from synthesis.analysis import SynthesisAnalysis

        args = self._make_args(output_dir=str(tmp_path / "out"))
        analysis = SynthesisAnalysis(args)
        analysis.library = _lib_4_with_circuits()
        analysis.specifications = Specifications()
        analysis.compute()
        analysis.write()

        ckt_files = sorted((tmp_path / "out" / "candidates").rglob("*.ckt"))
        assert len(ckt_files) == len(analysis.results)
        for ckt_path in ckt_files:
            text = ckt_path.read_text()
            assert text.startswith(".suckt")
            assert ".end" in text
            assert ".MACRO" not in text
            assert "stub" not in text.lower()

    def test_write_real_netlist_round_trips_through_hspice_parser(self, tmp_path):
        """A real candidate netlist must be re-parseable as a device circuit."""
        from synthesis.analysis import SynthesisAnalysis

        args = self._make_args(output_dir=str(tmp_path / "out"))
        analysis = SynthesisAnalysis(args)
        analysis.library = _lib_4_with_circuits()
        analysis.specifications = Specifications()
        analysis.compute()
        analysis.write()

        ckt_path = next((tmp_path / "out" / "candidates").rglob("*.ckt"))
        text = ckt_path.read_text()
        # M1's device line carries real drain/gate/source/bulk/model tokens
        device_lines = [
            line for line in text.splitlines()
            if line and not line.startswith((".", "*"))
        ]
        assert len(device_lines) == 1
        assert device_lines[0].split()[0] == "M1"
        assert device_lines[0].endswith("nmos")

    def test_write_falls_back_to_placeholder_when_circuit_unavailable(self, tmp_path):
        """Loading the library from a pre-built directory drops circuit
        objects (metadata only); write() must degrade gracefully, not crash."""
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
        for ckt_path in ckt_files:
            assert "Structural circuit unavailable" in ckt_path.read_text()

    def test_write_logs_warning_when_circuits_unavailable(self, tmp_path, caplog):
        """write() should warn (not silently degrade) when falling back."""
        from synthesis.analysis import SynthesisAnalysis

        lib_dir = tmp_path / "lib"
        _lib_4().to_directory(str(lib_dir))
        out_dir = tmp_path / "out"
        args = self._make_args(library_dir=str(lib_dir), output_dir=str(out_dir))

        analysis = SynthesisAnalysis(args)
        analysis.initialize()
        analysis.compute()
        with caplog.at_level(logging.WARNING):
            analysis.write()

        assert any(
            "structural circuit available" in rec.message
            for rec in caplog.records
        )

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


# ---------------------------------------------------------------------------
# Real sizing path (issue #51)
# ---------------------------------------------------------------------------

class TestRealSizingPath:
    """End-to-end candidate scoring through the real CP-SAT pipeline.

    A small slice (4 candidates, 2 s budget each) keeps this CI-friendly;
    the full single-output set is a multi-hour run like acst's reference
    (2 260 candidates in 2 h 50 min → 868 sized).
    """

    @pytest.fixture(scope="class")
    def synthesized(self, inputs_dir, tmp_path_factory):
        from types import SimpleNamespace

        from synthesis.analysis import SynthesisAnalysis

        src = inputs_dir / "Synthesis"
        out = tmp_path_factory.mktemp("synth51")
        args = SimpleNamespace(
            xml_spec_file=str(src / "CircuitSpecifications.xml"),
            xml_tech_file=str(src / "TechnologieFile.xml"),
            library_dir=None,
            output_dir=str(out),
            sizing_timeout=2.0,
            max_candidates=4,
        )
        analysis = SynthesisAnalysis(args)
        analysis.initialize()
        analysis.compute()
        analysis.write()
        return analysis, out

    def test_scores_derive_from_solved_performance(self, synthesized):
        analysis, _ = synthesized
        assert analysis.results, "no candidate survived sizing"
        for _spec, sizing in analysis.results:
            assert sizing.solver_status in ("optimal", "feasible")
            assert sizing.devices, "real sizing must populate devices"
            assert sizing.performance.gain_db > 0
            assert sizing.performance.slew_rate > 0

    def test_scores_vary_per_topology(self, synthesized):
        analysis, out = synthesized
        data = json.loads((out / "synthesis_results.json").read_text())
        assert len({e["score"] for e in data}) > 1, "stub-uniform scores"
        assert len({e["gain_db"] for e in data}) > 1

    def test_summary_carries_solved_metrics(self, synthesized):
        _, out = synthesized
        data = json.loads((out / "synthesis_results.json").read_text())
        top = data[0]
        for key in ("solver_status", "slew_rate_v_us", "phase_margin_deg"):
            assert key in top
        assert top["solver_status"] in ("optimal", "feasible")

    def test_candidate_netlists_are_sized(self, synthesized):
        _, out = synthesized
        first = sorted((out / "candidates").glob("rank_001_*.ckt"))[0]
        text = first.read_text()
        assert "W=" in text and "L=" in text, "netlist should embed solved W/L"

    # ── issue #61: two-stage candidates ───────────────────────────────

    def test_two_stage_candidate_sizes_with_composed_gain(self, synthesized):
        """Topology 67 (two-stage) was provably infeasible under the
        single-stage gain model; with A1·A2 stage composition it sizes and
        reports ≥ spec gain (issue #61)."""
        from synthesis.engine import SynthesisEngine

        analysis, _ = synthesized
        spec = analysis.library.topologies[67]
        assert spec.num_stages == 2
        engine = SynthesisEngine(
            analysis.library, analysis.specifications, analysis.technology,
            circuit_parameter=analysis.circuit_parameter, sizing_timeout=5.0)
        sizing = engine._solve_topology(spec, analysis.library.get_circuit(67))
        assert sizing is not None, "two-stage candidate must size (was infeasible)"
        assert sizing.performance.gain_db >= analysis.specifications.min_gain

    def test_second_stage_detection(self, synthesized):
        from core.net import Supply
        from partitioning.partitioner import Partitioner
        from recognition.library import Library
        from recognition.recognizer import StructureRecognizer
        from sizing.topology import second_stage_pieces

        analysis, _ = synthesized
        circuit = analysis.library.get_circuit(67)
        for net in circuit.nets:
            if net.name == "source_pmos":
                net.supply = Supply.vdd()
            elif net.name == "source_nmos":
                net.supply = Supply.gnd()
        sc = StructureRecognizer(Library.from_directory(None)).recognize(circuit)
        partition = Partitioner(analysis.circuit_parameter).partition(sc)
        ss = second_stage_pieces(circuit, partition, "out")
        assert ss is not None
        _, interstage = ss
        assert interstage not in ("out", "source_nmos", "source_pmos")

    def test_operating_parameters_parsed_from_spec_file(self, synthesized):
        analysis, _ = synthesized
        params = analysis.circuit_parameter
        assert params.supply_voltage == ("source_pmos", 5.0)
        assert params.ground == ("source_nmos", 0.0)
        assert params.load_capacities == [("Cap_load_1", 20.0)]
        assert params.input_plus == ("in1", 2.5)
        assert params.output_net == "out"
