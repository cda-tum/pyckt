"""Tests for the partitioning module.

Unit tests with mock structures and an integration test using the
cascoded-symmetrical-CMOS-OTA netlist.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ckt_io.circuit_info_parser import CircuitParameter
from core.device import Device, DeviceType, TechType
from core.net import Supply, SupplyType
from partitioning.partitioner import Partitioner
from partitioning.result import PartitionResult, PartType, StageType
from partitioning.writer import AcstPartitionXMLWriter, PartitionXMLWriter
from recognition.model import (
    ArrayStructure,
    PairStructure,
    StructureCircuit,
    StructureCircuits,
    StructureId,
    StructureNet,
    StructurePin,
)

# ═══════════════════════════════════════════════════════════════════════
#  Helpers for building mock structures
# ═══════════════════════════════════════════════════════════════════════

def _make_net(name: str, *, supply_type: SupplyType = SupplyType.NO_SUPPLY) -> StructureNet:
    supply = Supply(supply_type)
    return StructureNet(name, supply=supply)


def _make_array(name: str, tech: TechType, pin_map: dict[str, StructureNet],
                index: int = 0) -> ArrayStructure:
    sid = StructureId(name, index)
    arr = ArrayStructure(sid, tech_type=tech)
    for pn, net in pin_map.items():
        pin = StructurePin(pn)
        arr.add_pin(pin)
        pin.net = net
        net.add_pin(pin)
    return arr


def _make_pair(name: str, tech: TechType, child1, child2,
               pin_map: dict[str, StructureNet], index: int = 0) -> PairStructure:
    sid = StructureId(name, index)
    pair = PairStructure(sid, child1, child2, tech_type=tech)
    for pn, net in pin_map.items():
        pin = StructurePin(pn)
        pair.add_pin(pin)
        pin.net = net
        net.add_pin(pin)
    child1.add_parent(pair)
    child2.add_parent(pair)
    return pair


def _simple_params() -> CircuitParameter:
    return CircuitParameter(
        input_plus=("inp", 2.5),
        input_minus=("inn", 2.5),
        output_net="out",
        bias_current=("ibias", 10.0),
        supply_voltage=("vdd!", 5.0),
        ground=("gnd!", 0.0),
        load_capacities=[("cl", 20.0)],
    )


def _build_simple_ota() -> tuple[StructureCircuits, CircuitParameter]:
    """Simple single-stage OTA: diffpair + mirror load + tail bias + load cap."""
    params = _simple_params()

    vdd = _make_net("vdd!", supply_type=SupplyType.VDD)
    gnd = _make_net("gnd!", supply_type=SupplyType.GND)
    inp = _make_net("inp")
    inn = _make_net("inn")
    out = _make_net("out")
    tail = _make_net("tail")
    ibias = _make_net("ibias")

    m3 = _make_array("NormalArray", TechType.N, {"Gate": inp, "Drain": out, "Source": tail}, 0)
    m4 = _make_array("NormalArray", TechType.N, {"Gate": inn, "Drain": out, "Source": tail}, 1)
    m1 = _make_array("NormalArray", TechType.P, {"Gate": out, "Drain": out, "Source": vdd}, 2)
    m2 = _make_array("NormalArray", TechType.P, {"Gate": out, "Drain": out, "Source": vdd}, 3)
    m0 = _make_array("NormalArray", TechType.N, {"Gate": ibias, "Drain": tail, "Source": gnd}, 4)
    m8 = _make_array("NormalArray", TechType.N, {"Gate": ibias, "Drain": ibias, "Source": gnd}, 5)
    cap = _make_array("CapacitorArray", TechType.UNDEFINED, {"Plus": out, "Minus": gnd}, 6)

    diffpair = _make_pair(
        "MosfetDifferentialPair", TechType.N, m3, m4,
        {"Gate1": inp, "Gate2": inn, "Drain": out, "Source": tail},
    )
    mirror = _make_pair(
        "MosfetSimpleCurrentMirror", TechType.P, m1, m2,
        {"Gate": out, "Drain": out, "Source": vdd}, index=1,
    )
    tail_bias = _make_pair(
        "MosfetSimpleCurrentMirror", TechType.N, m0, m8,
        {"Gate": ibias, "Drain": tail, "Source": gnd}, index=0,
    )

    sc = StructureCircuits()
    lv0 = StructureCircuit(0)
    for s in [m3, m4, m1, m2, m0, m8, cap]:
        lv0.add_structure(s)
    lv1 = StructureCircuit(1)
    for s in [diffpair, mirror, tail_bias]:
        lv1.add_structure(s)
    sc.add_level(lv0)
    sc.add_level(lv1)

    return sc, params


# ═══════════════════════════════════════════════════════════════════════
#  Unit Tests — PartitionResult
# ═══════════════════════════════════════════════════════════════════════

class TestPartitionResult:
    def test_assign_and_lookup(self):
        arr = _make_array("Test", TechType.N, {}, 0)
        r = PartitionResult()
        r.assign(arr, PartType.TRANSCONDUCTANCE, StageType.FIRST, "test")
        assert r.is_classified(arr)
        assert r.get_part(arr).part_type is PartType.TRANSCONDUCTANCE

    def test_unclassified(self):
        arr = _make_array("Test", TechType.N, {}, 0)
        r = PartitionResult()
        assert not r.is_classified(arr)
        assert r.get_part(arr) is None

    def test_filtered_accessors(self):
        a = _make_array("A", TechType.N, {}, 0)
        b = _make_array("B", TechType.P, {}, 1)
        r = PartitionResult()
        r.assign(a, PartType.TRANSCONDUCTANCE, StageType.FIRST)
        r.assign(b, PartType.LOAD, StageType.FIRST)
        assert r.transconductance_parts(StageType.FIRST) == [a]
        assert r.load_parts(StageType.FIRST) == [b]
        assert r.bias_parts() == []

    def test_is_two_stage_false(self):
        assert not PartitionResult().is_two_stage()

    def test_summary(self):
        a = _make_array("A", TechType.N, {}, 0)
        r = PartitionResult()
        r.assign(a, PartType.BIAS, StageType.UNDEFINED, "test bias")
        assert "bias=1" in r.summary()

    def test_repr(self):
        r = PartitionResult()
        assert repr(r) == "PartitionResult(0 assignments)"


# ═══════════════════════════════════════════════════════════════════════
#  Unit Tests — Partitioner on simple OTA mock
# ═══════════════════════════════════════════════════════════════════════

class TestPartitionerSimpleOTA:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.sc, self.params = _build_simple_ota()
        self.result = Partitioner(self.params).partition(self.sc)

    def test_all_parentless_classified(self):
        for s in self.sc.structures_without_parents:
            assert self.result.is_classified(s), f"{s.name} not classified"

    def test_diff_pair_is_tc_first(self):
        tc = self.result.transconductance_parts(StageType.FIRST)
        assert any("DifferentialPair" in s.name for s in tc)

    def test_p_mirror_is_load_first(self):
        loads = self.result.load_parts(StageType.FIRST)
        assert any(s.tech_type == TechType.P for s in loads)

    def test_tail_bias_identified(self):
        bias = self.result.bias_parts()
        assert any(s.tech_type == TechType.N for s in bias)

    def test_capacitor_identified(self):
        caps = self.result.capacitance_parts()
        assert any("Capacitor" in s.name for s in caps)

    def test_not_two_stage(self):
        assert not self.result.is_two_stage()


# ═══════════════════════════════════════════════════════════════════════
#  Unit Tests — PartitionXMLWriter
# ═══════════════════════════════════════════════════════════════════════

class TestPartitionXMLWriter:
    @pytest.fixture(autouse=True)
    def _setup(self):
        sc, params = _build_simple_ota()
        self.result = Partitioner(params).partition(sc)
        self.writer = PartitionXMLWriter(self.result)

    def test_root_tag(self):
        root = self.writer.build_tree()
        assert root.tag == "PartitioningResult"

    def test_has_first_stage(self):
        root = self.writer.build_tree()
        assert root.find("FirstStage") is not None

    def test_no_second_stage(self):
        root = self.writer.build_tree()
        assert root.find("SecondStage") is None

    def test_has_transconductance(self):
        root = self.writer.build_tree()
        assert root.find("FirstStage/Transconductance") is not None

    def test_to_string_valid_xml(self):
        xml_str = self.writer.to_string()
        root = ET.fromstring(xml_str)
        assert root.tag == "PartitioningResult"

    def test_write_to_file(self, tmp_path):
        out = tmp_path / "partitioning.xml"
        self.writer.write(out)
        assert out.exists()
        tree = ET.parse(out)
        assert tree.getroot().tag == "PartitioningResult"

    def test_build_tree_with_second_stage(self):
        r = PartitionResult()
        s2 = _make_array("AnalogInverter", TechType.N, {}, 42)
        r.assign(s2, PartType.TRANSCONDUCTANCE, StageType.SECOND, "second tc")
        root = PartitionXMLWriter(r).build_tree()
        second = root.find("SecondStage")
        assert second is not None
        assert second.find("Transconductance") is not None

    def test_add_role_group_fallback_branch(self):
        writer = PartitionXMLWriter(PartitionResult())
        root = ET.Element("R")
        writer._add_role_group(root, "X", PartType.CAPACITANCE, StageType.FIRST)
        assert root.find("X") is None


# ═══════════════════════════════════════════════════════════════════════
#  Unit Tests — AcstPartitionXMLWriter (C++-compatible schema)
# ═══════════════════════════════════════════════════════════════════════

class TestAcstPartitionXMLWriter:
    """The acst writer consumes an :class:`AcstPartitionResult` and emits the
    eight ``circuit_partitioning_results`` sections."""

    def _result(self):
        from partitioning.acst_parts import (
            AcstPartitionResult,
            BiasPart,
            CapacitancePart,
            LoadPart,
            TransconductancePart,
        )
        net = StructureNet("net36")
        dp = _make_array("MosfetDifferentialPair", TechType.N,
                         {"Source": net}, index=1)
        dp.set_devices([Device("m3", DeviceType.MOSFET, TechType.N)])
        load_struct = _make_array("MosfetDiodeArray", TechType.P,
                                  {"Drain": StructureNet("n29")}, index=3)
        load_struct.set_devices([Device("m11", DeviceType.MOSFET, TechType.P)])
        bias_struct = _make_array("MosfetNormalArray", TechType.N,
                                  {"Drain": StructureNet("n36")}, index=4)
        bias_struct.set_devices([Device("m0", DeviceType.MOSFET, TechType.N)])
        cap_struct = _make_array("CapacitorArray", TechType.UNDEFINED,
                                 {"Plus": StructureNet("out")}, index=0)
        cap_struct.set_devices([Device("cl", DeviceType.CAPACITOR, TechType.UNDEFINED)])

        r = AcstPartitionResult()
        tp = TransconductancePart(0); tp.add_main_structure(dp)
        tp.type = "firstStage"; tp.first_stage_type = "symmetrical"
        r.add_transconductance_part(tp)
        lp = LoadPart(0); lp.add_main_structure(load_struct); r.add_load_part(lp)
        bp = BiasPart(0); bp.add_main_structure(bias_struct); bp.type = "currentBias"
        r.add_bias_part(bp)
        cp = CapacitancePart(0); cp.add_main_structure(cap_struct); cp.type = "load"
        r.add_capacitance_part(cp)
        return r

    def test_acst_envelope_and_all_sections(self):
        root = AcstPartitionXMLWriter(self._result()).build_tree()
        assert root.tag == "acst_results"
        assert root.find("date") is not None
        cpr = root.find("circuit_partitioning_results")
        assert cpr is not None
        for sec in ("gmParts", "loadParts", "biasParts", "capacitances",
                    "resistorParts", "commonModeSignalDetectorParts",
                    "positiveFeedbackParts", "undefinedParts"):
            assert cpr.find(sec) is not None, sec

    def test_acst_gmpart_first_stage_attrs_and_topology(self):
        root = AcstPartitionXMLWriter(self._result()).build_tree()
        gm = root.find("circuit_partitioning_results/gmParts/gmPart")
        assert gm.get("type") == "firstStage"
        assert gm.get("firstStageType") == "symmetrical"
        s = gm.find("structure")
        assert s.get("name") == "MosfetDifferentialPair[1]"
        assert s.find("pins/pin").get("net") == "/net36"
        assert s.find("devices/device").get("name") == "/m3"

    def test_acst_load_bias_capacitance_sections(self):
        root = AcstPartitionXMLWriter(self._result()).build_tree()
        cpr = root.find("circuit_partitioning_results")
        assert cpr.find("loadParts/loadPart/structure/devices/device").get("name") == "/m11"
        assert cpr.find("biasParts/biasPart/structure/devices/device").get("name") == "/m0"
        cap = cpr.find("capacitances/capacitance")
        assert cap.get("type") == "load"
        assert cap.find("structure/devices/device").get("name") == "/cl"


# ═══════════════════════════════════════════════════════════════════════
#  Integration Test — full pipeline on cascoded OTA
# ═══════════════════════════════════════════════════════════════════════

DATA = Path(__file__).resolve().parent / "data"


def _have_test_data() -> bool:
    required = [
        "cascodedSymmetricalCMOSOTA.hspice",
        "deviceTypes.xcat",
        "HSpiceMapping.xcat",
        "supplyNets.xcat",
        "CircuitParameterAndSpecifications.xml",
    ]
    return all((DATA / f).exists() for f in required)


@pytest.mark.skipif(not _have_test_data(), reason="test data not available")
class TestPartitioningIntegration:
    """Full pipeline: .hspice → recognize → partition → XML."""

    @pytest.fixture(scope="class")
    def pipeline(self):
        from ckt_io.circuit_info_parser import parse_circuit_parameters
        from ckt_io.device_types_parser import load_device_types
        from ckt_io.hspice_mapping import HSpiceMapping
        from ckt_io.hspice_parser import HSpiceParser
        from ckt_io.supply_nets_parser import SupplyNetConfig
        from recognition.library import Library
        from recognition.recognizer import StructureRecognizer

        device_types = load_device_types(DATA / "deviceTypes.xcat")
        mapping = HSpiceMapping.from_file(DATA / "HSpiceMapping.xcat")
        supply_nets = SupplyNetConfig.from_file(DATA / "supplyNets.xcat")
        circuit = HSpiceParser(mapping, supply_nets, device_types).parse(
            DATA / "cascodedSymmetricalCMOSOTA.hspice"
        )
        library = Library.from_directory()
        sc = StructureRecognizer(library).recognize(circuit)
        params = parse_circuit_parameters(DATA / "CircuitParameterAndSpecifications.xml")
        result = Partitioner(params).partition(sc)
        return sc, result, params

    def test_all_parentless_classified(self, pipeline):
        sc, result, _ = pipeline
        for s in sc.structures_without_parents:
            assert result.is_classified(s), f"{s.name} not classified"

    def test_has_transconductance(self, pipeline):
        _, result, _ = pipeline
        tc = result.transconductance_parts(StageType.FIRST)
        assert any("DifferentialPair" in s.name for s in tc)

    def test_has_load(self, pipeline):
        _, result, _ = pipeline
        assert len(result.load_parts(StageType.FIRST)) >= 1

    def test_has_bias(self, pipeline):
        _, result, _ = pipeline
        assert len(result.bias_parts()) >= 1

    def test_has_capacitance(self, pipeline):
        _, result, _ = pipeline
        assert len(result.capacitance_parts()) >= 1

    def test_xml_output(self, pipeline):
        _, result, _ = pipeline
        xml_str = PartitionXMLWriter(result).to_string()
        root = ET.fromstring(xml_str)
        assert root.tag == "PartitioningResult"
        assert root.find("FirstStage") is not None

    def test_summary(self, pipeline):
        _, result, _ = pipeline
        s = result.summary()
        assert "bias=" in s
        assert "transconductance=" in s

    def test_acst_partitioner_gm_path_matches_acst(self, pipeline):
        # §8b: the acst-faithful partitioner reproduces acst's gm-path exactly:
        # firstStage (symmetrical) = m3,m4; primarySecondStage = m9,m10;
        # secondarySecondStage = m12,m14.
        from partitioning.acst_partitioner import AcstPartitioner

        sc, _, params = pipeline
        res = AcstPartitioner(params).partition(sc)
        by_type = {t.type: t.devices() for t in res.transconductance_parts}
        assert by_type.get("firstStage") == ["m3", "m4"]
        assert by_type.get("primarySecondStage") == ["m10", "m9"]
        assert by_type.get("secondarySecondStage") == ["m12", "m14"]
        first = res.get_first_stage()
        assert first.first_stage_type == "symmetrical"

    def test_acst_partitioner_all_sections_match_acst(self, pipeline):
        # §8b: every section matches acst's device→part assignment.
        from partitioning.acst_partitioner import AcstPartitioner

        sc, _, params = pipeline
        res = AcstPartitioner(params).partition(sc)
        load = sorted(lp.devices() for lp in res.load_parts)
        bias = sorted(bp.devices() for bp in res.bias_parts)
        caps = sorted(cp.devices() for cp in res.capacitance_parts)
        assert load == [["m11", "m13"]]
        assert bias == [["m0"], ["m1", "m2"], ["m15"], ["m16"],
                        ["m17"], ["m5", "m6"], ["m7"], ["m8"]]
        assert caps == [["cl"]]
        assert res.undefined_parts == []


# ═══════════════════════════════════════════════════════════════════════
#  Missing-branch coverage tests for partitioner.py
# ═══════════════════════════════════════════════════════════════════════

class TestPartitionerMissingBranches:
    def test_step1_classified_continue_and_pin_runtimeerror(self):
        p = Partitioner(_simple_params())
        p._first_stage_output_nets = set()

        a1 = _make_array("NormalArray", TechType.N, {}, 0)
        a2 = _make_array("NormalArray", TechType.N, {}, 1)
        inp = _make_net("inp")
        tail = _make_net("tail")
        diff = _make_pair(
            "MosfetDifferentialPair", TechType.N, a1, a2,
            {"Gate1": inp, "Source": tail},
        )
        diff.add_pin(StructurePin("Orphan"))  # unconnected pin -> RuntimeError path

        result = PartitionResult()
        result.assign(diff, PartType.UNDEFINED, StageType.UNDEFINED, "pre")
        p._step1_identify_input_pair([diff], result)  # classified -> continue (line 89)

        result = PartitionResult()
        p._step1_identify_input_pair([diff], result)  # exception branch in pin iteration
        assert result.get_part(diff).part_type is PartType.TRANSCONDUCTANCE

    def test_early_return_steps_2_to_6(self):
        p = Partitioner(_simple_params())
        r = PartitionResult()
        p._first_stage_output_nets = set()
        p._second_stage_output_nets = set()

        p._step2_identify_first_stage_bias([], r)
        p._step3_identify_first_stage_load([], r)
        p._step4_identify_first_stage_load_cascode([], r)
        p._step5_identify_first_stage_tc_cascode([], r)
        p._step6_identify_second_stage_tc([], r, StructureCircuits())

    def test_step2_source_pin_runtimeerror(self):
        p = Partitioner(_simple_params())
        tc = _make_array("MosfetDifferentialPair", TechType.N, {}, 0)
        tc.add_pin(StructurePin("Source"))  # unconnected source pin

        r = PartitionResult()
        r.assign(tc, PartType.TRANSCONDUCTANCE, StageType.FIRST, "tc")
        p._step2_identify_first_stage_bias([tc], r)

    def test_steps4_to9_assignment_paths(self):
        p = Partitioner(_simple_params())

        # step 4
        p._first_stage_output_nets = {"n1"}
        r4 = PartitionResult()
        load = _make_array("LoadPart", TechType.P, {"P": _make_net("n1")}, 0)
        r4.assign(load, PartType.LOAD, StageType.FIRST, "load")
        cas_load = _make_array("SomeCascode", TechType.P, {"X": _make_net("n1")}, 1)
        p._step4_identify_first_stage_load_cascode([cas_load], r4)
        assert r4.get_part(cas_load).part_type is PartType.LOAD

        # step 5
        r5 = PartitionResult()
        tc = _make_array("MosfetDifferentialPair", TechType.N, {"N": _make_net("n2")}, 2)
        r5.assign(tc, PartType.TRANSCONDUCTANCE, StageType.FIRST, "tc")
        cas_tc = _make_array("AnyCascode", TechType.N, {"N": _make_net("n2")}, 3)
        p._step5_identify_first_stage_tc_cascode([cas_tc], r5)
        assert r5.get_part(cas_tc).part_type is PartType.TRANSCONDUCTANCE

        # step 6
        p._first_stage_output_nets = {"n2"}
        p._second_stage_output_nets = set()
        r6 = PartitionResult()
        pre = _make_array("Pre", TechType.N, {}, 4)
        r6.assign(pre, PartType.UNDEFINED, StageType.UNDEFINED, "pre")
        inv = _make_array("AnalogInverter", TechType.N, {"In": _make_net("n2"), "Out": _make_net("n3")}, 5)
        inv.add_pin(StructurePin("Orphan"))
        p._step6_identify_second_stage_tc([pre, inv], r6, StructureCircuits())
        assert r6.get_part(inv).part_type is PartType.TRANSCONDUCTANCE
        assert "n3" in p._second_stage_output_nets

        # step 7
        p._second_stage_output_nets = {"n3"}
        r7 = PartitionResult()
        pre7 = _make_array("Pre7", TechType.N, {}, 6)
        r7.assign(pre7, PartType.UNDEFINED, StageType.UNDEFINED, "pre")
        s7 = _make_array(
            "Load2", TechType.P,
            {"A": _make_net("n3"), "S": _make_net("vdd!", supply_type=SupplyType.VDD)},
            7,
        )
        p._step7_identify_second_stage_load([pre7, s7], r7)
        assert r7.get_part(s7).stage is StageType.SECOND

        # step 8
        r8 = PartitionResult()
        tc2 = _make_array("AnalogInverter", TechType.N, {"G": _make_net("n3")}, 8)
        r8.assign(tc2, PartType.TRANSCONDUCTANCE, StageType.SECOND, "tc2")
        pre8 = _make_array("Pre8", TechType.N, {}, 9)
        r8.assign(pre8, PartType.UNDEFINED, StageType.UNDEFINED, "pre")
        b8 = _make_array(
            "Bias2", TechType.P,
            {"X": _make_net("n3"), "Y": _make_net("vdd!", supply_type=SupplyType.VDD)},
            10,
        )
        p._step8_identify_second_stage_bias([pre8, b8], r8)
        assert r8.get_part(b8).part_type is PartType.BIAS

        # step 9
        p._first_stage_output_nets = {"n1"}
        p._second_stage_output_nets = {"n3"}
        r9 = PartitionResult()
        pre9 = _make_array("Pre9", TechType.N, {}, 11)
        r9.assign(pre9, PartType.UNDEFINED, StageType.UNDEFINED, "pre")
        not_cap = _make_array("NormalArray", TechType.N, {"A": _make_net("n1")}, 12)
        c9 = _make_array("CapacitorArray", TechType.UNDEFINED, {"P": _make_net("n1"), "M": _make_net("n3")}, 13)
        p._step9_identify_compensation_cap([pre9, not_cap, c9], r9)
        assert r9.get_part(c9).stage is StageType.COMPENSATION

    def test_step11_voltage_reference_and_diode_array_branches(self):
        p = Partitioner(_simple_params())
        r = PartitionResult()
        vref = _make_array("VoltageReferenceBlock", TechType.N, {"A": _make_net("x")}, 0)
        diode = _make_array(
            "MyDiodeArray", TechType.N,
            {"A": _make_net("y"), "S": _make_net("gnd!", supply_type=SupplyType.GND)},
            1,
        )
        p._step11_identify_remaining_bias([vref, diode], r, StructureCircuits())
        assert r.get_part(vref).part_type is PartType.BIAS
        assert r.get_part(diode).part_type is PartType.BIAS

    def test_utility_exception_paths(self):
        s = _make_array("X", TechType.N, {}, 0)
        s.add_pin(StructurePin("Orphan"))
        assert Partitioner._pin_net_names(s) == set()
        assert not Partitioner._has_supply_connection(s)
