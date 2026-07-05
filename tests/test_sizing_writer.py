"""Tests for sizing.writer module."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from sizing.result import DeviceSizing, ExpectedPerformance, SizingResult
from sizing.writer import (
    AcstSizingXMLWriter,
    SizedCircuitWriter,
    SizingXMLWriter,
)


def _sample_result() -> SizingResult:
    return SizingResult(
        devices={
            "m0": DeviceSizing("m0", width=10, length=2, current=50_000, vgs=800, vds=700, vov=400, gm=2_000_000, gds=100_000, area=20),
            "m1": DeviceSizing("m1", width=5, length=1, current=20_000, vgs=750, vds=650, vov=300, gm=900_000, gds=40_000, area=5),
        },
        performance=ExpectedPerformance(
            gain_db=81.2,
            transit_freq_mhz=2.75,
            slew_rate=3.5,
            power_mw=0.5,
            total_area_um2=25.0,
            phase_margin_deg=60.0,
            vout_min_v=1.0,
            vout_max_v=3.0,
        ),
        solver_status="optimal",
        iterations=7,
    )


def test_sizing_xml_writer_build_tree_has_expected_structure():
    writer = SizingXMLWriter(_sample_result())
    root = writer.build_tree()

    assert root.tag == "SizingResult"
    assert root.get("status") == "optimal"
    assert root.get("iterations") == "7"
    # Phase 3: timing attribute always present
    assert root.get("solve_time_seconds") is not None

    devices = root.find("Devices")
    assert devices is not None
    device_names = [d.get("name") for d in devices.findall("Device")]
    assert sorted(device_names) == ["m0", "m1"]

    perf = root.find("ExpectedPerformance")
    assert perf is not None
    assert perf.find("Gain").text is not None
    assert perf.find("PhaseMargin").text is not None


def test_sizing_xml_writer_to_string_and_write(tmp_path: Path):
    writer = SizingXMLWriter(_sample_result())

    text = writer.to_string()
    assert "<SizingResult" in text
    assert "<Devices>" in text

    out = tmp_path / "sizing.xml"
    writer.write(out)
    parsed = ET.parse(out).getroot()
    assert parsed.tag == "SizingResult"


def test_replace_or_append_parameter_replaces_existing_case_insensitive():
    line = "m0 d g s b nch w=1e-6 L=2e-6"
    replaced = SizedCircuitWriter._replace_or_append_parameter(line, "W", "10e-6")
    assert "W=10e-6" in replaced or "w=10e-6" in replaced


def test_replace_or_append_parameter_appends_if_missing():
    line = "m0 d g s b nch"
    out = SizedCircuitWriter._replace_or_append_parameter(line, "L", "2e-6")
    assert out.endswith(" L=2e-6")


def test_format_um_as_meter():
    assert SizedCircuitWriter._format_um_as_meter(10) == "10e-6"


def test_rewrite_line_covers_non_device_and_device_cases():
    writer = SizedCircuitWriter(_sample_result())

    assert writer._rewrite_line("") == ""
    assert writer._rewrite_line("   ") == "   "
    assert writer._rewrite_line("* comment") == "* comment"
    assert writer._rewrite_line(".option post") == ".option post"
    assert writer._rewrite_line("+ continuation") == "+ continuation"

    unknown = "mx d g s b nch W=1e-6 L=1e-6"
    assert writer._rewrite_line(unknown) == unknown

    known_with_params = "m0 d g s b nch W=1e-6 L=1e-6"
    rewritten = writer._rewrite_line(known_with_params)
    assert "W=10e-6" in rewritten
    assert "L=2e-6" in rewritten

    known_without_params = "m1 d g s b pch"
    rewritten2 = writer._rewrite_line(known_without_params)
    assert "W=5e-6" in rewritten2
    assert "L=1e-6" in rewritten2


def test_render_preserves_trailing_newline_and_write_roundtrip(tmp_path: Path):
    writer = SizedCircuitWriter(_sample_result())
    netlist = "* header\nm0 d g s b nch W=1e-6 L=1e-6\nmx d g s b nch W=1e-6 L=1e-6\n"

    rendered = writer.render(netlist)
    assert rendered.endswith("\n")
    assert "m0 d g s b nch W=10e-6 L=2e-6" in rendered
    assert "mx d g s b nch W=1e-6 L=1e-6" in rendered

    in_path = tmp_path / "in.hspice"
    out_path = tmp_path / "out.hspice"
    in_path.write_text(netlist)
    writer.write(in_path, out_path)

    out_text = out_path.read_text()
    assert "W=10e-6" in out_text


def test_xml_writer_no_solution_emits_no_solution_element():
    """Phase 3: infeasible result produces <NoSolution> instead of <Devices>."""
    result = SizingResult(solver_status="infeasible", iterations=0)
    writer = SizingXMLWriter(result)
    root = writer.build_tree()

    assert root.get("status") == "infeasible"
    assert root.find("Devices") is None
    no_sol = root.find("NoSolution")
    assert no_sol is not None
    assert no_sol.get("reason") == "infeasible"


def test_xml_writer_objective_value_attribute():
    """Phase 3: objective_value appears as XML attribute when present."""
    result = _sample_result()
    result.objective_value = 42.5
    root = SizingXMLWriter(result).build_tree()
    assert root.get("objective_value") == "42.5"


def test_xml_writer_no_objective_value_omits_attribute():
    """Phase 3: objective_value attribute absent when None."""
    root = SizingXMLWriter(_sample_result()).build_tree()
    assert root.get("objective_value") is None


# ── acst-format writer ────────────────────────────────────────────────────


def test_acst_sizing_writer_envelope_and_performance():
    root = AcstSizingXMLWriter(_sample_result()).build_tree()
    assert root.tag == "acst_results"
    assert root.find("date") is not None
    results = root.find("automatic_sizing-results")
    assert results is not None

    perf = results.find("ExpectedPerformance")
    gain = perf.find("Gain")
    assert gain.get("unit") == "dB" and gain.text == "81.2"
    # acst unit spellings
    assert perf.find("Power").get("unit") == "m_W"
    assert perf.find("Area").get("unit") == "(mu_m)^2"
    assert perf.find("TransitFrequency").get("unit") == "M_Hz"
    assert perf.find("SlewRate").get("unit") == "V/mum_s"
    assert perf.find("PhaseMargin").get("unit") == "degree"
    # acst renames TotalArea → Area, carries vout as Max/MinimumOutputVoltage
    assert perf.find("Area").text == "25"
    assert perf.find("MaximumOutputVoltage").text == "3"


def test_acst_sizing_writer_currents_and_dimensions():
    root = AcstSizingXMLWriter(_sample_result()).build_tree()
    results = root.find("automatic_sizing-results")

    currents = results.find("Currents")
    assert currents.get("unit") == "mu_A"
    comps = {c.get("name"): c.text for c in currents.findall("Component")}
    # leading-slash names; nA → µA (50_000 nA = 50 µA)
    assert comps["/m0"] == "50"
    assert comps["/m1"] == "20"

    transistors = results.find("Dimensions").find("Transistors")
    by_name = {t.get("name"): t for t in transistors.findall("Transistor")}
    assert set(by_name) == {"/m0", "/m1"}
    assert by_name["/m0"].find("Width").get("unit") == "mu_m"
    assert by_name["/m0"].find("Width").text == "10"
    assert by_name["/m0"].find("Length").text == "2"


def test_acst_sizing_writer_no_solution():
    empty = SizingResult(solver_status="infeasible")
    root = AcstSizingXMLWriter(empty).build_tree()
    results = root.find("automatic_sizing-results")
    ns = results.find("NoSolution")
    assert ns is not None and ns.get("reason") == "infeasible"


# ── acst-parity fields added in issue #1 ──────────────────────────────────


def _full_result() -> SizingResult:
    """Sample carrying every acst-parity field populated."""
    r = _sample_result()
    r.performance.transit_freq_error_factor_mhz = 2.2
    r.performance.cmrr_db = 78.0
    r.performance.neg_psrr_deg = 65.0
    r.performance.pos_psrr_deg = 70.0
    r.performance.max_cm_input_v = 2.4
    r.performance.min_cm_input_v = 0.6
    r.net_voltages = {"out": 1.65, "vdd!": 3.3, "gnd!": 0.0}
    r.capacitors = {"c1": 1.2, "c2": 0.5}
    return r


def test_acst_writer_always_emits_transit_freq_error_factor_and_shells():
    # even the bare sample (no optional AC metrics) carries the always-present
    # TransitFrequencyWithErrorFactor node and the Voltages / Capacitors shells
    root = AcstSizingXMLWriter(_sample_result()).build_tree()
    results = root.find("automatic_sizing-results")
    perf = results.find("ExpectedPerformance")

    tf_ef = perf.find("TransitFrequencyWithErrorFactor")
    assert tf_ef is not None and tf_ef.get("unit") == "M_Hz"
    # falls back to the nominal transit frequency when not separately computed
    assert tf_ef.text == "2.75"

    assert results.find("Voltages") is not None
    assert results.find("Voltages").get("unit") == "V"
    assert results.find("Dimensions").find("Capacitors") is not None


def test_acst_writer_omits_conditional_ac_metrics_when_absent():
    perf = (
        AcstSizingXMLWriter(_sample_result())
        .build_tree()
        .find("automatic_sizing-results")
        .find("ExpectedPerformance")
    )
    for tag in ("CMRR", "negPSRR", "posPSRR",
                "maxCommonModeInputVoltage", "minCommonModeInputVoltage"):
        assert perf.find(tag) is None


def test_acst_writer_emits_all_performance_fields_in_acst_order():
    perf = (
        AcstSizingXMLWriter(_full_result())
        .build_tree()
        .find("automatic_sizing-results")
        .find("ExpectedPerformance")
    )
    assert [child.tag for child in perf] == [
        "Gain", "Power", "Area", "TransitFrequency",
        "TransitFrequencyWithErrorFactor", "SlewRate", "PhaseMargin",
        "CMRR", "negPSRR", "posPSRR",
        "MaximumOutputVoltage", "MinimumOutputVoltage",
        "maxCommonModeInputVoltage", "minCommonModeInputVoltage",
    ]
    assert perf.find("CMRR").get("unit") == "dB"
    assert perf.find("CMRR").text == "78"
    assert perf.find("negPSRR").get("unit") == "degree"
    assert perf.find("posPSRR").text == "70"
    assert perf.find("maxCommonModeInputVoltage").get("unit") == "V"
    assert perf.find("minCommonModeInputVoltage").text == "0.6"


def test_acst_writer_voltages_section():
    results = (
        AcstSizingXMLWriter(_full_result())
        .build_tree()
        .find("automatic_sizing-results")
    )
    voltages = results.find("Voltages")
    assert voltages.get("unit") == "V"
    nets = {n.get("name"): n.text for n in voltages.findall("Net")}
    # leading-slash net names, sorted
    assert nets == {"/out": "1.65", "/vdd!": "3.3", "/gnd!": "0"}


def test_acst_writer_capacitor_dimensions():
    dims = (
        AcstSizingXMLWriter(_full_result())
        .build_tree()
        .find("automatic_sizing-results")
        .find("Dimensions")
    )
    caps = dims.find("Capacitors")
    by_name = {c.get("name"): c for c in caps.findall("Capacitor")}
    assert set(by_name) == {"/c1", "/c2"}
    value = by_name["/c1"].find("Value")
    assert value.get("unit") == "p_F"
    assert value.text == "1.2"
