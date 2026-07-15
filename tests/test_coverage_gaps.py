"""Targeted tests closing measured coverage gaps in otherwise-covered modules.

Each test here exists to exercise a specific branch or public entry point that
the broader suite happened not to reach — defensive ``continue``/``return``
paths, rarely-called public helpers (``write``/``to_string``), and the sizing
topology resolver's None/empty and cascode branches.  Grouped by module.
"""
from __future__ import annotations

import types
from pathlib import Path

import pytest

from core import (
    Circuit,
    Device,
    DeviceType,
    Net,
    NetId,
    PinType,
    Supply,
    SupplyType,
    TechType,
    Terminal,
)

# ── shared builders ─────────────────────────────────────────────────────────


def _mos(name: str, tech: TechType = TechType.N) -> Device:
    return Device(name, DeviceType.MOSFET, tech)


def _net(name: str, supply: SupplyType = SupplyType.NO_SUPPLY) -> Net:
    n = Net(NetId(name))
    n.supply = Supply(supply)
    return n


def _wire(ckt: Circuit, dev: Device, net: Net, pin: PinType) -> None:
    t = Terminal(dev, pin, net)
    dev.add_terminal(t)
    net.add_terminal(t)
    ckt.add_terminal(t)


class _FakePart:
    def __init__(self, devices):
        self.devices = list(devices)


class _FakePartition:
    """Duck-typed partition exposing only ``transconductance_parts``."""

    def __init__(self, first_devices=()):
        self._first = list(first_devices)

    def transconductance_parts(self, stage):
        from partitioning.result import StageType

        if stage == StageType.FIRST and self._first:
            return [_FakePart(self._first)]
        return []


# ═══════════════════════════════════════════════════════════════════════════
#  sizing/topology.py — input-pair / output-node / cascode-branch resolution
# ═══════════════════════════════════════════════════════════════════════════


def _cascode_circuit():
    """NMOS cascode (mcasc on internal ``mid`` over mbot) feeding ``out``.

    Also carries two malformed MOSFETs — one with no SOURCE terminal, one with
    no DRAIN terminal — to exercise the resolver's defensive ``except`` paths.
    """
    ckt = Circuit(name="casc")
    vdd, gnd = _net("vdd!", SupplyType.VDD), _net("gnd!", SupplyType.GND)
    out, mid, ing = _net("out"), _net("mid"), _net("in")
    for n in (vdd, gnd, out, mid, ing):
        ckt.add_net(n)

    mcasc, mbot = _mos("mcasc"), _mos("mbot")
    ckt.add_device(mcasc)
    ckt.add_device(mbot)
    _wire(ckt, mcasc, out, PinType.DRAIN)
    _wire(ckt, mcasc, ing, PinType.GATE)
    _wire(ckt, mcasc, mid, PinType.SOURCE)
    _wire(ckt, mbot, mid, PinType.DRAIN)
    _wire(ckt, mbot, ing, PinType.GATE)
    _wire(ckt, mbot, gnd, PinType.SOURCE)

    # drain on out but no source terminal → output-branch SOURCE lookup raises
    mnosrc = _mos("mnosrc")
    ckt.add_device(mnosrc)
    _wire(ckt, mnosrc, out, PinType.DRAIN)
    _wire(ckt, mnosrc, ing, PinType.GATE)

    # gate only (no drain) → drain lookups raise in both the outer and inner scan
    mnodrain = _mos("mnodrain")
    ckt.add_device(mnodrain)
    _wire(ckt, mnodrain, ing, PinType.GATE)

    # a second cascode over a dangling internal net with no bottom driver, so
    # the inner bottom-scan runs to completion (and trips over mnodrain's
    # missing drain) without finding a match
    mid2 = _net("mid2")
    ckt.add_net(mid2)
    mcasc2 = _mos("mcasc2")
    ckt.add_device(mcasc2)
    _wire(ckt, mcasc2, out, PinType.DRAIN)
    _wire(ckt, mcasc2, ing, PinType.GATE)
    _wire(ckt, mcasc2, mid2, PinType.SOURCE)
    return ckt, mcasc, mbot


def test_output_node_devices_none_and_empty_inputs():
    from sizing.topology import output_node_devices

    ckt, mcasc, _ = _cascode_circuit()
    assert output_node_devices(None, "out") == []
    assert output_node_devices(ckt, None) == []
    # names filter excludes every candidate (line: names continue)
    assert output_node_devices(ckt, "out", known_names={"nobody"}) == []
    # the well-formed cascode device is found; the no-drain one is skipped
    found = {d.name for d in output_node_devices(ckt, "out")}
    assert "mcasc" in found and "mnodrain" not in found


def test_output_branches_none_and_cascode_and_defensive():
    from sizing.topology import output_branches

    assert output_branches(None, "out") == []

    ckt, mcasc, mbot = _cascode_circuit()
    branches = output_branches(ckt, "out")
    pairs = {c.name: (b.name if b else None) for c, b in branches}
    # cascode device pairs with its bottom device across the internal net
    assert pairs["mcasc"] == "mbot"
    # the no-source output device appends with no bottom (SOURCE lookup raised)
    assert pairs["mnosrc"] is None

    # names filter inside the inner bottom scan (a candidate excluded by name)
    named = output_branches(ckt, "out", known_names={"mcasc", "mnosrc"})
    assert {c.name for c, _ in named} == {"mcasc", "mnosrc"}


def test_first_stage_pieces_none_and_empty_and_bad_device():
    from sizing.topology import first_stage_pieces

    ckt, mcasc, mbot = _cascode_circuit()
    assert first_stage_pieces(None, _FakePartition()) is None
    # empty first stage → None
    assert first_stage_pieces(ckt, _FakePartition()) is None
    # first device present but its topology doesn't match a full first stage
    partition = _FakePartition([mcasc])
    assert first_stage_pieces(ckt, partition, output_net="out") is None


def _two_stage_circuit():
    """Input pair drain on ``fsout``; a real second-stage device at ``out``.

    Includes a cascode climb off ``fsout`` (grows the first-stage closure) and
    a source-on-``fsout`` device with no drain (exercises the net() except).
    """
    ckt = Circuit(name="two_stage")
    vdd, gnd = _net("vdd!", SupplyType.VDD), _net("gnd!", SupplyType.GND)
    out, fsout, casc_int, tail, inp = (
        _net("out"), _net("fsout"), _net("casc_int"), _net("tail"), _net("inp"),
    )
    for n in (vdd, gnd, out, fsout, casc_int, tail, inp):
        ckt.add_net(n)

    m_in = _mos("m_in")               # input device: drain on first-stage output
    m2 = _mos("m2", TechType.P)       # second gain stage: gate on fsout → out
    m_climb = _mos("m_climb")         # cascode climb off fsout
    m_nodrain = _mos("m_nodrain")     # source on fsout, no drain → net() except
    for d in (m_in, m2, m_climb, m_nodrain):
        ckt.add_device(d)

    _wire(ckt, m_in, fsout, PinType.DRAIN)
    _wire(ckt, m_in, inp, PinType.GATE)
    _wire(ckt, m_in, tail, PinType.SOURCE)

    _wire(ckt, m2, out, PinType.DRAIN)
    _wire(ckt, m2, fsout, PinType.GATE)
    _wire(ckt, m2, vdd, PinType.SOURCE)

    _wire(ckt, m_climb, casc_int, PinType.DRAIN)
    _wire(ckt, m_climb, vdd, PinType.GATE)
    _wire(ckt, m_climb, fsout, PinType.SOURCE)

    _wire(ckt, m_nodrain, fsout, PinType.SOURCE)
    _wire(ckt, m_nodrain, vdd, PinType.GATE)
    return ckt, m_in, m2


def test_second_stage_pieces_none_empty_and_detects_stage():
    from sizing.topology import second_stage_pieces

    ckt, m_in, m2 = _two_stage_circuit()
    # None circuit / no output net
    assert second_stage_pieces(None, _FakePartition(), "out") is None
    assert second_stage_pieces(ckt, _FakePartition([m_in]), None) is None
    # empty first stage → None
    assert second_stage_pieces(ckt, _FakePartition(), "out") is None

    # real second stage: m2's gate sits on the (non-diode) first-stage output
    result = second_stage_pieces(ckt, _FakePartition([m_in]), "out")
    assert result is not None
    dev, inter = result
    assert dev.name == "m2" and inter == "fsout"


# ═══════════════════════════════════════════════════════════════════════════
#  sizing/writer.py — AcstSizingXMLWriter.write / to_string
# ═══════════════════════════════════════════════════════════════════════════


def _sizing_result():
    from sizing.result import DeviceSizing, ExpectedPerformance, SizingResult

    return SizingResult(
        devices={
            "m0": DeviceSizing("m0", width=10, length=2, current=50_000,
                               vgs=800, vds=700, vov=400, gm=2e6, gds=1e5, area=20),
        },
        performance=ExpectedPerformance(
            gain_db=81.2, transit_freq_mhz=2.75, slew_rate=3.5, power_mw=0.5,
            total_area_um2=25.0, phase_margin_deg=60.0, vout_min_v=1.0, vout_max_v=3.0),
        solver_status="optimal",
        iterations=7,
    )


def test_acst_sizing_writer_write_and_to_string(tmp_path: Path):
    import xml.etree.ElementTree as ET

    from sizing.writer import AcstSizingXMLWriter

    writer = AcstSizingXMLWriter(_sizing_result())
    text = writer.to_string()
    assert "acst_results" in text and "automatic_sizing-results" in text

    out = tmp_path / "sized.xml"
    writer.write(out)
    assert ET.parse(out).getroot().tag == "acst_results"


# ═══════════════════════════════════════════════════════════════════════════
#  ckt_io/acst_xml.py — unit fallback + unconnected-pin net fallback
# ═══════════════════════════════════════════════════════════════════════════


def test_acst_unit_passthrough_for_unknown_unit():
    from ckt_io.acst_xml import acst_unit

    # a unit with no acst spelling is returned unchanged
    assert acst_unit("__no_such_unit__") == "__no_such_unit__"


def test_write_structure_uses_question_mark_for_unconnected_pin():
    import xml.etree.ElementTree as ET

    from ckt_io.acst_xml import write_structure
    from recognition.model import ArrayStructure, StructureId, StructurePin

    arr = ArrayStructure(
        StructureId("MosfetNormalArray", 0), tech_type=TechType.N,
        device_list=[Device("m1", DeviceType.MOSFET, TechType.N)],
    )
    pin = StructurePin("Drain")        # added but never wired to a net
    arr.add_pin(pin)

    parent = ET.Element("root")
    write_structure(parent, arr)
    emitted = parent.find("structure").find("pins").find("pin")
    assert emitted.get("net") == "?"


# ═══════════════════════════════════════════════════════════════════════════
#  partitioning/net_index.py — unconnected pin, connections, net_names, repr
# ═══════════════════════════════════════════════════════════════════════════


def _array(name, idx, pins, devs, tech=TechType.N):
    from recognition.model import ArrayStructure, StructureId, StructurePin

    arr = ArrayStructure(StructureId(name, idx), tech_type=tech,
                         device_list=[Device(d, DeviceType.MOSFET, tech) for d in devs])
    for pin_name, net in pins.items():
        p = StructurePin(pin_name)
        arr.add_pin(p)
        if net is not None:
            net.add_pin(p)
    return arr


def test_net_index_skips_unconnected_pin_and_exposes_introspection():
    from partitioning.net_index import StructureNetIndex
    from recognition.model import StructureCircuits, StructureNet

    d = StructureNet("d")
    # "Gate" pin intentionally left unwired (net=None) → skipped in the index
    a = _array("MosfetNormalArray", 0, {"Drain": d, "Gate": None}, ["m1"])
    sc = StructureCircuits()
    sc.add_structure(a, 0)

    idx = StructureNetIndex.build(sc)
    assert idx.net_names == ["d"]                       # only the wired net
    assert [c.pin_name for c in idx.connections("d")] == ["Drain"]
    assert idx.connections("missing") == []
    assert "StructureNetIndex(1 nets)" == repr(idx)


# ═══════════════════════════════════════════════════════════════════════════
#  partitioning/acst_parts.py — repr, undefined parts, empty-lookup accessors
# ═══════════════════════════════════════════════════════════════════════════


def test_acst_parts_repr_and_result_accessors():
    from partitioning.acst_parts import (
        AcstPartitionResult,
        TransconductancePart,
        UndefinedPart,
    )

    part = TransconductancePart()
    assert "TransconductancePart" in repr(part)          # Part.__repr__

    result = AcstPartitionResult()
    # empty result: no first stage, nothing classified/looked up
    assert result.has_first_stage() is False
    assert result.get_first_stage() is None

    arr = _array("MosfetNormalArray", 0, {}, ["m1"])
    # structure with no registered leaves → not classified, no part
    assert result.get_part(arr) is None

    undef = UndefinedPart()
    undef.add_main_structure(arr)
    result.add_undefined_part(undef)
    assert undef in result.undefined_parts


def test_acst_parts_structure_already_classified_false_without_leaves():
    from partitioning.acst_parts import AcstPartitionResult

    # a structure with no array leaves reports "not classified"
    result = AcstPartitionResult()
    empty = types.SimpleNamespace(array_children=[])
    assert result.structure_already_classified(empty) is False


# ═══════════════════════════════════════════════════════════════════════════
#  partitioning/writer.py — AcstPartitionXMLWriter write / to_string / undefined
# ═══════════════════════════════════════════════════════════════════════════


def test_acst_partition_writer_write_to_string_and_undefined(tmp_path: Path):
    import xml.etree.ElementTree as ET

    from partitioning.acst_parts import AcstPartitionResult, UndefinedPart
    from partitioning.writer import AcstPartitionXMLWriter

    result = AcstPartitionResult()
    undef = UndefinedPart()
    undef.add_main_structure(_array("MosfetNormalArray", 0, {}, ["m9"]))
    result.add_undefined_part(undef)

    writer = AcstPartitionXMLWriter(result)
    text = writer.to_string()
    assert "circuit_partitioning_results" in text
    assert "undefinedPart" in text                       # _emit_part reached

    out = tmp_path / "part.xml"
    writer.write(out)
    assert ET.parse(out).getroot().tag == "acst_results"


# ═══════════════════════════════════════════════════════════════════════════
#  synthesis/analysis.py + converter.py — spec-without-Specifications, no caps
# ═══════════════════════════════════════════════════════════════════════════


def test_parse_operating_parameters_returns_none_without_specifications(tmp_path: Path):
    from synthesis.analysis import SynthesisAnalysis

    spec = tmp_path / "spec.xml"
    spec.write_text("<CircuitInformation></CircuitInformation>")   # no <Specifications>
    assert SynthesisAnalysis._parse_operating_parameters(str(spec)) is None


def test_converter_add_load_capacitors_noop_without_source_nmos():
    from core.circuit import Circuit as CoreCircuit
    from synthesis.converter import TopologyConverter

    conv = TopologyConverter(complete_bias=True)
    ckt = CoreCircuit(name="no_minus")
    ckt.find_or_create_net("out")            # no "source_nmos" net present
    before = len(list(ckt.devices))
    conv._add_load_capacitors(ckt)           # returns early, adds nothing
    assert len(list(ckt.devices)) == before


class _MiniLeaf:
    def __init__(self, techtype, drain, gate, source):
        self.techtype, self.drain, self.gate, self.source = techtype, drain, gate, source


class _MiniTopo:
    """Minimal already-flat topogen-circuit stand-in for TopologyConverter."""

    def __init__(self, name, instances):
        self.name, self.instances = name, instances

    def flatten(self):  # already flat
        pass


def test_converter_skips_unconnected_transistor_pin():
    from synthesis.converter import TopologyConverter

    # the gate is unconnected (None) — the converter skips that pin gracefully
    leaf = _MiniLeaf(techtype="n", drain="d1", gate=None, source="s1")
    core = TopologyConverter(complete_bias=False).convert(_MiniTopo("mini", [leaf]))

    dev = next(iter(core.devices))
    pins = {t.pin_type for t in dev.terminals.values()}
    assert PinType.GATE not in pins
    assert PinType.DRAIN in pins and PinType.SOURCE in pins


# ═══════════════════════════════════════════════════════════════════════════
#  partitioning/acst_partitioner.py — run a diverse op-amp corpus end-to-end
#
#  The existing partitioning tests exercise a single cascoded-symmetric OTA, so
#  the acst partitioner's many classification branches (telescopic / folded-
#  cascode first stages, second-stage gm typing, mirror-vs-gain output branches)
#  stay uncovered.  The SynthesisSmallLibrary ships 15 structurally different
#  op-amps with full parsing config — running the recognise → partition pipeline
#  over all of them reaches those branches.  Input/output roles come from each
#  ``.MACRO`` port line (net inference is exercised separately and cannot handle
#  these fixtures' 'm'-prefixed inline-value load capacitors).
# ═══════════════════════════════════════════════════════════════════════════


_OPAMP_NAMES = [f"OpAmp{i}" for i in range(1, 16)]


def _params_from_macro(hspice_path: Path):
    """Build a CircuitParameter from a fixture's ``.MACRO`` port declaration."""
    import re

    from ckt_io.circuit_info_parser import CircuitParameter

    ports: list[str] = []
    for line in hspice_path.read_text().splitlines():
        m = re.match(r"\.MACRO\s+\S+\s+(.*)", line.strip())
        if m:
            ports = m.group(1).split()
            break
    ins = [p for p in ports if p.startswith("in")]
    outs = [p for p in ports if p.startswith("out")]
    return CircuitParameter(
        supply_voltage=("vdd!", 0.0),
        ground=("gnd!", 0.0),
        bias_current=("", 0.0),
        input_plus=(ins[0] if ins else "", 0.0),
        input_minus=(ins[1] if len(ins) > 1 else "", 0.0),
        output_net=outs[0] if outs else "",
    )


@pytest.fixture(scope="module")
def _small_library_config(inputs_dir):
    from ckt_io.device_types_parser import load_device_types
    from ckt_io.hspice_mapping import HSpiceMapping
    from ckt_io.supply_nets_parser import SupplyNetConfig
    from recognition.library import Library

    base = inputs_dir / "SynthesisSmallLibrary"
    return (
        base,
        load_device_types(str(base / "deviceTypes.xcat")),
        HSpiceMapping.from_file(str(base / "HSpiceMapping.xcat")),
        SupplyNetConfig.from_file(str(base / "supplyNets.xcat")),
        Library.from_directory(None),
    )


@pytest.mark.parametrize("opamp", _OPAMP_NAMES)
def test_acst_partitioner_over_diverse_opamps(opamp, _small_library_config):
    from ckt_io.hspice_parser import HSpiceParser
    from partitioning.acst_partitioner import AcstPartitioner
    from partitioning.acst_parts import AcstPartitionResult
    from recognition.recognizer import StructureRecognizer

    base, dt, mp, sn, lib = _small_library_config
    netlist = base / "Netlist" / f"{opamp}.hspice"

    circuit = HSpiceParser(mp, sn, dt).parse(str(netlist))
    sc = StructureRecognizer(lib).recognize(circuit)
    params = _params_from_macro(netlist)

    result = AcstPartitioner(params).partition(sc)

    # every op-amp partitions to a result with an identified first stage
    assert isinstance(result, AcstPartitionResult)
    assert result.has_first_stage()


# ═══════════════════════════════════════════════════════════════════════════
#  partitioning/analysis.py — the acst-format write branch
# ═══════════════════════════════════════════════════════════════════════════


def test_partitioning_cli_acst_output_format(inputs_dir, tmp_path):
    """`partitioning --output-format acst` routes through the acst partitioner
    and its XML writer (analysis.py acst branch)."""
    import xml.etree.ElementTree as ET

    from cli import run

    src = inputs_dir / "AutomaticSizing"
    out = tmp_path / "part_acst.xml"
    result = run([
        "--log-level-console", "OFF",
        "partitioning",
        "--circuit", str(src / "cascodedSymmetricalCMOSOTA.hspice"),
        "--device-types", str(src / "deviceTypes.xcat"),
        "--mapping", str(src / "HSpiceMapping.xcat"),
        "--supply-nets", str(src / "supplyNets.xcat"),
        "--circuit-params", str(src / "CircuitParameterAndSpecifications.xml"),
        "--output-format", "acst",
        "--output", str(out),
    ])
    assert result.returncode == 0
    assert out.exists()
    root = ET.parse(out).getroot()
    assert root.tag == "acst_results"
    assert root.find("circuit_partitioning_results") is not None


# ═══════════════════════════════════════════════════════════════════════════
#  partitioning/net_inference.py — degenerate / fallback / tie-break branches
# ═══════════════════════════════════════════════════════════════════════════


def _cap(name: str) -> Device:
    return Device(name, DeviceType.CAPACITOR, TechType.UNDEFINED)


def test_infer_input_nets_returns_empty_on_only_degenerate_pairs():
    """No clean diff pair: same-gate, same-drain and missing-terminal pairs are
    all rejected, so input inference falls through to ``[]``."""
    from partitioning.net_inference import _infer_input_nets

    ckt = Circuit(name="degenerate")
    for n in ("vdd!", "gnd!", "s1", "g", "d1", "d2", "s2", "ga", "gb", "dd"):
        ckt.add_net(_net(n, SupplyType.VDD if n == "vdd!" else
                         SupplyType.GND if n == "gnd!" else SupplyType.NO_SUPPLY))
    nets = {n.name: n for n in ckt.nets}

    def add(name, src, gate, drain):
        m = _mos(name)
        ckt.add_device(m)
        _wire(ckt, m, nets[src], PinType.SOURCE)
        _wire(ckt, m, nets[gate], PinType.GATE)
        _wire(ckt, m, nets[drain], PinType.DRAIN)

    add("m1", "s1", "g", "d1")
    add("m2", "s1", "g", "d2")          # same gate as m1 → gates-equal skip
    add("m3", "s2", "ga", "dd")
    add("m4", "s2", "gb", "dd")         # distinct gates, same drain → drains-equal skip

    assert _infer_input_nets(ckt) == []


def test_infer_output_net_skips_source_nets_and_breaks_tie_with_cap():
    """Two all-drain candidates; the one a load capacitor ties to a rail wins,
    and an all-drain net that also carries a source terminal is skipped."""
    from partitioning.net_inference import _infer_output_net

    ckt = Circuit(name="two_out")
    for n, s in (("vdd!", SupplyType.VDD), ("gnd!", SupplyType.GND),
                 ("outA", SupplyType.NO_SUPPLY), ("outB", SupplyType.NO_SUPPLY),
                 ("srcnet", SupplyType.NO_SUPPLY), ("g", SupplyType.NO_SUPPLY)):
        ckt.add_net(_net(n, s))
    nets = {n.name: n for n in ckt.nets}

    def drainer(name, drain):
        m = _mos(name)
        ckt.add_device(m)
        _wire(ckt, m, nets[drain], PinType.DRAIN)

    # two all-drain candidate output nets
    drainer("a1", "outA"); drainer("a2", "outA")
    drainer("b1", "outB"); drainer("b2", "outB")
    # a net with 2 drains but also a source terminal → not an output (skipped)
    drainer("c1", "srcnet"); drainer("c2", "srcnet")
    msrc = _mos("msrc"); ckt.add_device(msrc)
    _wire(ckt, msrc, nets["srcnet"], PinType.SOURCE)

    # load capacitor ties outA to the ground rail → breaks the outA/outB tie
    cap = _cap("cap1"); ckt.add_device(cap)
    _wire(ckt, cap, nets["outA"], PinType.PLUS)
    _wire(ckt, cap, nets["gnd!"], PinType.MINUS)

    assert _infer_output_net(ckt) == "outA"


def test_infer_bias_net_skips_supply_diode_and_returns_empty():
    """A diode-connected device sitting on a supply rail is not a bias
    reference, so bias inference yields ``""``."""
    from partitioning.net_inference import _infer_bias_net

    ckt = Circuit(name="supply_diode")
    ckt.add_net(_net("vdd!", SupplyType.VDD))
    ckt.add_net(_net("gnd!", SupplyType.GND))
    vdd = {n.name: n for n in ckt.nets}["vdd!"]

    # drain == gate == vdd! → diode-connected but on a supply net → skipped
    m = _mos("mdiode", TechType.P)
    ckt.add_device(m)
    _wire(ckt, m, vdd, PinType.DRAIN)
    _wire(ckt, m, vdd, PinType.GATE)

    assert _infer_bias_net(ckt) == ""
