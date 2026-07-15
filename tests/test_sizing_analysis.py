"""Tests for sizing.analysis (AutomaticSizingAnalysis)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sizing.analysis import AutomaticSizingAnalysis
from sizing.result import SizingResult


class _Dummy:
    pass


def _args(**overrides):
    base = dict(
        hspice_mapping_file="map.xcat",
        hspice_supplynet_file="supply.xcat",
        device_types_file="deviceTypes.xcat",
        circuit_netlist="ckt.hspice",
        xml_circuit_information_file="cinfo.xml",
        xml_technologie_file="tech.xml",
        xml_structrec_library_file="lib.xml",
        output_file="out.xml",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_require_arg_missing_raises():
    analysis = AutomaticSizingAnalysis(_args(output_file=""))
    with pytest.raises(ValueError, match="Missing required argument --output-file"):
        analysis._require_arg("output_file")


def test_require_initialized_raises():
    with pytest.raises(RuntimeError, match="expected initialized circuit"):
        AutomaticSizingAnalysis._require_initialized(None, "circuit")


def test_resolve_structrec_library_dir(tmp_path: Path):
    d = tmp_path / "libdir"
    d.mkdir()
    f = d / "Library.xml"
    f.write_text("<x/>")

    assert AutomaticSizingAnalysis._resolve_structrec_library_dir(str(d)) == d
    # issue #47: wrapper files pass through unchanged
    assert AutomaticSizingAnalysis._resolve_structrec_library_dir(str(f)) == f


def test_initialize_populates_pipeline(monkeypatch, tmp_path: Path):
    args = _args(xml_structrec_library_file=str(tmp_path / "Library.xml"))
    analysis = AutomaticSizingAnalysis(args)

    # Sentinels that should flow through initialize() in order.
    mapping = _Dummy()
    supply = _Dummy()
    dtypes = _Dummy()
    circuit = _Dummy()
    cinfo = _Dummy()
    library = _Dummy()
    struct_circuits = _Dummy()
    partition = _Dummy()
    rules = ["r1", "r2"]

    class FakeHSpiceMapping:
        @staticmethod
        def from_file(path):
            assert path == args.hspice_mapping_file
            return mapping

    class FakeSupplyNetConfig:
        @staticmethod
        def from_file(path):
            assert path == args.hspice_supplynet_file
            return supply

    def fake_load_device_types(path):
        assert path == args.device_types_file
        return dtypes

    class FakeHSpiceParser:
        def __init__(self, m, s, dt):
            assert (m, s, dt) == (mapping, supply, dtypes)

        def parse(self, path):
            assert path == args.circuit_netlist
            return circuit

    def fake_load_circuit_information(info_path, tech_path):
        assert info_path == args.xml_circuit_information_file
        assert tech_path == args.xml_technologie_file
        return cinfo

    class FakeLibrary:
        @staticmethod
        def from_directory(path):
            assert Path(path) == tmp_path / "Library.xml"
            return library

    class FakeStructureRecognizer:
        def __init__(self, lib):
            assert lib is library

        def recognize(self, c):
            assert c is circuit
            return struct_circuits

    class FakePartitioner:
        def __init__(self, params):
            assert params is cinfo.parameters

        def partition(self, sc):
            assert sc is struct_circuits
            return partition

    class FakeRuleGenerator:
        def generate(self, sc):
            assert sc is struct_circuits
            return rules

    monkeypatch.setattr("ckt_io.HSpiceMapping", FakeHSpiceMapping)
    monkeypatch.setattr("ckt_io.SupplyNetConfig", FakeSupplyNetConfig)
    monkeypatch.setattr("ckt_io.load_device_types", fake_load_device_types)
    monkeypatch.setattr("ckt_io.HSpiceParser", FakeHSpiceParser)
    monkeypatch.setattr("ckt_io.load_circuit_information", fake_load_circuit_information)
    monkeypatch.setattr("recognition.library.Library", FakeLibrary)
    monkeypatch.setattr("recognition.recognizer.StructureRecognizer", FakeStructureRecognizer)
    monkeypatch.setattr("recognition.recognizer.RuleGenerator", FakeRuleGenerator)
    monkeypatch.setattr("partitioning.partitioner.Partitioner", FakePartitioner)

    cinfo.parameters = _Dummy()

    analysis.initialize()

    assert analysis.circuit is circuit
    assert analysis.circuit_info is cinfo
    assert analysis.library is library
    assert analysis.structure_circuits is struct_circuits
    assert analysis.partition is partition
    assert analysis.rules == rules


def test_compute_success(monkeypatch):
    import sizing.analysis as analysis_mod

    args = _args()
    analysis = AutomaticSizingAnalysis(args)
    analysis.circuit = _Dummy()
    analysis.partition = _Dummy()
    analysis.circuit_info = _Dummy()
    analysis.rules = ["rule"]

    fake_problem = _Dummy()
    fake_result = SizingResult()

    def fake_build(circuit, partition, rules, circuit_info):
        assert circuit is analysis.circuit
        assert partition is analysis.partition
        assert rules == analysis.rules
        assert circuit_info is analysis.circuit_info
        return fake_problem

    class FakeSolver:
        def __init__(self, problem):
            assert problem is fake_problem
            self.problem = problem

        def solve(self):
            return fake_result

    monkeypatch.setattr(analysis_mod.SizingProblem, "build", staticmethod(fake_build))
    monkeypatch.setattr(analysis_mod, "SizingSolver", FakeSolver)

    analysis.compute()

    assert analysis.problem is fake_problem
    assert isinstance(analysis.solver, FakeSolver)
    assert analysis.result is fake_result


def test_compute_handles_infeasible(monkeypatch):
    """compute() must NOT raise when the solver reports infeasible/no-solution.

    Phase 3: the NotImplementedError wrapper is removed.  When solve() returns
    a result with an empty ``devices`` dict (infeasible / timeout), analysis
    should complete and leave ``result.devices`` empty rather than raising.
    """
    import sizing.analysis as analysis_mod

    analysis = AutomaticSizingAnalysis(_args())
    analysis.circuit = _Dummy()
    analysis.partition = _Dummy()
    analysis.circuit_info = _Dummy()
    analysis.rules = []

    monkeypatch.setattr(analysis_mod.SizingProblem, "build", staticmethod(lambda *a, **k: _Dummy()))

    infeasible_result = SizingResult(solver_status="infeasible")

    class FakeSolver:
        def __init__(self, problem):
            self.problem = problem

        def solve(self):
            return infeasible_result

    monkeypatch.setattr(analysis_mod, "SizingSolver", FakeSolver)

    # Should NOT raise — graceful infeasible path.
    analysis.compute()

    assert analysis.result is infeasible_result
    assert analysis.result.devices == {}
    assert analysis.result.solver_status == "infeasible"


def test_write_uses_both_writers(monkeypatch, tmp_path: Path):
    import sizing.analysis as analysis_mod

    out_file = tmp_path / "sizing.xml"
    args = _args(output_file=str(out_file), circuit_netlist="input.hspice")
    analysis = AutomaticSizingAnalysis(args)
    analysis.result = SizingResult()

    calls: dict[str, tuple] = {}

    class FakeXMLWriter:
        def __init__(self, result):
            assert result is analysis.result

        def write(self, path):
            calls["xml"] = (Path(path),)

    class FakeSizedWriter:
        def __init__(self, result):
            assert result is analysis.result

        def write(self, in_netlist, out_netlist):
            calls["sized"] = (in_netlist, Path(out_netlist))

    monkeypatch.setattr(analysis_mod, "SizingXMLWriter", FakeXMLWriter)
    monkeypatch.setattr(analysis_mod, "SizedCircuitWriter", FakeSizedWriter)

    analysis.write()

    assert calls["xml"] == (out_file,)
    assert calls["sized"] == (
        args.circuit_netlist,
        out_file.with_suffix(".sized.hspice"),
    )


# ─────────────────────────────────────────────────────────────────────────
# §8d — real performance models (integration on the cascoded OTA fixture)
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.slow
class TestPerformanceModels:
    """The solver's performance estimate uses real first-order OTA equations
    on the solved operating point (gain on the gm-in/gds-out path, Ft, slew
    rate, phase margin, output swing) — not the old all-device average / zeros.
    """

    @pytest.fixture(scope="class")
    def perf(self, inputs_dir):
        import math

        src = inputs_dir / "AutomaticSizing"
        args = SimpleNamespace(
            circuit_netlist=str(src / "cascodedSymmetricalCMOSOTA.hspice"),
            device_types_file=str(src / "deviceTypes.xcat"),
            hspice_mapping_file=str(src / "HSpiceMapping.xcat"),
            hspice_supplynet_file=str(src / "supplyNets.xcat"),
            xml_circuit_information_file=str(src / "CircuitParameterAndSpecifications.xml"),
            xml_technologie_file=str(src / "TechnologyFile.xml"),
            xml_structrec_library_file=None,
            runtime=4.0, transistor_model="SHM", scaling="0.1mum",
            output_file="/tmp/_perf.xml",
        )
        analysis = AutomaticSizingAnalysis(args)
        analysis.initialize()
        analysis.compute()
        return analysis, analysis.result.performance, math

    def test_metrics_are_real_not_zero(self, perf):
        _, p, _ = perf
        # all four previously-zero metrics are now computed
        assert p.transit_freq_mhz > 0.0
        assert p.slew_rate > 0.0
        assert 0.0 < p.phase_margin_deg <= 90.0
        assert p.vout_max_v > p.vout_min_v

    def test_gain_on_proper_path_meets_spec(self, perf):
        _, p, _ = perf
        # gain computed on the gm(input)/gds(output) path, not an average
        assert p.gain_db >= 80.0  # meets the 80 dB spec

    def test_transit_freq_matches_b_gm_over_cl(self, perf):
        # Ft = B·gm_in/(2π·C_L) with the symmetrical-OTA mirror factor
        # B = I_out_branch/(I_tail/2)  (acst calculateTransitFrequency)
        analysis, p, math = perf
        result = analysis.result
        partition = analysis.partition
        solver = analysis.solver
        gm_in = solver._input_gm(result, partition)
        cl_pf = solver._load_cap_pf(analysis.circuit_info)
        i_tail = solver._tail_current_na(result, partition)
        i_out = solver._output_branch_current_na(
            result, analysis.circuit, analysis.circuit_info)
        b = i_out / (i_tail / 2.0) if i_tail > 0 and i_out > 0 else 1.0
        expected = b * gm_in / (2.0 * math.pi * cl_pf) * 1e-3
        assert p.transit_freq_mhz == pytest.approx(expected, rel=1e-6)

    def test_output_swing_within_rails(self, perf):
        analysis, p, _ = perf
        vdd = analysis.circuit_info.parameters.supply_voltage[1]
        assert 0.0 <= p.vout_min_v < p.vout_max_v <= vdd

    def test_design_meets_all_specs(self, perf):
        # §8d constraint reformulation: with the gain constraint on the output
        # node (not the diff-pair gds) the solver no longer pins the input
        # overdrive ~0, so the design meets *every* spec — including slew rate,
        # which the old formulation could not.
        analysis, p, _ = perf
        specs = analysis.circuit_info.specifications
        assert p.gain_db >= specs.min_gain
        assert p.transit_freq_mhz >= specs.min_transit_freq
        assert p.slew_rate >= specs.max_slew_rate          # min slew requirement
        assert p.phase_margin_deg >= specs.phase_margin
        assert p.power_mw <= specs.max_power
        assert p.total_area_um2 <= specs.max_area

    def test_input_overdrive_not_pinned_to_zero(self, perf):
        # the min-overdrive constraint keeps every device in strong inversion
        # (Vov >= gate_overdrive spec = 130 mV), not the old ~3 mV degenerate.
        analysis, _, _ = perf
        from partitioning.result import StageType
        tc = analysis.partition.transconductance_parts(StageType.FIRST)
        for s in tc:
            for d in s.devices:
                if d.name in analysis.result.devices:
                    assert analysis.result.devices[d.name].vov >= 100  # mV

    # ── issue #56: CM input range is constrained, not just reported ──

    def test_cm_input_range_meets_spec(self, perf):
        """The CM-range spec (±0.5 V around the 2.5 V input DC) is posted as
        a constraint, so any feasible design satisfies it — previously the
        metric was computed (#50) but unconstrained, and the solver violated
        vcmMin (2.29 V > 2.0 V)."""
        analysis, p, _ = perf
        vin = analysis.circuit_info.parameters.input_minus[1]
        specs = analysis.circuit_info.specifications
        assert p.min_cm_input_v <= vin + specs.vcm_min + 1e-9
        assert p.max_cm_input_v >= vin + specs.vcm_max - 1e-9

    def test_cm_range_constraints_in_problem(self, perf):
        analysis, _, _ = perf
        descs = [c.description() for c in analysis.problem.constraints]
        # the input-Vov + tail-Vgs stack bound (one per input device)
        assert sum("_Vov" in d and "_Vgs" in d and "<=" in d for d in descs) >= 2

    def test_single_stage_ota_has_no_second_stage(self, perf):
        """The cascoded symmetrical OTA's mirror-driven output branch is a
        current mirror, not a gain stage — the issue-#61 detector must not
        fire on it (its gain/Ft would silently change otherwise)."""
        from sizing.topology import second_stage_pieces

        analysis, _, _ = perf
        assert second_stage_pieces(
            analysis.circuit, analysis.partition,
            analysis.circuit_info.parameters.output_net) is None

    # ── issue #49: solved DC operating point + capacitor values ──────

    def test_net_voltages_exported(self, perf):
        """Every circuit net gets a solved DC value: the rails and pinned
        inputs at their given voltages, internal nets from the solver."""
        analysis, _, _ = perf
        volts = analysis.result.net_voltages
        params = analysis.circuit_info.parameters
        assert volts[params.supply_voltage[0]] == params.supply_voltage[1]
        assert volts[params.ground[0]] == params.ground[1]
        assert volts[params.input_plus[0]] == params.input_plus[1]
        assert volts[params.input_minus[0]] == params.input_minus[1]
        # one entry per circuit net (16 on the cascoded OTA, as acst emits)
        assert len(volts) == len(analysis.circuit.nets)
        vdd = params.supply_voltage[1]
        assert all(0.0 <= v <= vdd for v in volts.values())

    def test_load_capacitor_exported(self, perf):
        analysis, _, _ = perf
        assert analysis.result.capacitors == {"cl": 20.0}

    def test_balanced_objective_over_satisfies(self, perf):
        # §8d objective swap: the acst-style maximised multi-objective produces a
        # *balanced* design that clears the gain spec by a comfortable margin
        # while respecting the area/power budgets.  (The old ×2 Ft/slew margins
        # were calibrated against the pre-#2 flat-gds gain model, which let the
        # solver fake gain with an oversized gm_in; with the cascode-composed
        # model — issue #2 — a short CI solve is spec-clean but climbs the
        # current ladder only with more solve time.)
        analysis, p, _ = perf
        specs = analysis.circuit_info.specifications
        assert p.gain_db >= specs.min_gain + 5          # comfortably over spec
        assert p.transit_freq_mhz >= specs.min_transit_freq
        assert p.slew_rate >= specs.max_slew_rate
        assert p.power_mw <= specs.max_power
        assert p.total_area_um2 <= specs.max_area
        # the design actually spends current/area (not the degenerate minimum)
        assert p.power_mw > 1.0


# ═══════════════════════════════════════════════════════════════════════
#  §issue-2 — performance-model validation against the acst reference
# ═══════════════════════════════════════════════════════════════════════


class TestModelValidationAgainstAcstReference:
    """Evaluate pyckt's performance model on *acst's own solved design*.

    The reference XML carries acst's W/L/Id per device plus its reported
    performance.  Deriving Vov/gm/gds from the SHM equations and feeding the
    result through ``_estimate_performance`` must reproduce acst's numbers —
    this isolates model error from optimizer error (issue #2's key experiment;
    the pre-#2 flat-gds gain model was ~52 dB off on this design).
    """

    @pytest.fixture(scope="class")
    def estimated(self, inputs_dir):
        import math
        import xml.etree.ElementTree as ET

        from sizing.result import DeviceSizing

        src = inputs_dir / "AutomaticSizing"
        args = SimpleNamespace(
            circuit_netlist=str(src / "cascodedSymmetricalCMOSOTA.hspice"),
            device_types_file=str(src / "deviceTypes.xcat"),
            hspice_mapping_file=str(src / "HSpiceMapping.xcat"),
            hspice_supplynet_file=str(src / "supplyNets.xcat"),
            xml_circuit_information_file=str(
                src / "CircuitParameterAndSpecifications.xml"),
            xml_technologie_file=str(src / "TechnologyFile.xml"),
            xml_structrec_library_file=None,
            runtime=0.1, transistor_model="SHM", scaling="0.1mum",
            output_file="/tmp/_ref.xml",
        )
        analysis = AutomaticSizingAnalysis(args)
        analysis.initialize()
        # build the problem/solver context without a real solve
        from recognition.rulegen import RuleGenerator
        from sizing.problem import SizingProblem
        from sizing.solver import SizingSolver
        rules = RuleGenerator().generate(analysis.structure_circuits)
        problem = SizingProblem.build(
            analysis.circuit, analysis.partition, rules, analysis.circuit_info)
        solver = SizingSolver(problem)

        # acst's reference design
        root = ET.parse(str(src / "cascodedSymmetricalCMOSOTA.xml")).getroot()
        res = root.find("automatic_sizing-results")
        dims = {
            t.get("name").lstrip("/"): (float(t.find("Width").text),
                                        float(t.find("Length").text))
            for t in res.find("Dimensions").find("Transistors")
        }
        currents = {c.get("name").lstrip("/"): abs(float(c.text)) * 1e-6
                    for c in res.find("Currents")}

        tech = analysis.circuit_info.technology
        from core.device import DeviceType, TechType
        result = SizingResult(solver_status="reference")
        for dev in analysis.circuit.devices:
            if dev.device_type != DeviceType.MOSFET:
                continue
            w, length = dims[dev.name]
            i_d = currents[dev.name]
            tp = tech.pmos if dev.tech_type == TechType.P else tech.nmos
            vov = math.sqrt(2 * i_d / (tp.mu_cox * (w / length)))
            gm = math.sqrt(2 * tp.mu_cox * (w / length) * i_d)
            gds = tp.lambda_strong * i_d
            result.devices[dev.name] = DeviceSizing(
                name=dev.name,
                width=round(w), length=round(length),
                current=round(i_d * 1e9),
                vov=round(vov * 1e3),
                vgs=round(vov * 1e3 + abs(tp.threshold_voltage) * 1e3),
                vds=0,
                gm=round(gm * 1e9), gds=round(gds * 1e9),
                area=round(w * length),
            )
        perf = solver._estimate_performance(result)
        return perf

    def test_gain_matches_reference(self, estimated):
        assert estimated.gain_db == pytest.approx(90.0, abs=1.0)

    def test_transit_frequency_matches_reference(self, estimated):
        assert estimated.transit_freq_mhz == pytest.approx(6.929, rel=0.05)

    def test_slew_rate_matches_reference(self, estimated):
        assert estimated.slew_rate == pytest.approx(22.52, rel=0.03)

    def test_phase_margin_matches_reference(self, estimated):
        assert estimated.phase_margin_deg == pytest.approx(60.73, abs=4.0)

    def test_power_matches_reference(self, estimated):
        assert estimated.power_mw == pytest.approx(6.118, rel=0.03)

    def test_output_swing_matches_reference(self, estimated):
        assert estimated.vout_min_v == pytest.approx(0.670, abs=0.05)
        assert estimated.vout_max_v == pytest.approx(4.25, abs=0.05)

    # ── issue #50: AC / common-mode metrics ───────────────────────────

    def test_cmrr_matches_reference(self, estimated):
        assert estimated.cmrr_db == pytest.approx(133.0, abs=1.5)

    def test_psrr_matches_reference(self, estimated):
        assert estimated.pos_psrr_deg == pytest.approx(55.0, abs=1.5)
        assert estimated.neg_psrr_deg == pytest.approx(46.0, abs=1.5)

    def test_cm_input_range_matches_reference(self, estimated):
        assert estimated.max_cm_input_v == pytest.approx(4.24, abs=0.05)
        assert estimated.min_cm_input_v == pytest.approx(1.15, abs=0.05)
