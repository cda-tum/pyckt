"""Tests for the structure recognition model (StructureCircuit overlay).

Verifies the runtime structure circuit model that is produced by the
recognition engine.  Covers:

  - StructureId basics (frozen, hashing, str)
  - StructurePin creation, wiring, owner tracking
  - StructureNet supply delegation, pin management, queries
  - ArrayStructure device management, pin/net access, identity
  - PairStructure child navigation, tech-type inference, parent links
  - StructureCircuit single-level container operations
  - StructureCircuits multi-level queries, top-level, find, iteration

All tests use small hand-built circuits (no XML loading required).
"""

import pytest

from pyckt.core.circuit import Circuit
from pyckt.core.device import Device, DeviceType, TechType, PinType
from pyckt.core.net import Net, NetId, Supply, SupplyType
from pyckt.core.terminal import Terminal

from recognition.model import (
    StructureId,
    StructurePin,
    StructureNet,
    Structure,
    ArrayStructure,
    PairStructure,
    StructureCircuit,
    StructureCircuits,
    _PERSISTENCE_MAX,
)


# ═══════════════════════════════════════════════════════════════════════
#  Helper factories
# ═══════════════════════════════════════════════════════════════════════


def _make_nmos(name: str = "M1") -> Device:
    """Create a bare NMOS device (no terminals wired)."""
    return Device(name, DeviceType.MOSFET, TechType.N)


def _make_pmos(name: str = "M2") -> Device:
    return Device(name, DeviceType.MOSFET, TechType.P)


def _make_core_net(name: str, supply: Supply | None = None) -> Net:
    n = Net(NetId(name))
    if supply is not None:
        n.supply = supply
    return n


def _make_array(
    name: str = "MosfetNormalArray",
    index: int = 0,
    tech: TechType = TechType.N,
    devices: list[Device] | None = None,
    pin_names: tuple[str, ...] = ("Drain", "Gate", "Source"),
) -> ArrayStructure:
    """Build an ArrayStructure with pins wired to fresh nets."""
    sid = StructureId(name, index)
    arr = ArrayStructure(sid, tech_type=tech, device_list=devices or [_make_nmos(f"M_{index}")])
    for pn in pin_names:
        net = StructureNet(f"{pn}_net_{index}")
        pin = StructurePin(pn)
        arr.add_pin(pin)
        net.add_pin(pin)
    return arr


def _make_pair(
    name: str = "MosfetSimpleCurrentMirror",
    index: int = 0,
    child1: ArrayStructure | None = None,
    child2: ArrayStructure | None = None,
    symmetric: bool = False,
    tech: TechType = TechType.N,
    pin_names: tuple[str, ...] = ("Input", "Output", "Source"),
) -> PairStructure:
    """Build a PairStructure with children and pins."""
    c1 = child1 or _make_array("MosfetDiodeArray", index * 10 + 1, tech)
    c2 = child2 or _make_array("MosfetNormalArray", index * 10 + 2, tech)
    sid = StructureId(name, index)
    pair = PairStructure(sid, c1, c2, symmetric=symmetric, tech_type=tech)
    for pn in pin_names:
        net = StructureNet(f"{pn}_net_{index}")
        pin = StructurePin(pn)
        pair.add_pin(pin)
        net.add_pin(pin)
    return pair


# ═══════════════════════════════════════════════════════════════════════
#  StructureId
# ═══════════════════════════════════════════════════════════════════════


class TestStructureId:
    def test_frozen(self):
        sid = StructureId("Foo", 1)
        with pytest.raises(AttributeError):
            sid.name = "Bar"

    def test_equality_and_hash(self):
        a = StructureId("X", 0)
        b = StructureId("X", 0)
        c = StructureId("X", 1)
        assert a == b
        assert a != c
        assert hash(a) == hash(b)
        assert len({a, b, c}) == 2

    def test_str_and_defaults(self):
        assert str(StructureId("CM", 3)) == "CM#3"
        assert StructureId("Arr").index == 0


# ═══════════════════════════════════════════════════════════════════════
#  StructurePin
# ═══════════════════════════════════════════════════════════════════════


class TestStructurePin:
    def test_basic_creation(self):
        pin = StructurePin("Drain")
        assert pin.name == "Drain"
        assert not pin.is_connected

    def test_wiring_to_net(self):
        net = StructureNet("net1")
        pin = StructurePin("Gate")
        net.add_pin(pin)
        assert pin.is_connected
        assert pin.net is net
        assert pin in net.pins

    def test_error_on_unwired_pin(self):
        pin = StructurePin("Source")
        with pytest.raises(RuntimeError, match="not connected"):
            _ = pin.net
        with pytest.raises(RuntimeError, match="no owning structure"):
            _ = pin.structure

    def test_owner_and_equality(self):
        arr = _make_array()
        pin = arr.get_pin("Drain")
        assert pin.structure is arr
        assert arr.get_pin("Drain") is pin   # dict lookup → same object
        assert pin == arr.get_pin("Drain")

    def test_repr(self):
        arr = _make_array(name="TestArr", index=0)
        pin = arr.get_pin("Drain")
        r = repr(pin)
        assert "TestArr" in r
        assert "Drain" in r


# ═══════════════════════════════════════════════════════════════════════
#  StructureNet
# ═══════════════════════════════════════════════════════════════════════


class TestStructureNet:
    def test_basic(self):
        net = StructureNet("vdd")
        assert net.name == "vdd"
        assert not net.is_connected
        assert net.pins == []

    def test_supply_queries(self):
        # VDD from core net
        snet = StructureNet("VDD", core_net=_make_core_net("VDD", Supply.vdd()))
        assert snet.is_supply() and snet.is_vdd() and not snet.is_ground()
        # GND from explicit supply
        assert StructureNet("GND", supply=Supply.gnd()).is_ground()
        # No supply
        assert not StructureNet("internal").is_supply()
        # Core net overrides local supply annotation
        snet2 = StructureNet("n1", core_net=_make_core_net("n1"), supply=Supply.vdd())
        assert not snet2.is_supply()  # core net is not a supply → wins

    def test_pin_management(self):
        net = StructureNet("s_net")
        p1 = StructurePin("Source")
        p2 = StructurePin("Source")
        net.add_pin(p1)
        net.add_pin(p2)
        assert len(net.pins) == 2
        assert net.is_connected

        net.remove_pin(p1)
        assert len(net.pins) == 1

    def test_connected_structures(self):
        # Two different arrays
        net = StructureNet("shared")
        arr1, arr2 = _make_array(index=0), _make_array(index=1)
        for arr in (arr1, arr2):
            p = StructurePin("Drain")
            arr.add_pin(p)
            net.add_pin(p)
        assert len(net.connected_structures) == 2
        # Multiple pins from same structure → deduplicated
        net2 = StructureNet("net")
        arr = _make_array(index=5, pin_names=())
        for pname in ("Drain", "Gate"):
            p = StructurePin(pname)
            arr.add_pin(p)
            net2.add_pin(p)
        assert len(net2.connected_structures) == 1

    def test_find_pins_by_type(self):
        net = StructureNet("gate_net")
        arr1 = _make_array(name="MosfetNormalArray", index=0, pin_names=())
        arr2 = _make_array(name="MosfetDiodeArray", index=1, pin_names=())
        p1 = StructurePin("Gate")
        arr1.add_pin(p1)
        net.add_pin(p1)
        p2 = StructurePin("DrainGate")
        arr2.add_pin(p2)
        net.add_pin(p2)
        # Filter by structure name
        found = net.find_pins_by_type("MosfetNormalArray")
        assert len(found) == 1
        assert found[0].name == "Gate"
        # Filter by structure + pin name
        found2 = net.find_pins_by_type("MosfetDiodeArray", "DrainGate")
        assert len(found2) == 1

    def test_equality_hash_repr(self):
        a, b, c = StructureNet("x"), StructureNet("x"), StructureNet("y")
        assert a == b and a != c and hash(a) == hash(b)
        r = repr(StructureNet("VDD", core_net=_make_core_net("VDD", Supply.vdd())))
        assert "VDD" in r and "[VDD]" in r


# ═══════════════════════════════════════════════════════════════════════
#  Structure (base / ArrayStructure)
# ═══════════════════════════════════════════════════════════════════════


class TestArrayStructure:
    def test_creation(self):
        d1, d2 = _make_nmos("M1"), _make_nmos("M2")
        arr = ArrayStructure(
            StructureId("MosfetNormalArray", 0),
            tech_type=TechType.N,
            device_list=[d1, d2],
        )
        assert arr.is_array and not arr.is_pair
        assert arr.device_count == 2 and arr.first_device is d1
        assert arr.tech_type == TechType.N
        assert arr.array_children == [arr]  # leaf is its own array child

    def test_device_management(self):
        arr = ArrayStructure(StructureId("Arr", 0))
        assert arr.device_count == 0
        arr.add_device(_make_nmos())
        assert arr.device_count == 1
        arr.set_devices([_make_nmos("A"), _make_nmos("B")])
        assert arr.device_count == 2
        with pytest.raises(IndexError):
            _ = ArrayStructure(StructureId("Empty", 0)).first_device
        # devices property returns a copy
        d = _make_nmos()
        arr2 = ArrayStructure(StructureId("Arr", 1), device_list=[d])
        arr2.devices.clear()
        assert arr2.device_count == 1

    def test_pin_access(self):
        arr = _make_array(pin_names=("Drain", "Gate", "Source"))
        assert arr.has_pin("Drain") and not arr.has_pin("Bulk")
        assert arr.get_pin("Gate").name == "Gate"
        assert sorted(arr.pin_names) == ["Drain", "Gate", "Source"]
        assert isinstance(arr.find_net("Drain"), StructureNet)
        with pytest.raises(KeyError, match="no pin named"):
            arr.get_pin("NonExistent")

    def test_persistence(self):
        arr = ArrayStructure(StructureId("X", 0))
        assert arr.persistence == _PERSISTENCE_MAX and arr.has_max_persistence
        arr.persistence = 2
        assert arr.persistence == 2 and not arr.has_max_persistence
        arr.persistence = _PERSISTENCE_MAX
        assert arr.has_max_persistence

    def test_parent_and_connectivity(self):
        arr = _make_array(index=0, pin_names=("Drain",))
        assert not arr.has_parent and arr.parents == []
        assert arr.is_connected_to_net("Drain_net_0")
        assert not arr.is_connected_to_net("nonexistent")

    def test_shares_net_with(self):
        shared = StructureNet("shared_net")
        arr1 = _make_array(index=0, pin_names=())
        arr2 = _make_array(index=1, pin_names=())
        p1 = StructurePin("Source")
        arr1.add_pin(p1)
        shared.add_pin(p1)
        p2 = StructurePin("Source")
        arr2.add_pin(p2)
        shared.add_pin(p2)
        assert "shared_net" in arr1.shares_net_with(arr2)

    def test_current_mirror_flags(self):
        arr = _make_array(name="MosfetNormalArray")
        assert not arr.is_current_mirror
        assert not arr.is_part_of_current_mirror

    def test_identity(self):
        a = ArrayStructure(StructureId("X", 0))
        b = ArrayStructure(StructureId("X", 0))
        c = ArrayStructure(StructureId("X", 1))
        assert a == b and a != c and hash(a) == hash(b)
        assert ArrayStructure(StructureId("A", 0)) < ArrayStructure(StructureId("B", 0))
        r = repr(_make_array(name="MosfetDiodeArray"))
        assert "ArrayStructure" in r and "MosfetDiodeArray" in r


# ═══════════════════════════════════════════════════════════════════════
#  PairStructure
# ═══════════════════════════════════════════════════════════════════════


class TestPairStructure:
    def test_creation(self):
        c1 = _make_array(name="MosfetDiodeArray", index=1, tech=TechType.N)
        c2 = _make_array(name="MosfetNormalArray", index=2, tech=TechType.N)
        pair = _make_pair(child1=c1, child2=c2)
        assert pair.is_pair
        assert not pair.is_array
        assert pair.child1 is c1
        assert pair.child2 is c2
        assert pair.children == (c1, c2)

    def test_symmetric_flag(self):
        assert _make_pair(name="MosfetDifferentialPair", symmetric=True).symmetric
        assert not _make_pair().symmetric

    def test_get_child(self):
        pair = _make_pair()
        assert pair.get_child(1) is pair.child1
        assert pair.get_child(2) is pair.child2
        with pytest.raises(ValueError, match="1 or 2"):
            pair.get_child(3)

    def test_parent_backlink(self):
        c1 = _make_array(index=1)
        c2 = _make_array(index=2)
        pair = _make_pair(child1=c1, child2=c2)
        assert c1.has_parent
        assert pair in c1.parents
        assert pair in c2.parents

    def test_devices_and_children_recursive(self):
        d1, d2, d3 = _make_nmos("A"), _make_nmos("B"), _make_nmos("C")
        c1 = ArrayStructure(StructureId("Arr", 1), device_list=[d1, d2])
        c2 = ArrayStructure(StructureId("Arr", 2), device_list=[d3])
        pair = PairStructure(StructureId("Pair", 0), c1, c2)
        devs = pair.devices
        assert len(devs) == 3 and d1 in devs and d2 in devs and d3 in devs
        arrs = pair.array_children
        assert len(arrs) == 2 and c1 in arrs and c2 in arrs

    def test_nested_pair(self):
        """Pair of pairs — devices recurse through two levels."""
        a1 = _make_array(index=1)
        a2 = _make_array(index=2)
        a3 = _make_array(index=3)
        a4 = _make_array(index=4)
        p1 = PairStructure(StructureId("Inner", 0), a1, a2)
        p2 = PairStructure(StructureId("Inner", 1), a3, a4)
        outer = PairStructure(StructureId("Outer", 0), p1, p2)
        assert len(outer.devices) == 4
        assert len(outer.array_children) == 4
        assert p1.has_parent
        assert p2.has_parent

    def test_infer_tech_type(self):
        pp = PairStructure(StructureId("P", 0),
                           _make_array(tech=TechType.P, index=1),
                           _make_array(tech=TechType.P, index=2))
        assert pp.infer_tech_type() == TechType.P
        mixed = PairStructure(StructureId("P", 1),
                              _make_array(tech=TechType.N, index=3),
                              _make_array(tech=TechType.P, index=4))
        assert mixed.infer_tech_type() == TechType.UNDEFINED

    def test_child_pin_helpers(self):
        c1 = _make_array(index=1, pin_names=("Drain", "Gate", "Source"))
        c2 = _make_array(index=2, pin_names=("Drain", "Gate", "Source"))
        pair = PairStructure(StructureId("P", 0), c1, c2)
        assert pair.find_child1_pin("Drain") is c1.get_pin("Drain")
        assert pair.find_child2_pin("Source") is c2.get_pin("Source")

    def test_current_mirror_detection(self):
        pair = _make_pair(name="MosfetSimpleCurrentMirror")
        assert pair.is_current_mirror
        assert pair.child1.is_part_of_current_mirror
        assert pair.child2.is_part_of_current_mirror

    def test_has_common_devices(self):
        d = _make_nmos("shared")
        c1 = ArrayStructure(StructureId("A", 0), device_list=[d])
        c2 = ArrayStructure(StructureId("A", 1), device_list=[d])
        pair1 = PairStructure(StructureId("P", 0), c1, c2)
        pair2 = PairStructure(StructureId("P", 1), c1, c2)
        assert pair1.has_common_devices(pair2)

    def test_parent_chain(self):
        a1 = _make_array(index=1)
        a2 = _make_array(index=2)
        pair = _make_pair(child1=a1, child2=a2, index=0)
        assert pair in a1.topmost_parents
        assert pair.topmost_parents == [pair]  # root is its own topmost
        assert a1.has_common_parent(a2)
        a1.remove_parent(pair)
        assert not a1.has_parent

    def test_repr(self):
        pair = _make_pair(name="DiffPair", symmetric=True)
        r = repr(pair)
        assert "PairStructure" in r
        assert "DiffPair" in r
        assert "symmetric" in r


# ═══════════════════════════════════════════════════════════════════════
#  StructureCircuit (single level)
# ═══════════════════════════════════════════════════════════════════════


class TestStructureCircuit:
    def test_structure_ops(self):
        sc = StructureCircuit(2)
        assert sc.level == 2 and sc.empty and sc.num_structures == 0
        arr = _make_array(index=0)
        sc.add_structure(arr)
        assert not sc.empty and sc.num_structures == 1
        assert sc.find_structure(arr.structure_id) is arr
        assert sc.has_structure(arr.structure_id)
        with pytest.raises(KeyError):
            sc.find_structure(StructureId("X", 99))
        sc.remove_structure(arr)
        assert sc.empty

    def test_find_structures_by_name(self):
        sc = StructureCircuit(2)
        a1 = _make_array(name="MosfetNormalArray", index=0)
        a2 = _make_array(name="MosfetNormalArray", index=1)
        a3 = _make_array(name="MosfetDiodeArray", index=2)
        sc.add_structure(a1)
        sc.add_structure(a2)
        sc.add_structure(a3)
        found = sc.find_structures_by_name("MosfetNormalArray")
        assert len(found) == 2

    def test_structures_without_parents(self):
        sc = StructureCircuit(2)
        a1 = _make_array(index=1)
        a2 = _make_array(index=2)
        _pair = _make_pair(child1=a1, child2=a2)  # gives a1,a2 parents
        a3 = _make_array(index=3)  # no parent
        sc.add_structure(a1)
        sc.add_structure(a2)
        sc.add_structure(a3)
        orphans = sc.structures_without_parents
        assert len(orphans) == 1
        assert a3 in orphans

    def test_net_management(self):
        sc = StructureCircuit(2)
        net = StructureNet("n1")
        sc.add_net(net)
        assert sc.has_net("n1") and sc.find_net("n1") is net and sc.num_nets == 1
        sc.remove_net(net)
        assert not sc.has_net("n1")
        n1 = sc.find_or_create_net("auto")
        assert sc.find_or_create_net("auto") is n1  # idempotent

    def test_find_connected_structures(self):
        sc = StructureCircuit(2)
        shared = StructureNet("shared")
        arr1, arr2 = _make_array(index=0, pin_names=()), _make_array(index=1, pin_names=())
        for arr, pname in ((arr1, "Drain"), (arr2, "Gate")):
            p = StructurePin(pname)
            arr.add_pin(p)
            shared.add_pin(p)
            sc.add_structure(arr)
        sc.add_net(shared)
        assert len(sc.find_connected_structures("shared")) == 2
        assert sc.find_connected_structures("nope") == []

    def test_protocols(self):
        sc = StructureCircuit(3)
        a1, a2 = _make_array(index=0), _make_array(index=1)
        sc.add_structure(a1)
        sc.add_structure(a2)
        assert len(sc) == 2 and a1.structure_id in sc and len(list(sc)) == 2
        assert "level=3" in repr(sc)


# ═══════════════════════════════════════════════════════════════════════
#  StructureCircuits (multi-level)
# ═══════════════════════════════════════════════════════════════════════


class TestStructureCircuits:
    def _build_two_level(self) -> StructureCircuits:
        """Build a small two-level structure circuits for testing."""
        circuits = StructureCircuits()
        # Level 2: two arrays
        a1 = _make_array(name="MosfetDiodeArray", index=1, tech=TechType.N)
        a2 = _make_array(name="MosfetNormalArray", index=2, tech=TechType.N)
        circuits.add_structure(a1, level=2)
        circuits.add_structure(a2, level=2)
        # Level 3: one pair
        pair = _make_pair(
            name="MosfetSimpleCurrentMirror", index=0,
            child1=a1, child2=a2, tech=TechType.N,
        )
        circuits.add_structure(pair, level=3)
        return circuits

    def test_creation(self):
        sc = StructureCircuits()
        assert len(sc) == 0 and sc.all_structures == [] and sc.hierarchy_levels == []
        ckt = Circuit("test")
        assert StructureCircuits(circuit=ckt).circuit is ckt

    def test_add_and_query(self):
        sc = self._build_two_level()
        assert sc.hierarchy_levels == [2, 3]
        assert sc.total_structures == 3
        assert len(sc) == 3

    def test_level_management(self):
        sc = self._build_two_level()
        assert sc.get_level(2).num_structures == 2
        assert sc.has_level(2) and sc.has_level(3) and not sc.has_level(1)
        with pytest.raises(KeyError):
            sc.get_level(99)
        lc = sc.get_or_create_level(5)
        assert lc.level == 5 and sc.get_or_create_level(5) is lc

    def test_max_level(self):
        assert self._build_two_level().max_level == 3
        with pytest.raises(ValueError):
            _ = StructureCircuits().max_level

    def test_all_structures(self):
        sc = self._build_two_level()
        all_s = sc.all_structures
        assert len(all_s) == 3
        # Level 2 structures come first
        assert all_s[0].is_array
        assert all_s[1].is_array
        assert all_s[2].is_pair

    def test_find_and_top_level(self):
        sc = self._build_two_level()
        assert len(sc.find_structures_by_name("MosfetSimpleCurrentMirror")) == 1
        top = sc.top_level_structures
        assert len(top) == 1 and top[0].name == "MosfetSimpleCurrentMirror"
        assert StructureCircuits().top_level_structures == []

    def test_structures_without_parents(self):
        sc = self._build_two_level()
        orphans = sc.structures_without_parents
        # The pair has no parent; the arrays have the pair as parent
        assert len(orphans) == 1
        assert orphans[0].is_pair

    def test_find_level_of(self):
        sc = self._build_two_level()
        all_s = sc.all_structures
        arr = next(s for s in all_s if s.is_array)
        pair = next(s for s in all_s if s.is_pair)
        assert sc.find_level_of(arr) == 2 and sc.find_level_of(pair) == 3
        assert StructureCircuits().find_level_of(_make_array()) is None

    def test_protocols(self):
        sc = self._build_two_level()
        assert sc.all_structures[0].structure_id in sc
        assert StructureId("Fake", 999) not in sc
        assert len(list(sc)) == 3
        summary = sc.summary()
        assert "Level 2" in summary and "Level 3" in summary
        r = repr(sc)
        assert "L2=" in r and "L3=" in r
        # add_level directly
        lc = StructureCircuit(4)
        sc.add_level(lc)
        assert sc.has_level(4) and sc.get_level(4) is lc

    def test_three_level_hierarchy(self):
        """Build a 3-level hierarchy: arrays → pairs → pair-of-pairs."""
        sc = StructureCircuits()
        # Level 2
        a1 = _make_array(index=1, tech=TechType.N)
        a2 = _make_array(index=2, tech=TechType.N)
        a3 = _make_array(index=3, tech=TechType.N)
        a4 = _make_array(index=4, tech=TechType.N)
        for a in (a1, a2, a3, a4):
            sc.add_structure(a, 2)
        # Level 3
        p1 = PairStructure(StructureId("CM", 0), a1, a2, tech_type=TechType.N)
        p2 = PairStructure(StructureId("CM", 1), a3, a4, tech_type=TechType.N)
        sc.add_structure(p1, 3)
        sc.add_structure(p2, 3)
        # Level 4
        outer = PairStructure(StructureId("CascodeCM", 0), p1, p2, tech_type=TechType.N)
        sc.add_structure(outer, 4)

        assert sc.max_level == 4
        assert sc.total_structures == 7
        assert len(sc.top_level_structures) == 1
        assert sc.top_level_structures[0].name == "CascodeCM"
        # Only the outermost has no parent
        orphans = sc.structures_without_parents
        assert len(orphans) == 1


# ═══════════════════════════════════════════════════════════════════════
#  Integration: wiring structures through shared nets
# ═══════════════════════════════════════════════════════════════════════


class TestMissingBranches:
    """Targeted tests for previously uncovered branches."""

    def test_structure_pin_eq_not_implemented(self):
        """StructurePin.__eq__ returns NotImplemented for non-StructurePin (line 155)."""
        pin = StructurePin("Gate")
        assert pin.__eq__(42) is NotImplemented

    def test_structure_pin_hash(self):
        """StructurePin.__hash__ uses name + id(structure) (line 162)."""
        arr = _make_array()
        pin = arr.get_pin("Drain")
        assert isinstance(hash(pin), int)
        # Two pins with same name but different structures → different hash
        arr2 = _make_array(index=99)
        pin2 = arr2.get_pin("Drain")
        assert hash(pin) != hash(pin2)

    def test_structure_net_supply_property_setter(self):
        """StructureNet.supply setter stores the value (line 218)."""
        net = StructureNet("n")
        net.supply = Supply.vdd()
        assert net.supply == Supply.vdd()  # getter exercised via property

    def test_structure_net_is_vdd_without_core_net(self):
        """is_vdd() falls through to _supply.is_vdd when no core_net (line 241)."""
        assert StructureNet("v", supply=Supply.vdd()).is_vdd()
        assert not StructureNet("v", supply=Supply.gnd()).is_vdd()

    def test_find_pins_by_type_continue_branches(self):
        """Pins with no owning structure or wrong structure name are skipped (lines 290, 294)."""
        net = StructureNet("n")
        # Pin with no structure attached
        orphan = StructurePin("Gate")
        net.add_pin(orphan)   # structure is None -> continue
        # Pin with matching structure but non-matching pin_name -> line 294 continue
        arr = _make_array(name="MosfetNormalArray", index=0, pin_names=())
        p = StructurePin("Drain")
        arr.add_pin(p)
        net.add_pin(p)
        result = net.find_pins_by_type("MosfetNormalArray", "Gate")
        assert result == []
        result2 = net.find_pins_by_type("Other")
        assert result2 == []

    def test_structure_net_repr_with_supply_tag(self):
        """StructureNet repr includes supply tag when supply is set (line 308)."""
        net = StructureNet("VDD", supply=Supply.vdd())
        net.add_pin(StructurePin("x"))  # ensure len > 0
        r = repr(net)
        assert "[VDD]" in r

    def test_structure_net_eq_same_name(self):
        """StructureNet.__eq__ returns NotImplemented for non-StructureNet (line 313)."""
        n1 = StructureNet("vdd")
        n2 = StructureNet("vdd")
        assert n1 == n2
        assert not (n1 == StructureNet("gnd"))
        assert n1.__eq__(42) is NotImplemented

    def test_structure_base_repr(self):
        """Structure.__repr__ base implementation (lines 548-550)."""
        s = Structure.__new__(Structure)
        s._structure_id = StructureId("X", 0)
        s._tech_type = TechType.N
        s._pins = {}
        s._parents = []
        r = repr(s)
        assert "Structure(" in r
        assert "?" in r  # neither pair nor array

    def test_structure_circuit_nets_property(self):
        """StructureCircuit.nets returns list of registered nets (line 888)."""
        sc = StructureCircuit(1)
        n1 = StructureNet("vdd")
        n2 = StructureNet("gnd")
        sc.add_net(n1)
        sc.add_net(n2)
        nets = sc.nets
        assert set(n.name for n in nets) == {"vdd", "gnd"}

    def test_structure_base_devices_raises(self):
        """Structure.devices raises NotImplementedError (lines 548-550)."""
        # Access via ArrayStructure before device_list set
        s = Structure.__new__(Structure)
        s._structure_id = StructureId("X", 0)
        s._tech_type = TechType.N
        s._pins = {}
        s._parents = []
        with pytest.raises(NotImplementedError):
            _ = s.devices

    def test_structure_base_array_children_raises(self):
        """Structure.array_children raises NotImplementedError (lines 553-554)."""
        s = Structure.__new__(Structure)
        s._structure_id = StructureId("X", 0)
        s._tech_type = TechType.N
        s._pins = {}
        s._parents = []
        with pytest.raises(NotImplementedError):
            _ = s.array_children

    def test_structure_eq_not_implemented(self):
        """Structure.__eq__ returns NotImplemented for non-Structure (line 467 / 888)."""
        arr = _make_array()
        assert arr.__eq__(42) is NotImplemented
        pair = _make_pair()
        assert pair.__eq__(42) is NotImplemented

    def test_has_parent_and_exactly_one(self):
        """has_parent and has_exactly_one_parent properties (lines 499, 504)."""
        a1 = _make_array(index=1)
        a2 = _make_array(index=2)
        a3 = _make_array(index=3)
        pair1 = PairStructure(StructureId("P", 0), a1, a2)
        assert a1.has_parent
        assert a1.has_exactly_one_parent   # only pair1
        # Add second parent manually to test the False branch
        pair2 = PairStructure.__new__(PairStructure)
        a1._parents.append(pair2)
        assert not a1.has_exactly_one_parent

    def test_structure_circuits_circuit_setter(self):
        """StructureCircuits.circuit setter stores the Circuit (line 964)."""
        from recognition.model import StructureCircuits
        from pyckt.core.circuit import Circuit
        sc = StructureCircuits()
        c = Circuit("top")
        sc.circuit = c
        assert sc.circuit is c


class TestWiringIntegration:
    """Test full wiring scenario with core nets and structures."""

    def test_shared_source_net(self):
        """Two arrays sharing a source net — the fundamental pattern
        for differential-pair recognition."""
        # Core circuit nets
        vdd_core = _make_core_net("VDD", Supply.vdd())
        gnd_core = _make_core_net("GND", Supply.gnd())
        src_core = _make_core_net("tail")

        # Structure nets
        vdd_snet = StructureNet("VDD", core_net=vdd_core)
        gnd_snet = StructureNet("GND", core_net=gnd_core)
        src_snet = StructureNet("tail", core_net=src_core)
        d1_snet = StructureNet("out1")
        d2_snet = StructureNet("out2")
        g1_snet = StructureNet("in1")
        g2_snet = StructureNet("in2")

        # Arrays
        arr1 = ArrayStructure(
            StructureId("MosfetNormalArray", 0),
            tech_type=TechType.N,
            device_list=[_make_nmos("M1")],
        )
        arr2 = ArrayStructure(
            StructureId("MosfetNormalArray", 1),
            tech_type=TechType.N,
            device_list=[_make_nmos("M2")],
        )

        # Wire arr1
        for pname, snet in [("Drain", d1_snet), ("Gate", g1_snet), ("Source", src_snet)]:
            pin = StructurePin(pname)
            arr1.add_pin(pin)
            snet.add_pin(pin)

        # Wire arr2
        for pname, snet in [("Drain", d2_snet), ("Gate", g2_snet), ("Source", src_snet)]:
            pin = StructurePin(pname)
            arr2.add_pin(pin)
            snet.add_pin(pin)

        # Verify shared source
        assert "tail" in arr1.shares_net_with(arr2)
        assert len(src_snet.connected_structures) == 2

        # Build pair
        pair = PairStructure(
            StructureId("MosfetDifferentialPair", 0),
            arr1, arr2, symmetric=True, tech_type=TechType.N,
        )
        assert pair.infer_tech_type() == TechType.N
        assert pair.symmetric

        # Build StructureCircuits
        circuits = StructureCircuits()
        lc2 = circuits.get_or_create_level(2)
        lc2.add_structure(arr1)
        lc2.add_structure(arr2)
        for sn in (vdd_snet, gnd_snet, src_snet, d1_snet, d2_snet, g1_snet, g2_snet):
            lc2.add_net(sn)

        lc3 = circuits.get_or_create_level(3)
        lc3.add_structure(pair)

        assert circuits.total_structures == 3
        assert circuits.max_level == 3
        assert vdd_snet.is_supply()
        assert gnd_snet.is_ground()
        assert not src_snet.is_supply()

    def test_find_connected_structures_cross_level(self):
        """Structures from different levels sharing a net name
        are all discoverable via StructureCircuits."""
        circuits = StructureCircuits()
        shared = StructureNet("gate_bias")

        a1 = _make_array(index=0, pin_names=())
        p1 = StructurePin("Gate")
        a1.add_pin(p1)
        shared.add_pin(p1)

        lc2 = circuits.get_or_create_level(2)
        lc2.add_structure(a1)
        lc2.add_net(shared)

        connected = circuits.find_connected_structures("gate_bias")
        assert len(connected) == 1
        assert a1 in connected
