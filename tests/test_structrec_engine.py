"""Tests for the structure recognition engine."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from core.circuit import Circuit
from core.device import Device, DeviceType, PinType, TechType
from core.net import Net, NetId, Supply, SupplyType
from core.terminal import Terminal
from recognition.library import (
    PERSISTENCE_MAX,
    ArrayConnection,
    ArrayConnectionRule,
    ArrayLibrary,
    ArrayLibraryItem,
    CharacteristicConnection,
    ChildPinType,
    DevicePinType,
    DominanceRelation,
    HierarchyEntry,
    Library,
    PairConnectionRule,
    PairLibrary,
    PairLibraryItem,
    PairNetRule,
    PairPinMapping,
    StructurePinType,
)
from recognition.model import (
    ArrayStructure,
    PairStructure,
    StructureCircuits,
    StructureId,
    StructureNet,
    StructurePin,
)
from recognition.recognizer import (
    ArrayRecognizer,
    PairRecognizer,
    StructureRecognizer,
)
from recognition.rulegen import (
    EqualLengthRule,
    EqualWLRule,
    MatchedPairRule,
    RuleGenerator,
)
from recognition.writer import (
    AcstStructRecXMLWriter,
    RuleXMLWriter,
    StructRecXMLWriter,
)

# ── Helpers ──────────────────────────────────────────────────────────

def _net(name: str, supply: SupplyType = SupplyType.NO_SUPPLY) -> Net:
    n = Net(NetId(name)); n.supply = Supply(supply); return n

def _mosfet(name: str, tech: TechType, nets: dict[str, Net]) -> Device:
    dev = Device(name=name, device_type=DeviceType.MOSFET, tech_type=tech)
    pm = {"Drain": PinType.DRAIN, "Gate": PinType.GATE,
          "Source": PinType.SOURCE, "Bulk": PinType.BULK}
    for pn, net in nets.items():
        dev.add_terminal(Terminal(dev, pm[pn], net))
    return dev

def _circuit(name, devices_spec) -> Circuit:
    """Build circuit from list of (dev_name, tech, {pin: net}) tuples."""
    ckt = Circuit(name)
    nets = {}
    for _, _, pin_nets in devices_spec:
        for n in pin_nets.values():
            if n.name not in nets:
                nets[n.name] = n; ckt.add_net(n)
    for dname, tech, pin_nets in devices_spec:
        ckt.add_device(_mosfet(dname, tech, pin_nets))
    return ckt

_gnd = lambda: _net("gnd!", SupplyType.GND)

def _mirror_circuit() -> Circuit:
    gnd = _gnd(); dg = _net("net_dg"); out = _net("net_out")
    return _circuit("mirror", [
        ("m0", TechType.N, {"Drain": dg, "Gate": dg, "Source": gnd, "Bulk": gnd}),
        ("m1", TechType.N, {"Drain": out, "Gate": dg, "Source": gnd, "Bulk": gnd}),
    ])

def _diffpair_circuit() -> Circuit:
    gnd = _gnd(); d0 = _net("d0"); d1 = _net("d1")
    inp = _net("inp"); inn = _net("inn"); tail = _net("tail")
    return _circuit("dp", [
        ("m0", TechType.N, {"Drain": d0, "Gate": inp, "Source": tail, "Bulk": gnd}),
        ("m1", TechType.N, {"Drain": d1, "Gate": inn, "Source": tail, "Bulk": gnd}),
    ])


# ── Library fixtures ─────────────────────────────────────────────────

def _normal_item() -> ArrayLibraryItem:
    S = StructurePinType; D = DevicePinType
    return ArrayLibraryItem(
        name="MosfetNormalArray",
        connections=[ArrayConnection(S("MosfetNormalArray", p), D("Mosfet", p))
                     for p in ("Drain", "Gate", "Source")],
        device_type_rule="Mosfet",
        connection_rules=[ArrayConnectionRule(False, D("Mosfet","Gate"), D("Mosfet","Drain"))],
        parallel_nets=[D("Mosfet", p) for p in ("Gate", "Source", "Bulk")],
    )

def _diode_item() -> ArrayLibraryItem:
    S = StructurePinType; D = DevicePinType
    return ArrayLibraryItem(
        name="MosfetDiodeArray",
        connections=[ArrayConnection(S("MosfetDiodeArray","DrainGate"), D("Mosfet","Drain")),
                     ArrayConnection(S("MosfetDiodeArray","Source"), D("Mosfet","Source"))],
        device_type_rule="Mosfet",
        connection_rules=[ArrayConnectionRule(True, D("Mosfet","Gate"), D("Mosfet","Drain"))],
        parallel_nets=[D("Mosfet", p) for p in ("Drain", "Source", "Bulk")],
    )

def _array_lib() -> ArrayLibrary:
    lib = ArrayLibrary()
    d, n = _diode_item(), _normal_item()
    lib.items = {d.name: d, n.name: n}
    lib.active = [HierarchyEntry(d.name), HierarchyEntry(n.name)]
    return lib

def _cm_pair_item() -> PairLibraryItem:
    S = StructurePinType
    return PairLibraryItem(
        name="MosfetSimpleCurrentMirror", symmetry=False, is_helper_structure=False,
        connections=[
            PairPinMapping(S("MosfetSimpleCurrentMirror","Input"),
                           ChildPinType(1, S("MosfetDiodeArray","DrainGate"))),
            PairPinMapping(S("MosfetSimpleCurrentMirror","Output"),
                           ChildPinType(2, S("MosfetNormalArray","Drain"))),
        ],
        characteristic=CharacteristicConnection(
            S("MosfetDiodeArray","DrainGate"), [S("MosfetNormalArray","Gate")]),
        tech_type_rule="same",
        net_rules=[PairNetRule(S("MosfetDiodeArray","Source"), 1, "supply"),
                   PairNetRule(S("MosfetNormalArray","Source"), 2, "supply")],
        connection_rules=[PairConnectionRule(True,
            S("MosfetDiodeArray","Source"), S("MosfetNormalArray","Source"))],
    )

def _dp_pair_item() -> PairLibraryItem:
    S = StructurePinType
    return PairLibraryItem(
        name="MosfetDifferentialPair", symmetry=True, is_helper_structure=False,
        connections=[
            PairPinMapping(S("MosfetDifferentialPair", p),
                           ChildPinType(c, S("MosfetNormalArray", cp)))
            for p, c, cp in [("Drain1",1,"Drain"),("Drain2",2,"Drain"),
                              ("Gate1",1,"Gate"),("Gate2",2,"Gate"),("Source",1,"Source")]
        ],
        characteristic=CharacteristicConnection(
            S("MosfetNormalArray","Source"), [S("MosfetNormalArray","Source")]),
        tech_type_rule="same",
        net_rules=[PairNetRule(S("MosfetNormalArray","Source"), 1, "no_supply")],
        connection_rules=[],
    )

def _pair_lib() -> PairLibrary:
    lib = PairLibrary()
    cm, dp = _cm_pair_item(), _dp_pair_item()
    lib.items = {cm.name: cm, dp.name: dp}
    lib.levels = {1: [HierarchyEntry(cm.name), HierarchyEntry(dp.name)]}
    lib.dominance = []
    return lib

def _library() -> Library:
    return Library(array_library=_array_lib(), pair_library=_pair_lib())

def _mirror_arrays():
    gnd = _net("gnd!", SupplyType.GND); dg = _net("net_dg")
    diode = ArrayStructure(StructureId("MosfetDiodeArray", 0), TechType.N)
    for pn, n in [("DrainGate", dg), ("Source", gnd)]:
        p = StructurePin(pn); diode.add_pin(p); StructureNet(n.name, core_net=n).add_pin(p)
    normal = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
    for pn, n in [("Drain", _net("out")), ("Gate", dg), ("Source", gnd)]:
        p = StructurePin(pn); normal.add_pin(p); StructureNet(n.name, core_net=n).add_pin(p)
    return [diode, normal]


# ═════════════════════════════════════════════════════════════════════
#  Tests
# ═════════════════════════════════════════════════════════════════════

class TestArrayRecognizer:
    def test_normal_mosfets_grouped(self):
        gnd = _gnd(); g = _net("g"); s = _net("s")
        ckt = _circuit("t", [
            ("m0", TechType.N, {"Drain": _net("d0"), "Gate": g, "Source": s, "Bulk": gnd}),
            ("m1", TechType.N, {"Drain": _net("d1"), "Gate": g, "Source": s, "Bulk": gnd}),
        ])
        arrays = ArrayRecognizer(_array_lib()).recognize(ckt)
        normal = [a for a in arrays if a.name == "MosfetNormalArray"]
        assert len(normal) == 1 and normal[0].device_count == 2

    def test_diode_detected(self):
        gnd = _gnd(); dg = _net("dg")
        ckt = _circuit("t", [("m0", TechType.N, {"Drain": dg, "Gate": dg, "Source": _net("s"), "Bulk": gnd})])
        arrays = ArrayRecognizer(_array_lib()).recognize(ckt)
        assert any(a.name == "MosfetDiodeArray" for a in arrays)

    def test_mirror_gives_two_arrays(self):
        arrays = ArrayRecognizer(_array_lib()).recognize(_mirror_circuit())
        names = sorted(a.name for a in arrays)
        assert names == ["MosfetDiodeArray", "MosfetNormalArray"]

    def test_pins_wired(self):
        gnd = _gnd(); dg = _net("dg")
        ckt = _circuit("t", [("m0", TechType.N, {"Drain": dg, "Gate": dg, "Source": _net("s"), "Bulk": gnd})])
        arr = ArrayRecognizer(_array_lib()).recognize(ckt)[0]
        assert arr.has_pin("DrainGate") and arr.has_pin("Source")

    def test_empty_circuit(self):
        assert ArrayRecognizer(_array_lib()).recognize(Circuit("e")) == []


class TestPairRecognizer:
    def test_current_mirror(self):
        pairs = PairRecognizer(_pair_lib(), 1).recognize(_mirror_arrays())
        assert len(pairs) == 1 and pairs[0].name == "MosfetSimpleCurrentMirror"

    def test_no_match_different_tech(self):
        arrs = _mirror_arrays(); arrs[1].tech_type = TechType.P
        pairs = PairRecognizer(_pair_lib(), 1).recognize(arrs)
        assert len(pairs) == 0

    def test_diff_pair(self):
        tail = _net("tail"); d0 = _net("d0"); d1 = _net("d1")
        def make_na(idx, drain, gate):
            a = ArrayStructure(StructureId("MosfetNormalArray", idx), TechType.N)
            for pn, n in [("Drain", drain), ("Gate", gate), ("Source", tail)]:
                p = StructurePin(pn); a.add_pin(p); StructureNet(n.name, core_net=n).add_pin(p)
            return a
        pairs = PairRecognizer(_pair_lib(), 1).recognize([make_na(0, d0, _net("inp")), make_na(1, d1, _net("inn"))])
        assert len(pairs) == 1 and pairs[0].name == "MosfetDifferentialPair"


class TestDominance:
    def test_pairrecognizer_no_longer_resolves_dominance(self):
        # Dominance moved to the orchestrator (StructureRecognizer._remove_dominated).
        # PairRecognizer now returns ALL matching candidates, sharing children.
        arrs = _mirror_arrays()
        cm = _cm_pair_item()
        weak = PairLibraryItem(name="WeakMirror", symmetry=False, is_helper_structure=False,
            connections=cm.connections, characteristic=cm.characteristic,
            tech_type_rule="same", net_rules=cm.net_rules, connection_rules=cm.connection_rules)
        lib = PairLibrary()
        lib.items = {cm.name: cm, weak.name: weak}
        lib.levels = {1: [HierarchyEntry(cm.name), HierarchyEntry(weak.name)]}
        lib.dominance = [DominanceRelation(["MosfetSimpleCurrentMirror"], ["WeakMirror"])]
        pairs = PairRecognizer(lib, 1).recognize(arrs)
        names = sorted(p.name for p in pairs)
        assert names == ["MosfetSimpleCurrentMirror", "WeakMirror"]


class TestStructureRecognizer:
    def test_mirror_pipeline(self):
        result = StructureRecognizer(_library()).recognize(_mirror_circuit())
        assert result.has_level(0) and len(result.get_level(0).structures) == 2
        if result.has_level(1):
            assert any("CurrentMirror" in p.name for p in result.get_level(1).structures)

    def test_diffpair_pipeline(self):
        result = StructureRecognizer(_library()).recognize(_diffpair_circuit())
        if result.has_level(1):
            assert any("DifferentialPair" in p.name for p in result.get_level(1).structures)

    def test_empty(self):
        assert StructureRecognizer(_library()).recognize(Circuit("e")).total_structures == 0


class TestRuleGenerator:
    def _mirror_sc(self):
        m0 = Device("m0", DeviceType.MOSFET, TechType.N)
        m1 = Device("m1", DeviceType.MOSFET, TechType.N)
        d = ArrayStructure(StructureId("MosfetDiodeArray", 0), TechType.N, device_list=[m0])
        n = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N, device_list=[m1])
        p = PairStructure(StructureId("MosfetSimpleCurrentMirror", 0), d, n, tech_type=TechType.N)
        sc = StructureCircuits(); sc.add_structure(d, 0); sc.add_structure(n, 0); sc.add_structure(p, 1)
        return sc

    def test_mirror_rules(self):
        rules = RuleGenerator().generate(self._mirror_sc())
        assert {"equal_length", "equal_wl"} <= {r.rule_type for r in rules}

    def test_dedup(self):
        r1 = EqualLengthRule("X", "equal_length", ["m0","m1"], "")
        r2 = EqualLengthRule("Y", "equal_length", ["m1","m0"], "")
        assert len(RuleGenerator._deduplicate([r1, r2])) == 1

    def test_diffpair_rules(self):
        m0 = Device("m0", DeviceType.MOSFET, TechType.N)
        m1 = Device("m1", DeviceType.MOSFET, TechType.N)
        a1 = ArrayStructure(StructureId("MosfetNormalArray",0), TechType.N, device_list=[m0])
        a2 = ArrayStructure(StructureId("MosfetNormalArray",1), TechType.N, device_list=[m1])
        p = PairStructure(StructureId("MosfetDifferentialPair",0), a1, a2, symmetric=True, tech_type=TechType.N)
        sc = StructureCircuits(); sc.add_structure(a1,0); sc.add_structure(a2,0); sc.add_structure(p,1)
        assert any(r.rule_type == "matched" for r in RuleGenerator().generate(sc))

    def test_skips_structures_without_devices(self):
        empty = ArrayStructure(StructureId("MosfetSimpleCurrentMirror", 0), TechType.N)
        sc = StructureCircuits(); sc.add_structure(empty, 0)
        assert RuleGenerator().generate(sc) == []


class TestXMLWriters:
    def test_structrec_xml(self, tmp_path):
        arr = ArrayStructure(StructureId("MosfetNormalArray",0), TechType.N,
                             device_list=[Device("m0", DeviceType.MOSFET, TechType.N)])
        p = StructurePin("Drain"); arr.add_pin(p); StructureNet("net_d").add_pin(p)
        sc = StructureCircuits(); sc.add_structure(arr, 0)
        out = tmp_path / "r.xml"; StructRecXMLWriter().write(sc, out)
        assert ET.parse(out).getroot().find("Structure").get("name") == "MosfetNormalArray"

    def test_rule_xml(self, tmp_path):
        out = tmp_path / "rules.xml"
        RuleXMLWriter().write([EqualLengthRule("M","equal_length",["m0","m1"],"T")], out)
        root = ET.parse(out).getroot()
        assert root.find("Rule").get("type") == "equal_length"
        assert [d.text for d in root.find("Rule").findall("Device")] == ["m0", "m1"]

    def test_structrec_xml_pair_children(self, tmp_path):
        d = ArrayStructure(StructureId("MosfetDiodeArray", 0), TechType.N,
                           device_list=[Device("m0", DeviceType.MOSFET, TechType.N)])
        n = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N,
                           device_list=[Device("m1", DeviceType.MOSFET, TechType.N)])
        p = PairStructure(StructureId("MosfetSimpleCurrentMirror", 0), d, n, tech_type=TechType.N)
        sc = StructureCircuits(); sc.add_structure(d, 0); sc.add_structure(n, 0); sc.add_structure(p, 1)
        out = tmp_path / "pair.xml"; StructRecXMLWriter().write(sc, out)
        root = ET.parse(out).getroot()
        s = root.find("Structure")
        assert s is not None and s.find("Children") is not None
        assert len(s.find("Children").findall("Structure")) == 2

    def test_structrec_xml_orphan_pin_uses_question_mark(self, tmp_path):
        arr = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N,
                             device_list=[Device("m0", DeviceType.MOSFET, TechType.N)])
        arr.add_pin(StructurePin("Orphan"))  # intentionally unconnected pin
        sc = StructureCircuits(); sc.add_structure(arr, 0)
        out = tmp_path / "orphan.xml"; StructRecXMLWriter().write(sc, out)
        root = ET.parse(out).getroot()
        pin = root.find("Structure").find("Pins").find("Pin")
        assert pin.get("name") == "Orphan" and pin.get("net") == "?"

    def test_acst_structrec_xml_array(self, tmp_path):
        # acst schema: <acst_results>/<structure_recognition_results>, lowercase
        # tags, <devices><device>, leading-slash names, bracketed instance index.
        arr = ArrayStructure(StructureId("MosfetNormalArray", 2), TechType.N,
                             device_list=[Device("m0", DeviceType.MOSFET, TechType.N)])
        p = StructurePin("Drain"); arr.add_pin(p); StructureNet("net_d").add_pin(p)
        sc = StructureCircuits(); sc.add_structure(arr, 0)
        out = tmp_path / "acst.xml"; AcstStructRecXMLWriter().write(sc, out)
        root = ET.parse(out).getroot()
        assert root.tag == "acst_results"
        assert root.find("date") is not None
        results = root.find("structure_recognition_results")
        s = results.find("structure")
        assert s.get("name") == "MosfetNormalArray[2]"
        assert s.get("techType") == "n" and s.get("instance") == "/"
        dev = s.find("devices").find("device")
        assert dev.get("name") == "/m0"
        assert dev.get("deviceType") == "Mosfet" and dev.get("techType") == "n"
        assert s.find("pins").find("pin").get("net") == "/net_d"

    def test_acst_structrec_xml_pair_nested_directly(self, tmp_path):
        # Children must be nested directly inside the parent <structure>
        # (no <Children> wrapper, unlike the native format).
        d = ArrayStructure(StructureId("MosfetDiodeArray", 0), TechType.N,
                           device_list=[Device("m0", DeviceType.MOSFET, TechType.N)])
        n = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N,
                           device_list=[Device("m1", DeviceType.MOSFET, TechType.N)])
        p = PairStructure(StructureId("MosfetSimpleCurrentMirror", 0), d, n, tech_type=TechType.N)
        sc = StructureCircuits(); sc.add_structure(d, 0); sc.add_structure(n, 0); sc.add_structure(p, 1)
        out = tmp_path / "acst_pair.xml"; AcstStructRecXMLWriter().write(sc, out)
        root = ET.parse(out).getroot()
        top = root.find("structure_recognition_results").find("structure")
        assert top.get("name") == "MosfetSimpleCurrentMirror[0]"
        assert top.find("Children") is None
        assert len(top.findall("structure")) == 2


# ═════════════════════════════════════════════════════════════════════
#  Missing-branch coverage tests
# ═════════════════════════════════════════════════════════════════════

class TestMissingBranches:
    """Targeted tests for previously uncovered branches in recognizer.py."""

    # ── _get_device_net exception (lines 43-44) ───────────────────────

    def test_get_device_net_exception(self):
        """_get_device_net returns None when device.get_net raises (lines 43-44)."""
        from recognition.recognizer import _get_device_net
        dev = Device(name="m0", device_type=DeviceType.MOSFET, tech_type=TechType.N)
        # No terminals added → get_net raises KeyError → lines 43-44
        result = _get_device_net(dev, "Gate")
        assert result is None

    # ── ArrayRecognizer._classify / recognize branches (lines 68, 86, 90, 97) ──

    def test_recognize_skips_unmatched_device(self):
        """Device that can't be classified is skipped (lines 68, 86, 90)."""
        ckt = Circuit("t")
        gnd = _net("gnd!", SupplyType.GND)
        ckt.add_net(gnd)
        # BIPOLAR device fails device_type check for MOSFET library (line 86 continue)
        bipolar = Device(name="q0", device_type=DeviceType.BIPOLAR, tech_type=TechType.N)
        ckt.add_device(bipolar)
        # result: template=None (line 90), continue in recognize (line 68)
        arrays = ArrayRecognizer(_array_lib()).recognize(ckt)
        assert arrays == []

    def test_classify_returns_none_missing_pins(self):
        """MOSFET with no terminals: _conn_rules_ok returns False via None nets (lines 43-44, 90, 97)."""
        from recognition.recognizer import _get_device_net
        ckt = Circuit("t")
        dev = Device(name="m0", device_type=DeviceType.MOSFET, tech_type=TechType.N)
        ckt.add_device(dev)
        # Passes device_type check, but _conn_rules_ok gets None nets → line 97 return False
        # Both templates fail → line 90 return None → line 68 continue
        arrays = ArrayRecognizer(_array_lib()).recognize(ckt)
        assert arrays == []

    # ── PairRecognizer._check_characteristic (lines 184, 192-193) ────

    def test_check_characteristic_missing_pin(self):
        """c1 has right name but missing the required pin (line 184)."""
        S = StructurePinType
        char = CharacteristicConnection(S("MosfetDiodeArray", "DrainGate"),
                                        [S("MosfetNormalArray", "Gate")])
        c1 = ArrayStructure(StructureId("MosfetDiodeArray", 0), TechType.N)
        # DrainGate pin NOT added
        c2 = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
        assert PairRecognizer._check_characteristic(char, c1, c2) is False

    def test_check_characteristic_runtime_error(self):
        """c2 pin exists but has no net → RuntimeError caught (lines 192-193)."""
        S = StructurePinType
        char = CharacteristicConnection(S("MosfetDiodeArray", "DrainGate"),
                                        [S("MosfetNormalArray", "Gate")])
        c1 = ArrayStructure(StructureId("MosfetDiodeArray", 0), TechType.N)
        dg_net = StructureNet("dg")
        p1 = StructurePin("DrainGate"); c1.add_pin(p1); dg_net.add_pin(p1)

        c2 = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
        p2 = StructurePin("Gate"); c2.add_pin(p2)   # pin exists but no net
        # c2.get_pin("Gate").net raises RuntimeError → continue → return False (194)
        assert PairRecognizer._check_characteristic(char, c1, c2) is False

    # ── PairRecognizer._check_tech_type (lines 199-200) ──────────────

    def test_check_tech_type_different(self):
        """tech_type_rule='different' branch (line 199)."""
        n = ArrayStructure(StructureId("A", 0), TechType.N)
        p = ArrayStructure(StructureId("B", 0), TechType.P)
        assert PairRecognizer._check_tech_type("different", n, p) is True
        assert PairRecognizer._check_tech_type("different", n, n) is False

    def test_check_tech_type_norule(self):
        """tech_type_rule='noRule' falls through to True (line 200)."""
        n = ArrayStructure(StructureId("A", 0), TechType.N)
        p = ArrayStructure(StructureId("B", 0), TechType.P)
        assert PairRecognizer._check_tech_type("noRule", n, p) is True

    # ── PairRecognizer._check_net_rules (lines 207, 210-211) ─────────

    def test_check_net_rules_name_mismatch(self):
        """structure_pin name doesn't match child name → return False (line 207)."""
        S = StructurePinType
        rules = [PairNetRule(S("WrongName", "Source"), 1, "supply")]
        c1 = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
        c2 = ArrayStructure(StructureId("MosfetNormalArray", 1), TechType.N)
        assert PairRecognizer._check_net_rules(rules, c1, c2) is False

    def test_check_net_rules_runtime_error(self):
        """Pin exists but has no net → RuntimeError → return False (lines 210-211)."""
        S = StructurePinType
        rules = [PairNetRule(S("MosfetNormalArray", "Source"), 1, "supply")]
        c1 = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
        c1.add_pin(StructurePin("Source"))  # pin present, no net → RuntimeError
        c2 = ArrayStructure(StructureId("MosfetNormalArray", 1), TechType.N)
        assert PairRecognizer._check_net_rules(rules, c1, c2) is False

    # ── PairRecognizer._check_conn_rules (lines 223, 226, 229-230, 232) ──

    def test_check_conn_rules_structure_name_mismatch(self):
        """first_child_pin structure name doesn't match c1 (line 223)."""
        S = StructurePinType
        rules = [PairConnectionRule(True, S("WrongName", "Source"),
                                    S("MosfetNormalArray", "Source"))]
        c1 = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
        c2 = ArrayStructure(StructureId("MosfetNormalArray", 1), TechType.N)
        assert PairRecognizer._check_conn_rules(rules, c1, c2) is False

    def test_check_conn_rules_missing_pin(self):
        """Pin referenced by rule doesn't exist on the structure (line 226)."""
        S = StructurePinType
        rules = [PairConnectionRule(True, S("MosfetNormalArray", "MissingPin"),
                                    S("MosfetNormalArray", "Source"))]
        c1 = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
        c2 = ArrayStructure(StructureId("MosfetNormalArray", 1), TechType.N)
        assert PairRecognizer._check_conn_rules(rules, c1, c2) is False

    def test_check_conn_rules_runtime_error(self):
        """Pin has no net → RuntimeError → return False (lines 229-230)."""
        S = StructurePinType
        rules = [PairConnectionRule(True, S("MosfetNormalArray", "Source"),
                                    S("MosfetNormalArray", "Source"))]
        c1 = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
        c1.add_pin(StructurePin("Source"))   # no net
        c2 = ArrayStructure(StructureId("MosfetNormalArray", 1), TechType.N)
        c2.add_pin(StructurePin("Source"))   # no net
        assert PairRecognizer._check_conn_rules(rules, c1, c2) is False

    def test_check_conn_rules_connected_mismatch(self):
        """r.connected=True but pins are on different nets → return False (line 232)."""
        S = StructurePinType
        rules = [PairConnectionRule(True, S("MosfetNormalArray", "Source"),
                                    S("MosfetNormalArray", "Source"))]
        c1 = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
        p1 = StructurePin("Source"); c1.add_pin(p1); StructureNet("net1").add_pin(p1)
        c2 = ArrayStructure(StructureId("MosfetNormalArray", 1), TechType.N)
        p2 = StructurePin("Source"); c2.add_pin(p2); StructureNet("net2").add_pin(p2)
        assert PairRecognizer._check_conn_rules(rules, c1, c2) is False

    # ── is_helper_structure branch (line 151) ─────────────────────────

    def test_helper_structure_sets_persistence_without_creating_pair(self):
        """is_helper_structure=True: no pair emitted, children pinned to MAX persistence.

        Mirrors acst PairLibraryItem::recognize — a helper structure is
        recognition scaffolding only; it is not instantiated, it just keeps its
        children alive as standalone top-level structures.
        """
        cm = _cm_pair_item()
        helper_item = PairLibraryItem(
            name=cm.name, symmetry=cm.symmetry, is_helper_structure=True,
            connections=cm.connections, characteristic=cm.characteristic,
            tech_type_rule=cm.tech_type_rule, net_rules=cm.net_rules,
            connection_rules=cm.connection_rules,
        )
        lib = PairLibrary()
        lib.items = {helper_item.name: helper_item}
        lib.levels = {1: [HierarchyEntry(helper_item.name)]}
        lib.dominance = []
        arrs = _mirror_arrays()
        pairs = PairRecognizer(lib, 1).recognize(arrs)
        assert pairs == []                       # helper is NOT instantiated
        assert arrs[0].persistence == PERSISTENCE_MAX
        assert arrs[1].persistence == PERSISTENCE_MAX

    # ── symmetric reversed candidate (line 167) ──────────────────────

    def test_symmetric_reversed_candidate(self):
        """Symmetric item where (a,b) order fails but (b,a) succeeds (line 167)."""
        S = StructurePinType
        # CM item with symmetry=True: first child must be Diode, second Normal
        sym_item = PairLibraryItem(
            name="MosfetSimpleCurrentMirror", symmetry=True, is_helper_structure=False,
            connections=_cm_pair_item().connections,
            characteristic=CharacteristicConnection(
                S("MosfetDiodeArray", "DrainGate"), [S("MosfetNormalArray", "Gate")]),
            tech_type_rule="same", net_rules=[], connection_rules=[],
        )
        lib = PairLibrary()
        lib.items = {sym_item.name: sym_item}
        lib.levels = {1: [HierarchyEntry(sym_item.name)]}
        lib.dominance = []
        arrs = _mirror_arrays()          # [diode, normal]
        arrs_reversed = [arrs[1], arrs[0]]  # [normal, diode]
        # Recognition tries all ordered pairs: (diode, normal) matches the
        # characteristic regardless of input ordering.
        pairs = PairRecognizer(lib, 1).recognize(arrs_reversed)
        assert len(pairs) == 1

    # ── shared children: all candidates recognised (non-exclusive) ────

    def test_shared_child_yields_all_candidates(self):
        """A child shared by two matches yields BOTH pairs (no exclusive consume)."""
        gnd = _net("gnd!", SupplyType.GND)
        dg = _net("dg")

        diode = ArrayStructure(StructureId("MosfetDiodeArray", 0), TechType.N)
        for pn, n in [("DrainGate", dg), ("Source", gnd)]:
            p = StructurePin(pn); diode.add_pin(p)
            StructureNet(n.name, core_net=n).add_pin(p)

        def _make_normal(idx):
            arr = ArrayStructure(StructureId("MosfetNormalArray", idx), TechType.N)
            for pn, n in [("Drain", _net(f"out{idx}")), ("Gate", dg), ("Source", gnd)]:
                p = StructurePin(pn); arr.add_pin(p)
                StructureNet(n.name, core_net=n).add_pin(p)
            return arr

        n1 = _make_normal(0)
        n2 = _make_normal(1)
        # Both (diode, n1) and (diode, n2) match the CM item → two pairs sharing
        # the diode.  Conflict resolution is deferred to the orchestrator.
        pairs = PairRecognizer(_pair_lib(), 1).recognize([diode, n1, n2])
        assert len(pairs) == 2
        assert all(p.name == "MosfetSimpleCurrentMirror" for p in pairs)

    # ── _build_pair RuntimeError (pin exists but has no net) ──────────

    def test_build_pair_runtime_error_pin_no_net(self):
        """Child pin exists but has no net → RuntimeError caught; pair still built."""
        S = StructurePinType

        # Pair item that maps pair pin to child1's "Source" pin
        item = PairLibraryItem(
            name="TestPair", symmetry=False, is_helper_structure=False,
            connections=[
                PairPinMapping(S("TestPair", "PairPin"),
                               ChildPinType(1, S("MosfetNormalArray", "Source")))
            ],
            characteristic=CharacteristicConnection(
                S("MosfetNormalArray", "Source"), [S("MosfetNormalArray", "Source")]),
            tech_type_rule="same", net_rules=[], connection_rules=[],
        )
        c1 = ArrayStructure(StructureId("MosfetNormalArray", 0), TechType.N)
        c1.add_pin(StructurePin("Source"))   # pin exists but NO net → RuntimeError
        c2 = ArrayStructure(StructureId("MosfetNormalArray", 1), TechType.N)

        lib = PairLibrary()
        lib.items = {item.name: item}
        lib.levels = {1: [HierarchyEntry(item.name)]}
        lib.dominance = []
        recognizer = PairRecognizer(lib, 1)
        pair = recognizer._build_pair(item, c1, c2, 0, PERSISTENCE_MAX)
        # RuntimeError caught, pair is still created
        assert pair.name == "TestPair"
