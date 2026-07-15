"""Tests for partitioning.net_index — the structure-net connectivity index."""

from __future__ import annotations

from core.device import Device, DeviceType, TechType
from core.net import Net, Supply
from partitioning.net_index import StructureNetIndex
from recognition.model import (
    ArrayStructure,
    StructureCircuits,
    StructureId,
    StructureNet,
    StructurePin,
)


def _array(name: str, idx: int, pins: dict[str, StructureNet],
           devs: list[str], tech: TechType = TechType.N) -> ArrayStructure:
    arr = ArrayStructure(StructureId(name, idx), tech_type=tech,
                         device_list=[Device(d, DeviceType.MOSFET, tech) for d in devs])
    for pin_name, net in pins.items():
        p = StructurePin(pin_name)
        arr.add_pin(p)
        net.add_pin(p)
    return arr


def _circuits(*arrays: ArrayStructure) -> StructureCircuits:
    sc = StructureCircuits()
    for a in arrays:
        sc.add_structure(a, 0)
    return sc


# ── unit tests ────────────────────────────────────────────────────────────


def test_connected_structures_shares_net_by_name():
    # Two arrays whose Drain pins sit on the same electrical net "n1".
    n1a = StructureNet("n1")
    n1b = StructureNet("n1")
    a = _array("MosfetNormalArray", 0, {"Drain": n1a}, ["m1"])
    b = _array("MosfetDiodeArray", 0, {"Drain": n1b}, ["m2"])
    idx = StructureNetIndex.build(_circuits(a, b))

    conn = idx.connected_structures("n1")
    assert sorted(s.name for s in conn) == ["MosfetDiodeArray", "MosfetNormalArray"]


def test_connected_via_filters_by_name_and_pin():
    n = StructureNet("g")
    a = _array("MosfetNormalArray", 0, {"Gate": StructureNet("g")}, ["m1"])
    b = _array("MosfetNormalArray", 1, {"Drain": StructureNet("g")}, ["m2"])
    idx = StructureNetIndex.build(_circuits(a, b))

    # only the array attached via its Gate pin
    via_gate = idx.connected_via("g", "MosfetNormalArray", "Gate")
    assert [s.devices[0].name for s in via_gate] == ["m1"]
    via_drain = idx.connected_via("g", "MosfetNormalArray", "Drain")
    assert [s.devices[0].name for s in via_drain] == ["m2"]


def test_net_name_lookup_and_missing_pin():
    a = _array("MosfetNormalArray", 0, {"Drain": StructureNet("d")}, ["m1"])
    idx = StructureNetIndex.build(_circuits(a))
    assert idx.net_name(a, "Drain") == "d"
    assert idx.net_name(a, "Source") is None  # pin absent


def test_supply_classification():
    vdd = StructureNet("vdd!", supply=Supply.vdd(5.0))
    gnd = StructureNet("gnd!", supply=Supply.gnd(0.0))
    sig = StructureNet("out")
    a = _array("MosfetNormalArray", 0,
               {"Source": vdd, "Drain": sig, "Bulk": gnd}, ["m1"])
    idx = StructureNetIndex.build(_circuits(a))
    assert idx.is_supply("vdd!") and idx.is_vdd("vdd!")
    assert idx.is_supply("gnd!") and idx.is_ground("gnd!")
    assert not idx.is_supply("out")
    assert not idx.is_supply("nonexistent")


def test_distinct_structures_when_two_pins_on_same_net():
    # A single structure with two pins on the same net appears once.
    net_a = StructureNet("x")
    net_b = StructureNet("x")
    a = _array("MosfetNormalArray", 0, {"Drain": net_a, "Gate": net_b}, ["m1"])
    idx = StructureNetIndex.build(_circuits(a))
    assert len(idx.connected_structures("x")) == 1
    assert len(idx) == 1  # one distinct net name


# ── integration test on the real fixture ───────────────────────────────────


def test_index_on_real_cascode_ota(inputs_dir):
    from ckt_io.device_types_parser import load_device_types
    from ckt_io.hspice_mapping import HSpiceMapping
    from ckt_io.hspice_parser import HSpiceParser
    from ckt_io.supply_nets_parser import SupplyNetConfig
    from recognition.library import Library
    from recognition.recognizer import StructureRecognizer

    base = inputs_dir / "Partitioning"
    dt = load_device_types(str(base / "deviceTypes.xcat"))
    mp = HSpiceMapping.from_file(str(base / "HSpiceMapping.xcat"))
    sn = SupplyNetConfig.from_file(str(base / "supplyNets.xcat"))
    ckt = HSpiceParser(mp, sn, dt).parse(str(base / "cascodedSymmetricalCMOSOTA.hspice"))
    sc = StructureRecognizer(Library.from_directory()).recognize(ckt)

    idx = StructureNetIndex.build(sc)
    # recognition reports 0 nets; the index recovers them
    assert len(idx) > 0
    assert idx.is_supply("vdd!") and idx.is_supply("gnd!")
    assert not idx.is_supply("out")

    # the input differential pair's drains must reach load structures
    dp = [s for s in sc.structures_without_parents
          if s.name == "MosfetDifferentialPair"][0]
    reached = set()
    for arr in dp.array_children:
        dn = idx.net_name(arr, "Drain")
        reached.update(s.name for s in idx.connected_structures(dn))
    assert "MosfetSimpleCurrentMirror" in reached or "MosfetDiodeArray" in reached
