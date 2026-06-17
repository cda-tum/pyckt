"""Tests for pyckt.core — covers the 10 cases listed in core/README.md."""

import pytest

import argparse

from pyckt.core import (
    Circuit,
    Device,
    DeviceType,
    TechType,
    PinType,
    Terminal,
    Net,
    NetId,
    Supply,
    SupplyType,
    Instance,
    CellTripleId,
    Port,
    PortType,
    DuplicateDeviceError,
    DuplicateNetError,
    DuplicatePortError,
    UnknownDeviceError,
    UnknownNetError,
    UnknownPortError,
    UnknownParameterError,
    InvalidPinError,
    ValidationError,
)
from pyckt.core.common import AbstractAnalysis


# ── helpers ───────────────────────────────────────────────────────────────

def _make_nmos(name: str = "M1") -> Device:
    return Device(name, DeviceType.MOSFET, TechType.N)


def _wire(circuit: Circuit, device: Device, pin: PinType, net_name: str) -> Terminal:
    """Create a terminal, register it on device, net, and circuit."""
    net = circuit.find_or_create_net(net_name)
    t = Terminal(device, pin, net)
    device.add_terminal(t)
    net.add_terminal(t)
    circuit.add_terminal(t)
    return t


# ── 1. Wiring round-trip ─────────────────────────────────────────────────

def test_wiring_round_trip():
    c = Circuit("test")
    dev = _make_nmos()
    c.add_device(dev)

    _wire(c, dev, PinType.DRAIN, "OUT")
    _wire(c, dev, PinType.GATE, "GATE")
    _wire(c, dev, PinType.SOURCE, "GND")

    assert c.has_device("M1")
    assert c.find_device("M1") is dev
    assert dev.get_net(PinType.DRAIN) is c.find_net("OUT")
    assert dev.get_net(PinType.GATE) is c.find_net("GATE")
    assert dev.get_net(PinType.SOURCE) is c.find_net("GND")
    assert len(c.terminals) == 3
    assert c.has_terminals()


# ── 2. Duplicate device ──────────────────────────────────────────────────

def test_add_device_duplicate_raises():
    c = Circuit("x")
    c.add_device(_make_nmos("M1"))
    with pytest.raises(DuplicateDeviceError, match="M1"):
        c.add_device(Device("M1", DeviceType.MOSFET, TechType.P))


# ── 3. Duplicate net ─────────────────────────────────────────────────────

def test_add_net_duplicate_raises():
    c = Circuit("x")
    c.add_net(Net(NetId("VDD")))
    with pytest.raises(DuplicateNetError, match="VDD"):
        c.add_net(Net(NetId("VDD")))


# ── 4. Unknown device / net ──────────────────────────────────────────────

def test_find_device_unknown_raises():
    c = Circuit("x")
    with pytest.raises(UnknownDeviceError, match="NOPE"):
        c.find_device("NOPE")


def test_find_net_unknown_raises():
    c = Circuit("x")
    with pytest.raises(UnknownNetError, match="NOPE"):
        c.find_net("NOPE")


# ── 5. find_or_create_net idempotent ─────────────────────────────────────

def test_find_or_create_net_idempotent():
    c = Circuit("x")
    n1 = c.find_or_create_net("vdd")
    n2 = c.find_or_create_net("vdd")
    assert n1 is n2


# ── 6. Invalid pin ───────────────────────────────────────────────────────

def test_get_terminal_missing_pin_raises():
    dev = _make_nmos()
    with pytest.raises(InvalidPinError, match="BULK"):
        dev.get_terminal(PinType.BULK)


# ── 7. Device.get_net after wiring ───────────────────────────────────────

def test_get_net_returns_expected_net():
    c = Circuit("x")
    dev = _make_nmos()
    c.add_device(dev)
    _wire(c, dev, PinType.DRAIN, "OUT")

    assert dev.get_net(PinType.DRAIN).name == "OUT"


# ── 8. Supply flag queries ───────────────────────────────────────────────

def test_supply_vdd():
    s = Supply.vdd(level=1)
    assert s.is_vdd
    assert s.is_supply
    assert not s.is_gnd


def test_supply_gnd():
    s = Supply.gnd(level=2)
    assert s.is_gnd
    assert s.is_supply
    assert not s.is_vdd


def test_supply_none():
    s = Supply.no_supply()
    assert not s.is_supply
    assert not s.is_vdd
    assert not s.is_gnd


def test_supply_type_enum_direct_construction():
    """Build Supply via SupplyType enum directly (no factory) and verify."""
    vdd = Supply(supply_type=SupplyType.VDD, level=3)
    gnd = Supply(supply_type=SupplyType.GND, level=0)
    none = Supply(supply_type=SupplyType.NO_SUPPLY)

    assert vdd.supply_type is SupplyType.VDD
    assert vdd.level == 3
    assert vdd.is_vdd

    assert gnd.supply_type is SupplyType.GND
    assert gnd.is_gnd

    assert none.supply_type is SupplyType.NO_SUPPLY
    assert not none.is_supply

    # Enum values match the C++ strings
    assert SupplyType.VDD.value == "vdd"
    assert SupplyType.GND.value == "gnd"
    assert SupplyType.NO_SUPPLY.value == "none"


def test_net_supply_flags():
    c = Circuit("x")
    vdd = c.find_or_create_net("VDD")
    vdd.supply = Supply.vdd()
    gnd = c.find_or_create_net("GND")
    gnd.supply = Supply.gnd()
    sig = c.find_or_create_net("SIG")

    assert vdd.is_vdd()
    assert vdd.is_supply()
    assert not vdd.is_ground()

    assert gnd.is_ground()
    assert gnd.is_supply()
    assert not gnd.is_vdd()

    assert not sig.is_supply()
    assert not sig.is_power()

    assert vdd in c.get_supply_nets()
    assert gnd in c.get_ground_nets()
    assert sig not in c.get_supply_nets()
    assert sig not in c.get_ground_nets()


# ── 9. Net.get_terminals_by_type ─────────────────────────────────────────

def test_get_terminals_by_type():
    c = Circuit("x")
    m1 = _make_nmos("M1")
    m2 = _make_nmos("M2")
    c.add_device(m1)
    c.add_device(m2)

    net = c.find_or_create_net("SHARED")
    t1 = Terminal(m1, PinType.DRAIN, net)
    t2 = Terminal(m2, PinType.GATE, net)
    m1.add_terminal(t1)
    m2.add_terminal(t2)
    net.add_terminal(t1)
    net.add_terminal(t2)

    drains = net.get_terminals_by_type(PinType.DRAIN)
    gates = net.get_terminals_by_type(PinType.GATE)
    sources = net.get_terminals_by_type(PinType.SOURCE)

    assert len(drains) == 1 and drains[0] is t1
    assert len(gates) == 1 and gates[0] is t2
    assert len(sources) == 0
    assert net.has_terminal_type(PinType.DRAIN)
    assert net.has_terminal_type(PinType.GATE)
    assert not net.has_terminal_type(PinType.SOURCE)


# ── 10. Instance.connect rejects empty strings ───────────────────────────

def test_instance_connect_rejects_empty_pin():
    inst = Instance("XI0", CellTripleId("lib", "cell", "schematic"))
    with pytest.raises(ValidationError):
        inst.connect("", "NET1")


def test_instance_connect_rejects_empty_net():
    inst = Instance("XI0", CellTripleId("lib", "cell", "schematic"))
    with pytest.raises(ValidationError):
        inst.connect("A", "")


def test_instance_connect_rejects_whitespace_pin():
    inst = Instance("XI0", CellTripleId("lib", "cell", "schematic"))
    with pytest.raises(ValidationError):
        inst.connect("  ", "NET1")


def test_instance_connect_rejects_whitespace_net():
    inst = Instance("XI0", CellTripleId("lib", "cell", "schematic"))
    with pytest.raises(ValidationError):
        inst.connect("A", "   ")

# ── bonus: mosfets / capacitors filters ──────────────────────────────────

def test_mosfets_and_capacitors_filters():
    c = Circuit("x")
    c.add_device(Device("M1", DeviceType.MOSFET, TechType.N))
    c.add_device(Device("M2", DeviceType.MOSFET, TechType.P))
    c.add_device(Device("C1", DeviceType.CAPACITOR, TechType.UNDEFINED))

    assert len(c.mosfets) == 2
    assert len(c.capacitors) == 1
    assert len(c.devices) == 3


# ── bonus: has_net / has_instance / has_device ───────────────────────────

def test_has_queries():
    c = Circuit("x")
    c.add_device(_make_nmos("M1"))
    c.find_or_create_net("N1")
    inst = Instance("XI0", CellTripleId("lib", "inv", "schematic"))
    c.add_instance(inst)

    assert c.has_device("M1")
    assert not c.has_device("M99")
    assert c.has_net("N1")
    assert not c.has_net("N99")
    assert c.has_instance("XI0")
    assert not c.has_instance("XI99")
    assert c.has_instances()

    # find_instance: found and not-found
    assert c.find_instance("XI0") is inst
    assert c.find_instance("XI99") is None

    # instances property returns list of all instances
    assert c.instances == [inst]


# ── bonus: Device convenience properties ─────────────────────────────────

def test_device_type_flags():
    nmos = Device("N1", DeviceType.MOSFET, TechType.N)
    pmos = Device("P1", DeviceType.MOSFET, TechType.P)
    cap = Device("C1", DeviceType.CAPACITOR, TechType.UNDEFINED)

    assert nmos.is_mosfet and nmos.is_nmos and not nmos.is_pmos
    assert pmos.is_mosfet and pmos.is_pmos and not pmos.is_nmos
    assert not cap.is_mosfet


def test_case_insensitive_enum_from_text():
    """Enum helper resolves name/value regardless of case and validates errors."""
    assert DeviceType.from_text("mosfet") is DeviceType.MOSFET
    assert DeviceType.from_text("MOSFET") is DeviceType.MOSFET
    assert DeviceType.from_text("Mosfet") is DeviceType.MOSFET

    assert TechType.from_text("n") is TechType.N
    assert TechType.from_text("N") is TechType.N
    assert TechType.from_text("undefined") is TechType.UNDEFINED

    assert PinType.from_text("drain") is PinType.DRAIN
    assert PinType.from_text("DRAIN") is PinType.DRAIN
    assert PinType.from_text("Drain") is PinType.DRAIN

    with pytest.raises(KeyError, match="Empty DeviceType"):
        DeviceType.from_text("   ")

    with pytest.raises(KeyError, match="Unknown PinType"):
        PinType.from_text("not_a_real_pin")


# ── 11. Port model ───────────────────────────────────────────────────────

def test_add_port_and_find():
    c = Circuit("x")
    net = c.find_or_create_net("OUT")
    p = Port("OUT", PortType.OUTPUT, net)
    c.add_port(p)

    assert c.has_port("OUT")
    assert c.find_port("OUT") is p
    assert p.is_output
    assert not p.is_input
    assert not p.is_inout
    assert len(c.ports) == 1
    assert c.has_ports()


def test_port_types():
    inp = Port("IN", PortType.INPUT)
    out = Port("OUT", PortType.OUTPUT)
    io = Port("IO", PortType.INOUT)

    assert inp.is_input and not inp.is_output and not inp.is_inout
    assert out.is_output and not out.is_input
    assert io.is_inout and not io.is_input and not io.is_output


def test_add_port_duplicate_raises():
    c = Circuit("x")
    c.add_port(Port("A", PortType.INPUT))
    with pytest.raises(DuplicatePortError, match="A"):
        c.add_port(Port("A", PortType.OUTPUT))


def test_find_port_unknown_raises():
    c = Circuit("x")
    with pytest.raises(UnknownPortError, match="NOPE"):
        c.find_port("NOPE")


def test_port_repr() -> None:
    """Port.__repr__ returns the expected string (port.py line 44)."""
    p = Port("CLK", PortType.INPUT)
    assert repr(p) == "Port('CLK', INPUT)"


# ── 12. Device parameters ────────────────────────────────────────────────

def test_device_set_get_parameter():
    dev = _make_nmos()
    dev.set_parameter("w", 1e-6)
    dev.set_parameter("l", 180e-9)

    assert dev.get_parameter("w") == 1e-6
    assert dev.get_parameter("l") == 180e-9
    assert len(dev.parameters) == 2


def test_device_get_parameter_unknown_raises():
    dev = _make_nmos()
    with pytest.raises(UnknownParameterError, match="vth"):
        dev.get_parameter("vth")


def test_device_parameter_overwrite():
    dev = _make_nmos()
    dev.set_parameter("w", 1e-6)
    dev.set_parameter("w", 2e-6)
    assert dev.get_parameter("w") == 2e-6


# ── 13. Instance parameters ──────────────────────────────────────────────

def test_abstract_analysis_raises_not_implemented() -> None:
    """AbstractAnalysis stores args and raises NotImplementedError on each abstract method."""
    args = argparse.Namespace(foo="bar")

    class _Concrete(AbstractAnalysis):
        pass

    analysis = _Concrete(args)
    assert analysis.args is args

    with pytest.raises(NotImplementedError, match="initialize"):
        analysis.initialize()
    with pytest.raises(NotImplementedError, match="compute"):
        analysis.compute()
    with pytest.raises(NotImplementedError, match="write"):
        analysis.write()


def test_instance_set_get_parameter():
    inst = Instance("XI0", CellTripleId("lib", "cell", "schematic"))
    inst.set_param("w", 1e-6)
    inst.set_param("nf", 2)

    assert inst.get_parameter("w") == 1e-6
    assert inst.get_parameter("nf") == 2


def test_instance_get_parameter_unknown_raises():
    inst = Instance("XI0", CellTripleId("lib", "cell", "schematic"))
    with pytest.raises(UnknownParameterError, match="m"):
        inst.get_parameter("m")


def test_cell_triple_id_qualified_name() -> None:
    """qualified_name() returns library/cell/view (instance.py line 13)."""
    cid = CellTripleId("mylib", "inv", "schematic")
    assert cid.qualified_name() == "mylib/inv/schematic"


def test_instance_connect_success() -> None:
    """connect() with valid args stores the connection (instance.py line 27)."""
    inst = Instance("XI0", CellTripleId("lib", "cell", "schematic"))
    inst.connect("A", "NET1")
    assert inst.connections["A"] == "NET1"


# ── 14. Net merge operations ─────────────────────────────────────────────

def test_merge_nets_terminals_reassigned():
    c = Circuit("x")
    m1 = _make_nmos("M1")
    m2 = _make_nmos("M2")
    c.add_device(m1)
    c.add_device(m2)

    _wire(c, m1, PinType.DRAIN, "NET_A")
    _wire(c, m2, PinType.DRAIN, "NET_B")

    assert c.has_net("NET_A")
    assert c.has_net("NET_B")

    target = c.merge_nets("NET_A", "NET_B")

    assert target.name == "NET_A"
    # NET_B is removed
    assert not c.has_net("NET_B")
    # target net now has both terminals
    assert len(target.terminals) == 2
    # M2's drain terminal now points to NET_A
    assert m2.get_net(PinType.DRAIN) is target


def test_merge_nets_supply_propagation():
    c = Circuit("x")
    n1 = c.find_or_create_net("A")
    n2 = c.find_or_create_net("B")
    n2.supply = Supply.vdd(level=1)

    target = c.merge_nets("A", "B")

    assert target.is_vdd()
    assert target.supply.level == 1


def test_merge_nets_same_net_noop():
    c = Circuit("x")
    _wire(c, _make_nmos(), PinType.DRAIN, "NET")
    c.add_device(c.find_device("M1")  if False else _make_nmos("M1"))
    # Simpler: just create a net and merge with itself
    c2 = Circuit("y")
    c2.find_or_create_net("X")
    result = c2.merge_nets("X", "X")
    assert result.name == "X"
    assert c2.has_net("X")


def test_merge_nets_source_unknown_raises():
    c = Circuit("x")
    c.find_or_create_net("A")
    with pytest.raises(UnknownNetError, match="GONE"):
        c.merge_nets("A", "GONE")


def test_net_id_property() -> None:
    """net_id property returns the underlying NetId (net.py line 99)."""
    nid = NetId("VDD")
    net = Net(nid)
    assert net.net_id is nid
    assert net.net_id.name == "VDD"


def test_net_clear_terminals() -> None:
    """clear_terminals() empties the terminal list (net.py line 141)."""
    c = Circuit("x")
    m = _make_nmos("M1")
    c.add_device(m)
    _wire(c, m, PinType.DRAIN, "N1")
    net = c.find_or_create_net("N1")
    assert net.has_terminals()
    net.clear_terminals()
    assert not net.has_terminals()
