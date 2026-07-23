from __future__ import annotations

import pytest

from ckt_io.circuit_info_parser import (
	CircuitInformation,
	CircuitParameter,
	Specifications,
	load_circuit_information,
	parse_circuit_parameters,
	parse_specifications,
)
from ckt_io.device_types_parser import load_device_types
from ckt_io.hspice_mapping import HSpiceMapping, _repair_known_mapping_xml_issues
from ckt_io.hspice_parser import HSpiceParser
from ckt_io.hspice_writer import HSpiceWriter
from ckt_io.supply_nets_parser import SupplyNetConfig
from ckt_io.technology_parser import TechnologyParams, TransistorTechParams
from core import (
	Circuit,
	Device,
	DeviceType,
	Net,
	NetId,
	PinType,
	Port,
	PortType,
	Supply,
	SupplyType,
	TechType,
	Terminal,
)


def test_load_device_types_parses_reference_xcat() -> None:
	register = load_device_types("tests/data/deviceTypes.xcat")

	mos_pins = register.get_pin_types(DeviceType.MOSFET)
	assert [p.pin_type for p in mos_pins] == [
		PinType.DRAIN,
		PinType.GATE,
		PinType.SOURCE,
		PinType.BULK,
	]
	assert mos_pins[3].optional is True
	assert mos_pins[3].auto_connection == PinType.SOURCE

	mos_techs = register.get_tech_types(DeviceType.MOSFET)
	assert mos_techs == [TechType.N, TechType.P]

	cap_pins = register.get_pin_types(DeviceType.CAPACITOR)
	assert [p.pin_type for p in cap_pins] == [PinType.PLUS, PinType.MINUS]
	assert all(p.optional is False for p in cap_pins)

	cap_techs = register.get_tech_types(DeviceType.CAPACITOR)
	assert cap_techs == [TechType.UNDEFINED]

def test_load_device_types_unknown_pin_raises_keyerror(tmp_path) -> None:
	xml = """
<deviceTypes>
	<deviceType name="Mosfet">
		<techTypes>
			<techType>n</techType>
			<techType>p</techType>
		</techTypes>
		<pinTypes>
			<pinType>Drain</pinType>
			<pinType>DoesNotExist</pinType>
		</pinTypes>
	</deviceType>
</deviceTypes>
"""
	bad_file = tmp_path / "bad_device_types.xcat"
	bad_file.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Unknown pin type"):
		load_device_types(bad_file)

def test_hspice_mapping_parses_reference_xcat_with_repair() -> None:
	mapping = HSpiceMapping.from_file("tests/data/HSpiceMapping.xcat")

	assert len(mapping) == 6
	assert "m" in mapping
	assert "M" in mapping

	m = mapping.get_mapping("M")
	assert m.device_type is DeviceType.MOSFET
	assert m.has_model is True
	assert m.model_position == 5
	assert m.pin_positions == {
		PinType.DRAIN: 1,
		PinType.GATE: 2,
		PinType.SOURCE: 3,
		PinType.BULK: 4,
	}
	assert m.model_map is not None
	assert m.model_map["nmos"] is TechType.N
	assert m.model_map["pmos"] is TechType.P

	c = mapping.get_mapping("c")
	assert c.device_type is DeviceType.CAPACITOR
	assert c.has_model is False
	assert c.model_position is None
	assert c.model_map is None
	assert c.fixed_tech is TechType.UNDEFINED
	assert c.pin_positions == {
		PinType.PLUS: 1,
		PinType.MINUS: 2,
	}

def test_hspice_mapping_case_insensitive_tokens(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="M">
        <deviceTypeName>mosfet</deviceTypeName>
        <pins>
            <pin pinType="dRaIn" position="1"/>
            <pin pinType="gAtE" position="2"/>
            <pin pinType="source" position="3"/>
            <pin pinType="BULK" position="4"/>
        </pins>
        <modelName position="5">
            <model name="NMOS4" techType="N"/>
            <model name="PMOS4" techType="p"/>
        </modelName>
    </deviceLineMapping>
</deviceLineMapper>
"""
	file = tmp_path / "mixed_case_mapping.xcat"
	file.write_text(xml, encoding="utf-8")

	mapping = HSpiceMapping.from_file(file)
	rule = mapping.get_mapping("m")

	assert rule.device_type is DeviceType.MOSFET
	assert rule.pin_positions[PinType.DRAIN] == 1
	assert rule.pin_positions[PinType.GATE] == 2
	assert rule.pin_positions[PinType.SOURCE] == 3
	assert rule.pin_positions[PinType.BULK] == 4
	assert rule.model_map is not None
	assert rule.model_map["nmos4"] is TechType.N
	assert rule.model_map["pmos4"] is TechType.P

def test_hspice_mapping_unknown_identifier_raises() -> None:
	mapping = HSpiceMapping.from_file("tests/data/HSpiceMapping.xcat")
	with pytest.raises(KeyError):
		mapping.get_mapping("z")

def test_hspice_mapping_identifiers_property() -> None:
	mapping = HSpiceMapping.from_file("tests/data/HSpiceMapping.xcat")
	ids = mapping.identifiers
	assert isinstance(ids, list)
	assert "m" in ids

def test_hspice_mapping_empty_identifier_skipped(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="">
        <deviceTypeName>mosfet</deviceTypeName>
    </deviceLineMapping>
    <deviceLineMapping identifier="m">
        <deviceTypeName>mosfet</deviceTypeName>
        <pins>
            <pin pinType="Drain" position="1"/>
            <pin pinType="Gate" position="2"/>
            <pin pinType="Source" position="3"/>
            <pin pinType="Bulk" position="4"/>
        </pins>
        <modelName position="5">
            <model name="nmos" techType="n"/>
        </modelName>
    </deviceLineMapping>
</deviceLineMapper>
"""
	f = tmp_path / "empty_id.xcat"
	f.write_text(xml, encoding="utf-8")
	mapping = HSpiceMapping.from_file(f)
	assert len(mapping) == 1
	assert "m" in mapping

def test_hspice_mapping_missing_device_type_name_raises(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="x">
    </deviceLineMapping>
</deviceLineMapper>
"""
	f = tmp_path / "no_dtype.xcat"
	f.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Missing deviceTypeName"):
		HSpiceMapping.from_file(f)

def test_hspice_mapping_unknown_device_type_raises(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="x">
        <deviceTypeName>NotADevice</deviceTypeName>
    </deviceLineMapping>
</deviceLineMapper>
"""
	f = tmp_path / "bad_dtype.xcat"
	f.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Unknown device type"):
		HSpiceMapping.from_file(f)

def test_hspice_mapping_pin_with_missing_attrs_skipped(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="c">
        <deviceTypeName>capacitor</deviceTypeName>
        <pins>
            <pin pinType="" position="1"/>
            <pin pinType="Plus" position=""/>
            <pin pinType="Plus" position="1"/>
            <pin pinType="Minus" position="2"/>
        </pins>
        <techType>undefined</techType>
    </deviceLineMapping>
</deviceLineMapper>
"""
	f = tmp_path / "empty_pin_attr.xcat"
	f.write_text(xml, encoding="utf-8")
	mapping = HSpiceMapping.from_file(f)
	rule = mapping.get_mapping("c")
	assert PinType.PLUS in rule.pin_positions
	assert PinType.MINUS in rule.pin_positions

def test_hspice_mapping_unknown_pin_type_raises(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="m">
        <deviceTypeName>mosfet</deviceTypeName>
        <pins>
            <pin pinType="UnknownPin" position="1"/>
        </pins>
        <modelName position="5">
            <model name="nmos" techType="n"/>
        </modelName>
    </deviceLineMapping>
</deviceLineMapper>
"""
	f = tmp_path / "bad_pin.xcat"
	f.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Unknown pin type"):
		HSpiceMapping.from_file(f)

def test_hspice_mapping_model_name_missing_position_raises(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="m">
        <deviceTypeName>mosfet</deviceTypeName>
        <modelName>
            <model name="nmos" techType="n"/>
        </modelName>
    </deviceLineMapping>
</deviceLineMapper>
"""
	f = tmp_path / "no_model_pos.xcat"
	f.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Missing modelName position"):
		HSpiceMapping.from_file(f)

def test_hspice_mapping_model_entry_missing_attrs_skipped(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="m">
        <deviceTypeName>mosfet</deviceTypeName>
        <modelName position="5">
            <model name="" techType="n"/>
            <model name="nmos" techType=""/>
            <model name="nmos" techType="n"/>
        </modelName>
    </deviceLineMapping>
</deviceLineMapper>
"""
	f = tmp_path / "empty_model_attr.xcat"
	f.write_text(xml, encoding="utf-8")
	mapping = HSpiceMapping.from_file(f)
	rule = mapping.get_mapping("m")
	assert rule.model_map == {"nmos": TechType.N}

def test_hspice_mapping_unknown_tech_type_in_model_raises(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="m">
        <deviceTypeName>mosfet</deviceTypeName>
        <modelName position="5">
            <model name="nmos" techType="NotATech"/>
        </modelName>
    </deviceLineMapping>
</deviceLineMapper>
"""
	f = tmp_path / "bad_model_tech.xcat"
	f.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Unknown tech type"):
		HSpiceMapping.from_file(f)

def test_hspice_mapping_unknown_fixed_tech_type_raises(tmp_path) -> None:
	xml = """
<deviceLineMapper>
    <deviceLineMapping identifier="c">
        <deviceTypeName>capacitor</deviceTypeName>
        <techType>NotATech</techType>
    </deviceLineMapping>
</deviceLineMapper>
"""
	f = tmp_path / "bad_fixed_tech.xcat"
	f.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Unknown fixed tech type"):
		HSpiceMapping.from_file(f)

def test_hspice_mapping_broken_xml_raises(tmp_path) -> None:
	f = tmp_path / "broken.xcat"
	f.write_text("<not valid xml <<<<", encoding="utf-8")
	import xml.etree.ElementTree as ET
	with pytest.raises(ET.ParseError):
		HSpiceMapping.from_file(f)

def test_repair_already_valid_xml_returns_unchanged() -> None:
	xml = "<deviceLineMapper></deviceLineMapper>"
	result = _repair_known_mapping_xml_issues(xml)
	assert result == xml

def test_repair_no_closing_tag_returns_unchanged() -> None:
	# No </deviceLineMapper> and no </deviceLineMapping> → idx == -1 branch
	xml = "<root><child/></root>"
	result = _repair_known_mapping_xml_issues(xml)
	assert result == xml

def test_supply_nets_parses_reference_and_classifies() -> None:
	config = SupplyNetConfig.from_file("tests/data/supplyNets.xcat")

	assert config.classify("gnd!") == "GND_1"
	assert config.classify("vdd!") == "VDD_2"
	assert config.classify("vddp") == "VDD_2"
	# Last file line has unterminated quote: VDD_1 "Vdd
	assert config.classify("vdd") == "VDD_1"

	assert config.is_ground("gnd!")
	assert not config.is_supply("gnd!")
	assert config.is_supply("vdd!")
	assert config.is_power("vddp!")

	assert config.supply_level("gnd!") == 1
	assert config.supply_level("vdd!") == 2
	assert config.supply_level("unknown") == 0
	assert config.classify("unknown") is None

def test_supply_nets_case_insensitive_lookup_and_labels(tmp_path) -> None:
	content = """
gnd_3 "GNDX"
VdD_7 "VddMain"
"""
	path = tmp_path / "supply_case.xcat"
	path.write_text(content, encoding="utf-8")

	config = SupplyNetConfig.from_file(path)

	assert config.classify("gndx") == "GND_3"
	assert config.classify("GNDX") == "GND_3"
	assert config.classify("vddmain") == "VDD_7"
	assert config.classify("VDDMAIN") == "VDD_7"
	assert config.is_ground("GNDX")
	assert config.is_supply("VDDMAIN")
	assert config.supply_level("VddMain") == 7

def test_supply_nets_malformed_lines_skipped(tmp_path) -> None:
	content = (
		"gnd_1 \"gnd!\"\n"
		"justonetoken\n"          # < 2 parts → skipped (line 72)
		'vdd_2 ""\n'              # empty net name after strip → skipped (line 80)
		'vdd_2 "  "\n'            # also empty after strip
		"OTHER_3 \"someNet\"\n"   # unknown label family → skipped (line 88)
	)
	path = tmp_path / "malformed.xcat"
	path.write_text(content, encoding="utf-8")

	config = SupplyNetConfig.from_file(path)
	assert config.classify("gnd!") == "GND_1"
	assert config.classify("someNet") is None   # unknown label skipped
	assert len(config._label_by_net) == 1

def test_supply_nets_supply_level_no_underscore(tmp_path) -> None:
	# Label with no underscore → rsplit gives only 1 part → IndexError → returns 0
	content = "GND \"gndflat\"\n"
	path = tmp_path / "nounderscore.xcat"
	path.write_text(content, encoding="utf-8")

	config = SupplyNetConfig.from_file(path)
	assert config.supply_level("gndflat") == 0

def test_supply_nets_supply_level_non_numeric_suffix(tmp_path) -> None:
	# Label suffix is not a number → ValueError → returns 0
	content = "GND_abc \"gndx\"\n"
	path = tmp_path / "nonnumeric.xcat"
	path.write_text(content, encoding="utf-8")

	config = SupplyNetConfig.from_file(path)
	assert config.supply_level("gndx") == 0

# ── HSpice parser tests ──────────────────────────────────────────────────

def _make_hspice_parser() -> HSpiceParser:
	"""Build an HSpiceParser from the reference config files."""
	device_types = load_device_types("tests/data/deviceTypes.xcat")
	mapping = HSpiceMapping.from_file("tests/data/HSpiceMapping.xcat")
	supply_nets = SupplyNetConfig.from_file("tests/data/supplyNets.xcat")
	return HSpiceParser(mapping, supply_nets, device_types)

def test_hspice_parser_parses_reference_netlist() -> None:
	parser = _make_hspice_parser()
	circuit = parser.parse("tests/data/cascodedSymmetricalCMOSOTA.hspice")

	# Circuit name extracted from comment header
	assert circuit.name == "cascodeSymmetricalCMOSOTA"

	# 18 MOSFETs + 1 capacitor
	assert len(circuit.mosfets) == 18
	assert len(circuit.capacitors) == 1
	assert len(circuit.devices) == 19

	# m4 gate connected to inp, nmos tech
	m4 = circuit.find_device("m4")
	assert m4.device_type is DeviceType.MOSFET
	assert m4.tech_type is TechType.N
	assert m4.get_net(PinType.GATE).name == "inp"

	# cl (capacitor) between out and gnd!
	cl = circuit.find_device("cl")
	assert cl.device_type is DeviceType.CAPACITOR
	assert cl.tech_type is TechType.UNDEFINED
	assert cl.get_net(PinType.PLUS).name == "out"
	assert cl.get_net(PinType.MINUS).name == "gnd!"

	# Supply classification
	vdd = circuit.find_net("vdd!")
	assert vdd.is_vdd()
	assert vdd.supply.level == 2
	assert vdd.is_global

	gnd = circuit.find_net("gnd!")
	assert gnd.is_ground()
	assert gnd.supply.level == 1
	assert gnd.is_global

	# Internal nets have no supply annotation
	assert not circuit.find_net("inp").is_supply()

def test_hspice_parser_bulk_auto_connection(tmp_path) -> None:
	parser = _make_hspice_parser()

	# 5-token MOS line: name D G S model — bulk omitted
	hspice = (
		".GLOBAL vdd! gnd!\n"
		"m1 out inp gnd! nmos\n"
		".END\n"
	)
	path = tmp_path / "short_mos.hspice"
	path.write_text(hspice, encoding="utf-8")

	circuit = parser.parse(path)
	m1 = circuit.find_device("m1")

	# Bulk auto-connects to Source net (gnd!)
	assert m1.get_net(PinType.SOURCE).name == "gnd!"
	assert m1.get_net(PinType.BULK).name == "gnd!"
	assert m1.get_net(PinType.DRAIN).name == "out"
	assert m1.get_net(PinType.GATE).name == "inp"
	assert m1.tech_type is TechType.N

def test_hspice_parser_case_insensitive_model(tmp_path) -> None:
	parser = _make_hspice_parser()

	hspice = (
		"m1 net1 net2 net3 net3 NMOS\n"
		"m2 net4 net5 net6 net6 Pmos\n"
		".END\n"
	)
	path = tmp_path / "mixed_case.hspice"
	path.write_text(hspice, encoding="utf-8")

	circuit = parser.parse(path)
	assert circuit.find_device("m1").tech_type is TechType.N
	assert circuit.find_device("m2").tech_type is TechType.P

def test_hspice_parser_inline_wl_params(tmp_path) -> None:
	# Device lines may carry inline "W=.." / "L=.." params after the model
	# name (as in .ckt netlists). These must not be mistaken for the model;
	# the model is the last *non-parameter* token.
	parser = _make_hspice_parser()

	hspice = (
		"m1 d g s b nmos L=3.68e-6 W=2.95e-6\n"
		"m2 d2 g2 s2 b2 pmos W=10e-6 L=1e-6 M=2\n"
		".END\n"
	)
	path = tmp_path / "inline_params.hspice"
	path.write_text(hspice, encoding="utf-8")

	circuit = parser.parse(path)
	assert circuit.find_device("m1").tech_type is TechType.N
	assert circuit.find_device("m2").tech_type is TechType.P
	# pins still read from the correct (param-stripped) positions
	assert circuit.find_device("m1").get_net(PinType.DRAIN).name == "d"
	assert circuit.find_device("m1").get_net(PinType.GATE).name == "g"


def test_hspice_parser_unknown_model_undefined(tmp_path) -> None:
	# An unknown model string doesn't abort the parse; the device is tagged
	# UNDEFINED (mirrors the C++ parser's tolerance).
	parser = _make_hspice_parser()

	hspice = "m1 d g s b weirdmodel\n.END\n"
	path = tmp_path / "unknown_model.hspice"
	path.write_text(hspice, encoding="utf-8")

	circuit = parser.parse(path)
	assert circuit.find_device("m1").tech_type is TechType.UNDEFINED


def test_hspice_parser_unknown_identifier_skipped(tmp_path) -> None:
	# An unmapped device identifier (here 'z') is tolerated: the line is
	# skipped with a warning rather than aborting the parse — mirroring the
	# C++ ACST parser. The surrounding valid devices still parse.
	parser = _make_hspice_parser()

	hspice = (
		"m1 net1 net2 net3 net3 nmos\n"
		"z1 net1 net2\n"
		".END\n"
	)
	path = tmp_path / "bad_id.hspice"
	path.write_text(hspice, encoding="utf-8")

	circuit = parser.parse(path)
	assert circuit.has_device("m1")
	assert not circuit.has_device("z1")

def test_hspice_parser_skips_subcircuit_markers(tmp_path) -> None:
	parser = _make_hspice_parser()

	hspice = (
		".SUBCKT inner inp out\n"
		"m1 out inp gnd! gnd! nmos\n"
		".ENDS inner\n"
		".MACRO wrapper\n"
		".EOM wrapper\n"
		"m2 out inp gnd! gnd! nmos\n"
		".END\n"
	)
	path = tmp_path / "subckt.hspice"
	path.write_text(hspice, encoding="utf-8")

	circuit = parser.parse(path)
	# Only m2 is at the top level; m1 inside .SUBCKT/.ENDS is skipped
	assert circuit.find_device("m2") is not None

def test_hspice_parser_parse_device_line_empty_is_noop(tmp_path) -> None:
	parser = _make_hspice_parser()
	circuit = Circuit(name="empty_test")
	# Calling _parse_device_line directly with a whitespace-only string
	# exercises the `if not tokens: return` guard (line 202)
	parser._parse_device_line("   ", circuit)
	assert len(circuit.devices) == 0

# ── HSpice writer helpers ────────────────────────────────────────────────

def _build_simple_circuit() -> Circuit:
	"""Build a small circuit with 1 NMOS, 1 cap, and 3 ports for writer tests."""
	circuit = Circuit(name="test_opamp")

	# Ports
	circuit.add_port(Port("inp", PortType.INPUT))
	circuit.add_port(Port("out", PortType.OUTPUT))
	circuit.add_port(Port("vss", PortType.INOUT))

	# NMOS m1: drain=out, gate=inp, source=vss, bulk=vss
	m1 = Device("m1", DeviceType.MOSFET, TechType.N)
	circuit.add_device(m1)
	for pin, net_name in [
		(PinType.DRAIN, "out"),
		(PinType.GATE, "inp"),
		(PinType.SOURCE, "vss"),
		(PinType.BULK, "vss"),
	]:
		net = circuit.find_or_create_net(net_name)
		t = Terminal(m1, pin, net)
		m1.add_terminal(t)
		net.add_terminal(t)
		circuit.add_terminal(t)

	# Capacitor cl: plus=out, minus=vss
	cl = Device("cl", DeviceType.CAPACITOR, TechType.UNDEFINED)
	circuit.add_device(cl)
	for pin, net_name in [(PinType.PLUS, "out"), (PinType.MINUS, "vss")]:
		net = circuit.find_or_create_net(net_name)
		t = Terminal(cl, pin, net)
		cl.add_terminal(t)
		net.add_terminal(t)
		circuit.add_terminal(t)

	return circuit

# ── HSpice writer tests ─────────────────────────────────────────────────

def test_hspice_writer_header(tmp_path) -> None:
	circuit = _build_simple_circuit()
	writer = HSpiceWriter()
	out = tmp_path / "header.ckt"
	writer.write(circuit, out)

	text = out.read_text(encoding="utf-8")
	lines = text.splitlines()
	assert lines[0] == "** Name: test_opamp"
	# blank line after header
	assert lines[1] == ""

def test_hspice_writer_macro_header_and_footer(tmp_path) -> None:
	circuit = _build_simple_circuit()
	writer = HSpiceWriter()
	out = tmp_path / "macro.ckt"
	writer.write(circuit, out)

	text = out.read_text(encoding="utf-8")
	lines = text.splitlines()

	# .MACRO line includes circuit name and port names
	assert lines[2] == ".MACRO test_opamp inp out vss"

	# .EOM line
	assert lines[-1] == ".EOM test_opamp"

def test_hspice_writer_mosfet_line(tmp_path) -> None:
	circuit = _build_simple_circuit()
	writer = HSpiceWriter()
	out = tmp_path / "mos.ckt"
	writer.write(circuit, out)

	text = out.read_text(encoding="utf-8")

	# m1 drain gate source bulk model
	assert "m1 out inp vss vss nmos4" in text

def test_hspice_writer_pmos_model(tmp_path) -> None:
	circuit = Circuit(name="ptest")
	m1 = Device("m1", DeviceType.MOSFET, TechType.P)
	circuit.add_device(m1)
	for pin, net_name in [
		(PinType.DRAIN, "d"),
		(PinType.GATE, "g"),
		(PinType.SOURCE, "s"),
		(PinType.BULK, "s"),
	]:
		net = circuit.find_or_create_net(net_name)
		t = Terminal(m1, pin, net)
		m1.add_terminal(t)
		net.add_terminal(t)
		circuit.add_terminal(t)

	writer = HSpiceWriter()
	out = tmp_path / "pmos.ckt"
	writer.write(circuit, out)

	text = out.read_text(encoding="utf-8")
	assert "m1 d g s s pmos4" in text

def test_hspice_writer_capacitor_line_no_model(tmp_path) -> None:
	circuit = _build_simple_circuit()
	writer = HSpiceWriter()
	out = tmp_path / "cap.ckt"
	writer.write(circuit, out)

	text = out.read_text(encoding="utf-8")

	# capacitor: name plus minus  (no model name)
	assert "cl out vss" in text
	# must NOT contain a model token after the two nets
	for line in text.splitlines():
		if line.startswith("cl"):
			tokens = line.split()
			assert len(tokens) == 3
			assert tokens == ["cl", "out", "vss"]

def test_hspice_writer_device_parameters(tmp_path) -> None:
	circuit = Circuit(name="params_test")
	m1 = Device("m1", DeviceType.MOSFET, TechType.N)
	m1.set_parameter("L", "4e-6")
	m1.set_parameter("W", "53e-6")
	circuit.add_device(m1)
	for pin, net_name in [
		(PinType.DRAIN, "d"),
		(PinType.GATE, "g"),
		(PinType.SOURCE, "s"),
		(PinType.BULK, "s"),
	]:
		net = circuit.find_or_create_net(net_name)
		t = Terminal(m1, pin, net)
		m1.add_terminal(t)
		net.add_terminal(t)
		circuit.add_terminal(t)

	writer = HSpiceWriter()
	out = tmp_path / "params.ckt"
	writer.write(circuit, out)

	text = out.read_text(encoding="utf-8")
	assert "m1 d g s s nmos4 L=4e-6 W=53e-6" in text

def test_hspice_writer_capacitor_with_value(tmp_path) -> None:
	# Capacitor value written positionally (no 'C=' prefix)
	circuit = Circuit(name="cap_val_test")
	cl = Device("cl", DeviceType.CAPACITOR, TechType.UNDEFINED)
	cl.set_parameter("C", "20e-12")
	circuit.add_device(cl)
	for pin, net_name in [(PinType.PLUS, "out"), (PinType.MINUS, "gnd")]:
		net = circuit.find_or_create_net(net_name)
		t = Terminal(cl, pin, net)
		cl.add_terminal(t)
		net.add_terminal(t)
		circuit.add_terminal(t)

	line = HSpiceWriter._format_device_line(cl)
	tokens = line.split()
	assert tokens == ["cl", "out", "gnd", "C=20e-12"]

def test_hspice_writer_resistor_with_value(tmp_path) -> None:
	# Resistor value written positionally (no 'R=' prefix)
	circuit = Circuit(name="res_val_test")
	r1 = Device("r1", DeviceType.RESISTOR, TechType.UNDEFINED)
	r1.set_parameter("R", "10e3")
	circuit.add_device(r1)
	for pin, net_name in [(PinType.PLUS, "a"), (PinType.MINUS, "b")]:
		net = circuit.find_or_create_net(net_name)
		t = Terminal(r1, pin, net)
		r1.add_terminal(t)
		net.add_terminal(t)
		circuit.add_terminal(t)

	line = HSpiceWriter._format_device_line(r1)
	tokens = line.split()
	assert tokens == ["r1", "a", "b", "R=10e3"]

def test_hspice_writer_inductor_with_value(tmp_path) -> None:
	# Inductor value written positionally (no 'L=' prefix)
	circuit = Circuit(name="ind_val_test")
	l1 = Device("l1", DeviceType.INDUCTOR, TechType.UNDEFINED)
	l1.set_parameter("L", "1e-9")
	circuit.add_device(l1)
	for pin, net_name in [(PinType.PLUS, "a"), (PinType.MINUS, "b")]:
		net = circuit.find_or_create_net(net_name)
		t = Terminal(l1, pin, net)
		l1.add_terminal(t)
		net.add_terminal(t)
		circuit.add_terminal(t)

	line = HSpiceWriter._format_device_line(l1)
	tokens = line.split()
	assert tokens == ["l1", "a", "b", "L=1e-9"]

def test_hspice_writer_performance_comments(tmp_path) -> None:
	circuit = _build_simple_circuit()
	writer = HSpiceWriter()
	out = tmp_path / "perf.ckt"
	writer.write(
		circuit,
		out,
		performance={"Gain": "83 dB", "Power consumption": "0.809 mW"},
	)

	text = out.read_text(encoding="utf-8")
	assert "** Expected Performance Values:" in text
	assert "** Gain: 83 dB" in text
	assert "** Power consumption: 0.809 mW" in text

def test_hspice_writer_voltages_comments(tmp_path) -> None:
	circuit = _build_simple_circuit()
	writer = HSpiceWriter()
	out = tmp_path / "volts.ckt"
	writer.write(circuit, out, voltages={"out": 2.5, "vss": 0.0})

	text = out.read_text(encoding="utf-8")
	assert "** Expected Voltages:" in text
	assert "** out: 2.5 V" in text
	assert "** vss: 0.0 V" in text

def test_hspice_writer_currents_comments(tmp_path) -> None:
	circuit = _build_simple_circuit()
	writer = HSpiceWriter()
	out = tmp_path / "curr.ckt"
	writer.write(circuit, out, currents={"m1": 42.5})

	text = out.read_text(encoding="utf-8")
	assert "** Expected Currents:" in text
	assert "** m1: 42.5 muA" in text

def test_hspice_writer_no_optional_annotations(tmp_path) -> None:
	circuit = _build_simple_circuit()
	writer = HSpiceWriter()
	out = tmp_path / "noannot.ckt"
	writer.write(circuit, out)

	text = out.read_text(encoding="utf-8")
	assert "** Expected Performance" not in text
	assert "** Expected Voltages" not in text
	assert "** Expected Currents" not in text

def test_hspice_writer_empty_circuit(tmp_path) -> None:
	circuit = Circuit(name="empty")
	writer = HSpiceWriter()
	out = tmp_path / "empty.ckt"
	writer.write(circuit, out)

	text = out.read_text(encoding="utf-8")
	lines = text.splitlines()
	assert lines[0] == "** Name: empty"
	assert lines[2] == ".MACRO empty"
	assert lines[3] == ".EOM empty"

def test_hspice_writer_round_trip(tmp_path) -> None:
	"""Parse → write → re-parse: connectivity must be preserved."""
	parser = _make_hspice_parser()
	circuit1 = parser.parse("tests/data/cascodedSymmetricalCMOSOTA.hspice")

	writer = HSpiceWriter()
	out = tmp_path / "round_trip.ckt"
	writer.write(circuit1, out)

	text = out.read_text(encoding="utf-8")

	# Verify structural markers present
	assert "** Name: cascodeSymmetricalCMOSOTA" in text
	assert ".MACRO cascodeSymmetricalCMOSOTA" in text
	assert ".EOM cascodeSymmetricalCMOSOTA" in text

	# Verify all 19 devices are present as lines
	device_lines = [
		l for l in text.splitlines()
		if l and not l.startswith("*") and not l.startswith(".")
	]
	assert len(device_lines) == 19

	# Spot-check specific device wiring preserved
	assert "m4 net40 inp net36 net36 nmos4" in text
	assert "cl out gnd!" in text

# ── Technology parser tests ──────────────────────────────────────────────

def test_technology_parser_parses_reference_file() -> None:
	"""Full acceptance test: parse the reference TechnologyFile.xml."""
	tech = TechnologyParams.from_file("tests/data/TechnologyFile.xml")

	assert tech.thermal_voltage == 0.026

	# NMOS spot checks
	assert tech.nmos.threshold_voltage == 0.405
	assert tech.nmos.mu_cox == 0.0001693
	assert tech.nmos.early_voltage == 4.4
	assert tech.nmos.slope_factor == 1.75
	assert tech.nmos.min_length == 1.0
	assert tech.nmos.min_width == 1.0
	assert tech.nmos.min_area == 10.0

	# PMOS spot checks
	assert tech.pmos.threshold_voltage == -0.564
	assert tech.pmos.mu_cox == 3.574e-05
	assert tech.pmos.early_voltage == 2.86
	assert tech.pmos.slope_factor == 1.31
	assert tech.pmos.pb == 0.99
	assert tech.pmos.min_length == 1.0

def test_technology_parser_all_nmos_fields() -> None:
	"""Verify every NMOS field is populated from the reference file."""
	tech = TechnologyParams.from_file("tests/data/TechnologyFile.xml")
	n = tech.nmos

	assert n.threshold_voltage == 0.405
	assert n.mu_cox == 0.0001693
	assert n.early_voltage == 4.4
	assert n.overlap_capacitance == 6.2e-10
	assert n.gate_oxide_capacitance == 0.006058
	assert n.cj == 0.001812
	assert n.cjsw == 5.341e-10
	assert n.pb == 0.5
	assert n.lateral_diffusion == 3.162e-05
	assert n.slope_factor == 1.75
	assert n.lambda_strong == 0.024
	assert n.lambda_weak == 0.07
	assert n.min_area == 10.0
	assert n.min_length == 1.0
	assert n.min_width == 1.0

def test_technology_parser_all_pmos_fields() -> None:
	"""Verify every PMOS field is populated from the reference file."""
	tech = TechnologyParams.from_file("tests/data/TechnologyFile.xml")
	p = tech.pmos

	assert p.threshold_voltage == -0.564
	assert p.mu_cox == 3.574e-05
	assert p.early_voltage == 2.86
	assert p.overlap_capacitance == 6.66e-10
	assert p.gate_oxide_capacitance == 0.006058
	assert p.cj == 0.001894
	assert p.cjsw == 3.626e-10
	assert p.pb == 0.99
	assert p.lateral_diffusion == 9.968e-07
	assert p.slope_factor == 1.31
	assert p.lambda_strong == 0.029
	assert p.lambda_weak == 0.074
	assert p.min_area == 10.0
	assert p.min_length == 1.0
	assert p.min_width == 1.0

def test_technology_parser_handles_stray_characters() -> None:
	"""The reference NMOS section has a stray 'q' after one closing tag.

	Parsing must succeed without error despite this quirk.
	"""
	tech = TechnologyParams.from_file("tests/data/TechnologyFile.xml")
	# The stray 'q' is between </zeroBiasSidewallBulkJunctionCapacitance>
	# and <bulkJunctionContactPotential>.  Both must parse correctly.
	assert tech.nmos.cjsw == 5.341e-10
	assert tech.nmos.pb == 0.5

def test_technology_parser_synthetic_file(tmp_path) -> None:
	"""Parse a minimal synthetic technology file."""
	xml = """\
<general>
	<thermalVoltage Vt="0.030"/>
</general>
<nmos>
	<thresholdVoltage vth="0.5"/>
	<mobilityOxideCapacity muCox="0.0002"/>
	<earlyVoltage earlyVoltage="5.0"/>
	<overlapCapacity Cgdov="1e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="5e-10"/>
	<bulkJunctionContactPotential pb="0.6"/>
	<lateralDiffusionLength Ldiff="1e-6"/>
	<slopeFactor n="1.5"/>
	<channelLengthCoefficientStrongInversion lamda="0.03"/>
	<channelLengthCoefficientWeakInversion lamda="0.08"/>
	<minArea Amin="8"/>
	<minLength Lmin="2"/>
	<minWidth Wmin="3"/>
</nmos>
<pmos>
	<thresholdVoltage vth="-0.6"/>
	<mobilityOxideCapacity muCox="0.00004"/>
	<earlyVoltage earlyVoltage="3.0"/>
	<overlapCapacity Cgdov="2e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="4e-10"/>
	<bulkJunctionContactPotential pb="1.0"/>
	<lateralDiffusionLength Ldiff="2e-6"/>
	<slopeFactor n="1.3"/>
	<channelLengthCoefficientStrongInversion lamda="0.025"/>
	<channelLengthCoefficientWeakInversion lamda="0.06"/>
	<minArea Amin="12"/>
	<minLength Lmin="1"/>
	<minWidth Wmin="1"/>
</pmos>
"""
	path = tmp_path / "TechTest.xml"
	path.write_text(xml, encoding="utf-8")

	tech = TechnologyParams.from_file(path)
	assert tech.thermal_voltage == 0.030
	assert tech.nmos.threshold_voltage == 0.5
	assert tech.nmos.mu_cox == 0.0002
	assert tech.nmos.min_length == 2.0
	assert tech.pmos.threshold_voltage == -0.6
	assert tech.pmos.pb == 1.0
	assert tech.pmos.min_area == 12.0

def test_technology_parser_missing_general_raises(tmp_path) -> None:
	"""Missing <general> section must raise KeyError."""
	xml = """\
<nmos>
	<thresholdVoltage vth="0.4"/>
	<mobilityOxideCapacity muCox="0.0002"/>
	<earlyVoltage earlyVoltage="5.0"/>
	<overlapCapacity Cgdov="1e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="5e-10"/>
	<bulkJunctionContactPotential pb="0.6"/>
	<lateralDiffusionLength Ldiff="1e-6"/>
	<slopeFactor n="1.5"/>
	<channelLengthCoefficientStrongInversion lamda="0.03"/>
	<channelLengthCoefficientWeakInversion lamda="0.08"/>
	<minArea Amin="8"/>
	<minLength Lmin="2"/>
	<minWidth Wmin="3"/>
</nmos>
<pmos>
	<thresholdVoltage vth="-0.6"/>
	<mobilityOxideCapacity muCox="0.00004"/>
	<earlyVoltage earlyVoltage="3.0"/>
	<overlapCapacity Cgdov="2e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="4e-10"/>
	<bulkJunctionContactPotential pb="1.0"/>
	<lateralDiffusionLength Ldiff="2e-6"/>
	<slopeFactor n="1.3"/>
	<channelLengthCoefficientStrongInversion lamda="0.025"/>
	<channelLengthCoefficientWeakInversion lamda="0.06"/>
	<minArea Amin="12"/>
	<minLength Lmin="1"/>
	<minWidth Wmin="1"/>
</pmos>
"""
	path = tmp_path / "no_general.xml"
	path.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Missing <general>"):
		TechnologyParams.from_file(path)

def test_technology_parser_missing_nmos_raises(tmp_path) -> None:
	"""Missing <nmos> section must raise KeyError."""
	xml = """\
<general>
	<thermalVoltage Vt="0.026"/>
</general>
<pmos>
	<thresholdVoltage vth="-0.6"/>
	<mobilityOxideCapacity muCox="0.00004"/>
	<earlyVoltage earlyVoltage="3.0"/>
	<overlapCapacity Cgdov="2e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="4e-10"/>
	<bulkJunctionContactPotential pb="1.0"/>
	<lateralDiffusionLength Ldiff="2e-6"/>
	<slopeFactor n="1.3"/>
	<channelLengthCoefficientStrongInversion lamda="0.025"/>
	<channelLengthCoefficientWeakInversion lamda="0.06"/>
	<minArea Amin="12"/>
	<minLength Lmin="1"/>
	<minWidth Wmin="1"/>
</pmos>
"""
	path = tmp_path / "no_nmos.xml"
	path.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Missing <nmos>"):
		TechnologyParams.from_file(path)

def test_technology_parser_missing_element_in_transistor_raises(tmp_path) -> None:
	"""A missing child element inside <nmos> must raise KeyError."""
	# Omitting <slopeFactor> from the NMOS section
	xml = """\
<general>
	<thermalVoltage Vt="0.026"/>
</general>
<nmos>
	<thresholdVoltage vth="0.4"/>
	<mobilityOxideCapacity muCox="0.0002"/>
	<earlyVoltage earlyVoltage="5.0"/>
	<overlapCapacity Cgdov="1e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="5e-10"/>
	<bulkJunctionContactPotential pb="0.6"/>
	<lateralDiffusionLength Ldiff="1e-6"/>
	<channelLengthCoefficientStrongInversion lamda="0.03"/>
	<channelLengthCoefficientWeakInversion lamda="0.08"/>
	<minArea Amin="8"/>
	<minLength Lmin="2"/>
	<minWidth Wmin="3"/>
</nmos>
<pmos>
	<thresholdVoltage vth="-0.6"/>
	<mobilityOxideCapacity muCox="0.00004"/>
	<earlyVoltage earlyVoltage="3.0"/>
	<overlapCapacity Cgdov="2e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="4e-10"/>
	<bulkJunctionContactPotential pb="1.0"/>
	<lateralDiffusionLength Ldiff="2e-6"/>
	<slopeFactor n="1.3"/>
	<channelLengthCoefficientStrongInversion lamda="0.025"/>
	<channelLengthCoefficientWeakInversion lamda="0.06"/>
	<minArea Amin="12"/>
	<minLength Lmin="1"/>
	<minWidth Wmin="1"/>
</pmos>
"""
	path = tmp_path / "missing_slope.xml"
	path.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Missing <slopeFactor>"):
		TechnologyParams.from_file(path)

def test_technology_parser_missing_attribute_raises(tmp_path) -> None:
	"""A present element with a missing attribute must raise KeyError."""
	# <thresholdVoltage> present but 'vth' attribute missing
	xml = """\
<general>
	<thermalVoltage Vt="0.026"/>
</general>
<nmos>
	<thresholdVoltage wrongattr="0.4"/>
	<mobilityOxideCapacity muCox="0.0002"/>
	<earlyVoltage earlyVoltage="5.0"/>
	<overlapCapacity Cgdov="1e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="5e-10"/>
	<bulkJunctionContactPotential pb="0.6"/>
	<lateralDiffusionLength Ldiff="1e-6"/>
	<slopeFactor n="1.5"/>
	<channelLengthCoefficientStrongInversion lamda="0.03"/>
	<channelLengthCoefficientWeakInversion lamda="0.08"/>
	<minArea Amin="8"/>
	<minLength Lmin="2"/>
	<minWidth Wmin="3"/>
</nmos>
<pmos>
	<thresholdVoltage vth="-0.6"/>
	<mobilityOxideCapacity muCox="0.00004"/>
	<earlyVoltage earlyVoltage="3.0"/>
	<overlapCapacity Cgdov="2e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="4e-10"/>
	<bulkJunctionContactPotential pb="1.0"/>
	<lateralDiffusionLength Ldiff="2e-6"/>
	<slopeFactor n="1.3"/>
	<channelLengthCoefficientStrongInversion lamda="0.025"/>
	<channelLengthCoefficientWeakInversion lamda="0.06"/>
	<minArea Amin="12"/>
	<minLength Lmin="1"/>
	<minWidth Wmin="1"/>
</pmos>
"""
	path = tmp_path / "missing_attr.xml"
	path.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Missing attribute 'vth'"):
		TechnologyParams.from_file(path)

def test_technology_parser_missing_thermal_voltage_element_raises(tmp_path) -> None:
	"""Missing <thermalVoltage> element inside <general> must raise KeyError."""
	xml = """\
<general>
</general>
<nmos><thresholdVoltage vth="0.4"/></nmos>
<pmos><thresholdVoltage vth="-0.6"/></pmos>
"""
	path = tmp_path / "no_vt_elem.xml"
	path.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Missing <thermalVoltage>"):
		TechnologyParams.from_file(path)

def test_technology_parser_missing_vt_attribute_raises(tmp_path) -> None:
	"""<thermalVoltage> present but 'Vt' attribute absent must raise KeyError."""
	xml = """\
<general>
	<thermalVoltage wrongAttr="0.026"/>
</general>
<nmos><thresholdVoltage vth="0.4"/></nmos>
<pmos><thresholdVoltage vth="-0.6"/></pmos>
"""
	path = tmp_path / "no_vt_attr.xml"
	path.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Missing 'Vt' attribute"):
		TechnologyParams.from_file(path)

def test_technology_parser_missing_pmos_raises(tmp_path) -> None:
	"""Missing <pmos> section must raise KeyError."""
	xml = """\
<general>
	<thermalVoltage Vt="0.026"/>
</general>
<nmos>
	<thresholdVoltage vth="0.4"/>
	<mobilityOxideCapacity muCox="0.0002"/>
	<earlyVoltage earlyVoltage="5.0"/>
	<overlapCapacity Cgdov="1e-10"/>
	<gateOxideCapacity Cox="0.007"/>
	<zeroBiasBulkJunctionCapacitance Cj="0.002"/>
	<zeroBiasSidewallBulkJunctionCapacitance Cjsw="5e-10"/>
	<bulkJunctionContactPotential pb="0.6"/>
	<lateralDiffusionLength Ldiff="1e-6"/>
	<slopeFactor n="1.5"/>
	<channelLengthCoefficientStrongInversion lamda="0.03"/>
	<channelLengthCoefficientWeakInversion lamda="0.08"/>
	<minArea Amin="8"/>
	<minLength Lmin="2"/>
	<minWidth Wmin="3"/>
</nmos>
"""
	path = tmp_path / "no_pmos.xml"
	path.write_text(xml, encoding="utf-8")
	with pytest.raises(KeyError, match="Missing <pmos>"):
		TechnologyParams.from_file(path)

def test_technology_parser_negative_and_small_values() -> None:
	"""Verify that negative (PMOS Vth) and very small (capacitance) values parse."""
	tech = TechnologyParams.from_file("tests/data/TechnologyFile.xml")

	# Negative threshold for PMOS
	assert tech.pmos.threshold_voltage < 0

	# Very small overlap capacitances (sub-nano range)
	assert tech.nmos.overlap_capacitance == 6.2e-10
	assert tech.pmos.overlap_capacitance == 6.66e-10
	assert tech.nmos.cjsw == 5.341e-10
	assert tech.pmos.cjsw == 3.626e-10

def test_technology_parser_dataclass_equality() -> None:
	"""Parsing the same file twice produces equal dataclass instances."""
	tech1 = TechnologyParams.from_file("tests/data/TechnologyFile.xml")
	tech2 = TechnologyParams.from_file("tests/data/TechnologyFile.xml")
	assert tech1 == tech2
	assert tech1.nmos == tech2.nmos
	assert tech1.pmos == tech2.pmos

# ── Circuit info parser tests ─────────────────────────────────────────────

def test_circuit_params_parses_reference_file() -> None:
	"""Full acceptance test: parse reference CircuitParameterAndSpecifications.xml."""
	p = parse_circuit_parameters("tests/data/CircuitParameterAndSpecifications.xml")

	assert p.load_capacities == [("cl", 20.0)]
	assert p.supply_voltage == ("vdd!", 5.0)
	assert p.ground == ("gnd!", 0.0)
	assert p.bias_current == ("ibias", 10.0)
	assert p.input_plus == ("inp", 2.5)
	assert p.input_minus == ("inn", 2.5)
	assert p.output_net == "out"

def test_circuit_params_load_capacities_multiple(tmp_path) -> None:
	"""Multiple <LoadCapacity> entries are collected in order."""
	xml = """\
<CircuitParameter>
	<LoadCapacities>
		<LoadCapacity><Value>10</Value><DeviceName>c1</DeviceName></LoadCapacity>
		<LoadCapacity><Value>20</Value><DeviceName>c2</DeviceName></LoadCapacity>
		<LoadCapacity><Value>30</Value><DeviceName>c3</DeviceName></LoadCapacity>
	</LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="3.3"/><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="5"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="1.0"/><NetName>inm</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="1.0"/><NetName>inp</NetName></InputPinPlus>
	<OutputPin><NetName>out</NetName></OutputPin>
</CircuitParameter>
<Specifications>
	<minimumGain A="0"/><minimumTransientFrequency ft="0"/>
	<maximumSlewRate SR="0"/><minimumCMRR CMRR="0"/>
	<minimumPosPSRR posPSRR="0"/><minimumNegPSRR negPSRR="0"/>
	<OutputVoltageSwing Voutmax="0" Voutmin="0"/>
	<CommonModeInputVoltage Vcmmin="0" Vcmmax="0"/>
	<GateOverDriveVoltage Vover="0"/><maximumPowerConsumption P="0"/>
	<maximumArea Area="0"/><phaseMargin PM="0"/>
</Specifications>
"""
	path = tmp_path / "multi_cap.xml"
	path.write_text(xml, encoding="utf-8")

	p = parse_circuit_parameters(path)
	assert p.load_capacities == [("c1", 10.0), ("c2", 20.0), ("c3", 30.0)]
	assert p.supply_voltage == ("vdd", 3.3)

def test_circuit_params_no_load_capacities(tmp_path) -> None:
	"""Empty <LoadCapacities> section produces an empty list."""
	xml = """\
<CircuitParameter>
	<LoadCapacities></LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="1.8"/><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="1"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0.9"/><NetName>in-</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0.9"/><NetName>in+</NetName></InputPinPlus>
	<OutputPin><NetName>o</NetName></OutputPin>
</CircuitParameter>
<Specifications>
	<minimumGain A="0"/><minimumTransientFrequency ft="0"/>
	<maximumSlewRate SR="0"/><minimumCMRR CMRR="0"/>
	<minimumPosPSRR posPSRR="0"/><minimumNegPSRR negPSRR="0"/>
	<OutputVoltageSwing Voutmax="0" Voutmin="0"/>
	<CommonModeInputVoltage Vcmmin="0" Vcmmax="0"/>
	<GateOverDriveVoltage Vover="0"/><maximumPowerConsumption P="0"/>
	<maximumArea Area="0"/><phaseMargin PM="0"/>
</Specifications>
"""
	path = tmp_path / "no_cap.xml"
	path.write_text(xml, encoding="utf-8")

	p = parse_circuit_parameters(path)
	assert p.load_capacities == []

def test_circuit_params_whitespace_in_attributes() -> None:
	"""The reference file has `Vin= "2.5"` and `P ="10"` — spaces handled."""
	p = parse_circuit_parameters("tests/data/CircuitParameterAndSpecifications.xml")
	# InputPinPlus has Vin= "2.5" (space before quote)
	assert p.input_plus == ("inp", 2.5)

def test_circuit_params_missing_section_raises(tmp_path) -> None:
	"""XML without <CircuitParameter> raises KeyError."""
	xml = '<Specifications><minimumGain A="0"/></Specifications>'
	path = tmp_path / "no_cp.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <CircuitParameter>"):
		parse_circuit_parameters(path)

def test_circuit_params_missing_pin_section_raises(tmp_path) -> None:
	"""Missing a required pin section raises KeyError."""
	xml = """\
<CircuitParameter>
	<LoadCapacities></LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="1"/><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<!-- CurrentBiasPin intentionally omitted -->
	<InputPinMinus><InputVoltage Vin="0"/><NetName>im</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0"/><NetName>ip</NetName></InputPinPlus>
	<OutputPin><NetName>out</NetName></OutputPin>
</CircuitParameter>
"""
	path = tmp_path / "no_bias.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <CurrentBiasPin>"):
		parse_circuit_parameters(path)

def test_circuit_params_missing_attribute_raises(tmp_path) -> None:
	"""Pin value element without expected attribute raises KeyError."""
	xml = """\
<CircuitParameter>
	<LoadCapacities></LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage WrongAttr="1"/><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="1"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0"/><NetName>im</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0"/><NetName>ip</NetName></InputPinPlus>
	<OutputPin><NetName>out</NetName></OutputPin>
</CircuitParameter>
"""
	path = tmp_path / "bad_attr.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing attribute 'Vdd'"):
		parse_circuit_parameters(path)

def test_specifications_parses_reference_file() -> None:
	"""Full acceptance test: all 14 sizing fields from the reference file."""
	s = parse_specifications("tests/data/CircuitParameterAndSpecifications.xml")

	assert s.min_gain == 80.0
	assert s.min_transit_freq == 2.75
	assert s.max_slew_rate == 3.5
	assert s.min_cmrr == 0.0
	assert s.min_pos_psrr == 0.0
	assert s.min_neg_psrr == 0.0
	assert s.vout_max == 3.0
	assert s.vout_min == 1.0
	assert s.vcm_max == 0.5
	assert s.vcm_min == -0.5
	assert s.gate_overdrive == 0.13
	assert s.max_power == 10.0
	assert s.max_area == 15000.0
	assert s.phase_margin == 60.0

def test_specifications_synthesis_fields_none_for_sizing() -> None:
	"""Sizing file has no synthesis-only fields — all should be None."""
	s = parse_specifications("tests/data/CircuitParameterAndSpecifications.xml")

	assert s.complementary is None
	assert s.fully_differential is None
	assert s.settling_time is None
	assert s.offset_error_min is None
	assert s.offset_error_max is None

def test_specifications_synthesis_file(tmp_path) -> None:
	"""Synthetic synthesis file: all fields including synthesis-only."""
	xml = """\
<Specifications>
	<minimumGain A="60"/>
	<minimumTransientFrequency ft="1.5"/>
	<maximumSlewRate SR="2.0"/>
	<minimumCMRR CMRR="50"/>
	<minimumPosPSRR posPSRR="40"/>
	<minimumNegPSRR negPSRR="35"/>
	<OutputVoltageSwing Voutmax="4.0" Voutmin="0.5"/>
	<CommonModeInputVoltage Vcmmin="-1.0" Vcmmax="1.0"/>
	<GateOverDriveVoltage Vover="0.2"/>
	<maximumPowerConsumption P="5"/>
	<maximumArea Area="10000"/>
	<phaseMargin PM="45"/>
	<complementary>yes</complementary>
	<fullyDifferential>no</fullyDifferential>
	<settlingTime ts="12.5"/>
	<OffsetError Vmin="-3.0" Vmax="3.0"/>
</Specifications>
"""
	path = tmp_path / "synth_specs.xml"
	path.write_text(xml, encoding="utf-8")

	s = parse_specifications(path)

	# Core fields
	assert s.min_gain == 60.0
	assert s.min_transit_freq == 1.5
	assert s.max_slew_rate == 2.0
	assert s.min_cmrr == 50.0
	assert s.min_pos_psrr == 40.0
	assert s.min_neg_psrr == 35.0
	assert s.vout_max == 4.0
	assert s.vout_min == 0.5
	assert s.vcm_max == 1.0
	assert s.vcm_min == -1.0
	assert s.gate_overdrive == 0.2
	assert s.max_power == 5.0
	assert s.max_area == 10000.0
	assert s.phase_margin == 45.0

	# Synthesis-only fields
	assert s.complementary is True
	assert s.fully_differential is False
	assert s.settling_time == 12.5
	assert s.offset_error_min == -3.0
	assert s.offset_error_max == 3.0

def test_specifications_negative_and_zero_values(tmp_path) -> None:
	"""Negative voltages and zero specs parse correctly."""
	xml = """\
<Specifications>
	<minimumGain A="0"/>
	<minimumTransientFrequency ft="0"/>
	<maximumSlewRate SR="0"/>
	<minimumCMRR CMRR="0"/>
	<minimumPosPSRR posPSRR="0"/>
	<minimumNegPSRR negPSRR="0"/>
	<OutputVoltageSwing Voutmax="0" Voutmin="-2.5"/>
	<CommonModeInputVoltage Vcmmin="-3.0" Vcmmax="-0.1"/>
	<GateOverDriveVoltage Vover="0"/>
	<maximumPowerConsumption P="0"/>
	<maximumArea Area="0"/>
	<phaseMargin PM="0"/>
</Specifications>
"""
	path = tmp_path / "zero_specs.xml"
	path.write_text(xml, encoding="utf-8")

	s = parse_specifications(path)
	assert s.min_gain == 0.0
	assert s.vout_min == -2.5
	assert s.vcm_min == -3.0
	assert s.vcm_max == -0.1

def test_specifications_missing_section_raises(tmp_path) -> None:
	"""XML without <Specifications> raises KeyError."""
	xml = """\
<CircuitParameter>
	<LoadCapacities></LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="1"/><NetName>v</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>g</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="1"/><NetName>b</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0"/><NetName>m</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0"/><NetName>p</NetName></InputPinPlus>
	<OutputPin><NetName>o</NetName></OutputPin>
</CircuitParameter>
"""
	path = tmp_path / "no_specs.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <Specifications>"):
		parse_specifications(path)

def test_specifications_missing_element_raises(tmp_path) -> None:
	"""Missing a required spec element raises KeyError."""
	xml = """\
<Specifications>
	<minimumGain A="80"/>
	<!-- minimumTransientFrequency intentionally omitted -->
	<maximumSlewRate SR="3.5"/>
	<minimumCMRR CMRR="0"/>
	<minimumPosPSRR posPSRR="0"/>
	<minimumNegPSRR negPSRR="0"/>
	<OutputVoltageSwing Voutmax="3" Voutmin="1"/>
	<CommonModeInputVoltage Vcmmin="0" Vcmmax="0"/>
	<GateOverDriveVoltage Vover="0"/>
	<maximumPowerConsumption P="0"/>
	<maximumArea Area="0"/>
	<phaseMargin PM="0"/>
</Specifications>
"""
	path = tmp_path / "missing_ft.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <minimumTransientFrequency>"):
		parse_specifications(path)

def test_specifications_missing_attribute_raises(tmp_path) -> None:
	"""Element present but wrong attribute raises KeyError."""
	xml = """\
<Specifications>
	<minimumGain WrongAttr="80"/>
	<minimumTransientFrequency ft="0"/>
	<maximumSlewRate SR="0"/>
	<minimumCMRR CMRR="0"/>
	<minimumPosPSRR posPSRR="0"/>
	<minimumNegPSRR negPSRR="0"/>
	<OutputVoltageSwing Voutmax="0" Voutmin="0"/>
	<CommonModeInputVoltage Vcmmin="0" Vcmmax="0"/>
	<GateOverDriveVoltage Vover="0"/>
	<maximumPowerConsumption P="0"/>
	<maximumArea Area="0"/>
	<phaseMargin PM="0"/>
</Specifications>
"""
	path = tmp_path / "bad_gain_attr.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing attribute 'A'"):
		parse_specifications(path)

def test_specifications_missing_dual_attribute_raises(tmp_path) -> None:
	"""Dual-attribute element with one missing attr raises KeyError."""
	xml = """\
<Specifications>
	<minimumGain A="0"/>
	<minimumTransientFrequency ft="0"/>
	<maximumSlewRate SR="0"/>
	<minimumCMRR CMRR="0"/>
	<minimumPosPSRR posPSRR="0"/>
	<minimumNegPSRR negPSRR="0"/>
	<OutputVoltageSwing Voutmax="3"/>
	<CommonModeInputVoltage Vcmmin="0" Vcmmax="0"/>
	<GateOverDriveVoltage Vover="0"/>
	<maximumPowerConsumption P="0"/>
	<maximumArea Area="0"/>
	<phaseMargin PM="0"/>
</Specifications>
"""
	path = tmp_path / "missing_voutmin.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing attribute 'Voutmin'"):
		parse_specifications(path)

def test_specifications_triple_dash_comments(tmp_path) -> None:
	"""Files with triple-dash comments parse after repair."""
	xml = """\
<Specifications>
	<minimumGain A="99"/><!--- [dB] --->
	<minimumTransientFrequency ft="1"/><!--- [MHz] --->
	<maximumSlewRate SR="2"/>
	<minimumCMRR CMRR="0"/>
	<minimumPosPSRR posPSRR="0"/>
	<minimumNegPSRR negPSRR="0"/>
	<OutputVoltageSwing Voutmax="0" Voutmin="0"/>
	<CommonModeInputVoltage Vcmmin="0" Vcmmax="0"/>
	<GateOverDriveVoltage Vover="0"/>
	<maximumPowerConsumption P="0"/>
	<maximumArea Area="0"/>
	<phaseMargin PM="0"/>
</Specifications>
"""
	path = tmp_path / "triple_dash.xml"
	path.write_text(xml, encoding="utf-8")

	s = parse_specifications(path)
	assert s.min_gain == 99.0
	assert s.min_transit_freq == 1.0

def test_load_circuit_information_integrates() -> None:
	"""End-to-end: load_circuit_information combines params, specs, and tech."""
	ci = load_circuit_information(
		"tests/data/CircuitParameterAndSpecifications.xml",
		"tests/data/TechnologyFile.xml",
	)

	assert isinstance(ci, CircuitInformation)
	assert isinstance(ci.parameters, CircuitParameter)
	assert isinstance(ci.specifications, Specifications)
	assert isinstance(ci.technology, TechnologyParams)

	# Spot-check one field from each sub-object
	assert ci.parameters.supply_voltage == ("vdd!", 5.0)
	assert ci.specifications.min_gain == 80.0
	assert ci.technology.nmos.threshold_voltage == 0.405

def test_circuit_params_dataclass_equality() -> None:
	"""Parsing the same file twice produces equal dataclass instances."""
	p1 = parse_circuit_parameters("tests/data/CircuitParameterAndSpecifications.xml")
	p2 = parse_circuit_parameters("tests/data/CircuitParameterAndSpecifications.xml")
	assert p1 == p2

def test_specifications_dataclass_equality() -> None:
	"""Parsing the same file twice produces equal Specifications."""
	s1 = parse_specifications("tests/data/CircuitParameterAndSpecifications.xml")
	s2 = parse_specifications("tests/data/CircuitParameterAndSpecifications.xml")
	assert s1 == s2

def test_circuit_info_dataclass_equality() -> None:
	"""Parsing the same files twice produces equal CircuitInformation."""
	ci1 = load_circuit_information(
		"tests/data/CircuitParameterAndSpecifications.xml",
		"tests/data/TechnologyFile.xml",
	)
	ci2 = load_circuit_information(
		"tests/data/CircuitParameterAndSpecifications.xml",
		"tests/data/TechnologyFile.xml",
	)
	assert ci1 == ci2


# ── Helpers ─────────────────────────────────────────────────────────────────


_VALID_CP = """\
<CircuitParameter>
	<LoadCapacities></LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="1.8"/><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="10"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0.9"/><NetName>inn</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0.9"/><NetName>inp</NetName></InputPinPlus>
	<OutputPin><NetName>out</NetName></OutputPin>
</CircuitParameter>
"""

_VALID_SPECS = """\
<Specifications>
	<minimumGain A="80"/>
	<minimumTransientFrequency ft="2.75"/>
	<maximumSlewRate SR="3.5"/>
	<minimumCMRR CMRR="0"/>
	<minimumPosPSRR posPSRR="0"/>
	<minimumNegPSRR negPSRR="0"/>
	<OutputVoltageSwing Voutmax="3" Voutmin="1"/>
	<CommonModeInputVoltage Vcmmin="-0.5" Vcmmax="0.5"/>
	<GateOverDriveVoltage Vover="0.13"/>
	<maximumPowerConsumption P="10"/>
	<maximumArea Area="15000"/>
	<phaseMargin PM="60"/>
</Specifications>
"""


# ── circuit_info_parser.py: missing-line coverage ────────────────────────────


def test_circuit_params_missing_netname_in_pin_section_raises(tmp_path) -> None:
	"""<NetName> absent inside an existing pin section hits line 193."""
	# SupplyVoltagePin exists but has no <NetName> child
	xml = """\
<CircuitParameter>
	<LoadCapacities></LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="1.8"/></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="10"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0.9"/><NetName>inn</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0.9"/><NetName>inp</NetName></InputPinPlus>
	<OutputPin><NetName>out</NetName></OutputPin>
</CircuitParameter>
"""
	path = tmp_path / "no_netname.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <NetName> in <SupplyVoltagePin>"):
		parse_circuit_parameters(path)


def test_circuit_params_missing_value_element_in_pin_section_raises(tmp_path) -> None:
	"""Value element absent inside an existing pin section hits line 196."""
	# SupplyVoltagePin has <NetName> but no <SupplyVoltage> element
	xml = """\
<CircuitParameter>
	<LoadCapacities></LoadCapacities>
	<SupplyVoltagePin><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="10"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0.9"/><NetName>inn</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0.9"/><NetName>inp</NetName></InputPinPlus>
	<OutputPin><NetName>out</NetName></OutputPin>
</CircuitParameter>
"""
	path = tmp_path / "no_voltage_elem.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <SupplyVoltage> in <SupplyVoltagePin>"):
		parse_circuit_parameters(path)


def test_circuit_params_load_capacity_missing_device_name_raises(tmp_path) -> None:
	"""<LoadCapacity> without <DeviceName> hits line 264."""
	xml = """\
<CircuitParameter>
	<LoadCapacities>
		<LoadCapacity><Value>20</Value></LoadCapacity>
	</LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="1.8"/><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="10"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0.9"/><NetName>inn</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0.9"/><NetName>inp</NetName></InputPinPlus>
	<OutputPin><NetName>out</NetName></OutputPin>
</CircuitParameter>
"""
	path = tmp_path / "no_device_name.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <DeviceName> in <LoadCapacity>"):
		parse_circuit_parameters(path)


def test_circuit_params_load_capacity_missing_value_raises(tmp_path) -> None:
	"""<LoadCapacity> without <Value> hits line 266."""
	xml = """\
<CircuitParameter>
	<LoadCapacities>
		<LoadCapacity><DeviceName>cl</DeviceName></LoadCapacity>
	</LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="1.8"/><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="10"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0.9"/><NetName>inn</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0.9"/><NetName>inp</NetName></InputPinPlus>
	<OutputPin><NetName>out</NetName></OutputPin>
</CircuitParameter>
"""
	path = tmp_path / "no_value.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <Value> in <LoadCapacity>"):
		parse_circuit_parameters(path)


def test_circuit_params_missing_output_pin_section_raises(tmp_path) -> None:
	"""No <OutputPin> element at all hits line 281."""
	xml = """\
<CircuitParameter>
	<LoadCapacities></LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="1.8"/><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="10"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0.9"/><NetName>inn</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0.9"/><NetName>inp</NetName></InputPinPlus>
</CircuitParameter>
"""
	path = tmp_path / "no_output_pin.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <OutputPin> in <CircuitParameter>"):
		parse_circuit_parameters(path)


def test_circuit_params_output_pin_missing_netname_raises(tmp_path) -> None:
	"""<OutputPin> exists but has no <NetName> child hits line 284."""
	xml = """\
<CircuitParameter>
	<LoadCapacities></LoadCapacities>
	<SupplyVoltagePin><SupplyVoltage Vdd="1.8"/><NetName>vdd</NetName></SupplyVoltagePin>
	<GroundPin><GroundVoltage Gnd="0"/><NetName>gnd</NetName></GroundPin>
	<CurrentBiasPin><BiasCurrent Ibias="10"/><NetName>ib</NetName></CurrentBiasPin>
	<InputPinMinus><InputVoltage Vin="0.9"/><NetName>inn</NetName></InputPinMinus>
	<InputPinPlus><InputVoltage Vin="0.9"/><NetName>inp</NetName></InputPinPlus>
	<OutputPin></OutputPin>
</CircuitParameter>
"""
	path = tmp_path / "output_pin_no_netname.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <NetName> in <OutputPin>"):
		parse_circuit_parameters(path)


def test_specifications_missing_dual_element_raises(tmp_path) -> None:
	"""A dual-attribute element (OutputVoltageSwing) entirely absent hits line 341."""
	xml = """\
<Specifications>
	<minimumGain A="80"/>
	<minimumTransientFrequency ft="2.75"/>
	<maximumSlewRate SR="3.5"/>
	<minimumCMRR CMRR="0"/>
	<minimumPosPSRR posPSRR="0"/>
	<minimumNegPSRR negPSRR="0"/>
	<!-- OutputVoltageSwing intentionally omitted -->
	<CommonModeInputVoltage Vcmmin="-0.5" Vcmmax="0.5"/>
	<GateOverDriveVoltage Vover="0.13"/>
	<maximumPowerConsumption P="10"/>
	<maximumArea Area="15000"/>
	<phaseMargin PM="60"/>
</Specifications>
"""
	path = tmp_path / "missing_swing.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing <OutputVoltageSwing> in <Specifications>"):
		parse_specifications(path)


def test_specifications_settling_time_missing_ts_raises(tmp_path) -> None:
	"""<settlingTime> present but without 'ts' attribute hits line 364."""
	xml = _VALID_SPECS.rstrip() + "\n\t<settlingTime/>\n</Specifications>\n"
	# Replace the closing tag that's already in _VALID_SPECS
	xml = _VALID_SPECS.replace("</Specifications>", "<settlingTime/>\n</Specifications>")
	path = tmp_path / "no_ts.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing attribute 'ts' on <settlingTime>"):
		parse_specifications(path)


def test_specifications_offset_error_missing_vmin_vmax_raises(tmp_path) -> None:
	"""<OffsetError> present but without Vmin/Vmax attributes hits line 374."""
	xml = _VALID_SPECS.replace("</Specifications>", "<OffsetError/>\n</Specifications>")
	path = tmp_path / "no_offset_attrs.xml"
	path.write_text(xml, encoding="utf-8")

	with pytest.raises(KeyError, match="Missing 'Vmin' or 'Vmax' on <OffsetError>"):
		parse_specifications(path)

# ── Additional coverage for error paths and edge cases ──────────────────

def test_load_device_types_empty_name_skipped(tmp_path) -> None:
	"""Empty deviceType name should be skipped (line 70: continue)."""
	xml = """
<deviceTypes>
	<deviceType name="">
		<techTypes><techType>n</techType></techTypes>
		<pinTypes><pinType>Drain</pinType></pinTypes>
	</deviceType>
	<deviceType name="Mosfet">
		<techTypes><techType>n</techType></techTypes>
		<pinTypes><pinType>Drain</pinType></pinTypes>
	</deviceType>
</deviceTypes>
"""
	file = tmp_path / "empty_name.xcat"
	file.write_text(xml, encoding="utf-8")
	
	register = load_device_types(file)
	# Only Mosfet should be registered
	assert register.get_pin_types(DeviceType.MOSFET) is not None



def test_load_device_types_unknown_device_type_raises(tmp_path) -> None:
    """name not in DeviceType enum → lines 74-75."""
    xml = """<deviceTypes>
    <deviceType name="UnknownGadget">
        <techTypes><techType>n</techType></techTypes>
        <pinTypes><pinType>Drain</pinType></pinTypes>
    </deviceType>
</deviceTypes>"""
    f = tmp_path / "t.xcat"
    f.write_text(xml)
    with pytest.raises(KeyError, match="Unknown device type name in XML"):
        load_device_types(f)


def test_load_device_types_empty_tech_type_skipped(tmp_path) -> None:
    """Empty <techType> text → line 81 continue."""
    xml = """<deviceTypes>
    <deviceType name="Mosfet">
        <techTypes><techType>  </techType><techType>n</techType></techTypes>
        <pinTypes><pinType>Drain</pinType></pinTypes>
    </deviceType>
</deviceTypes>"""
    f = tmp_path / "t.xcat"
    f.write_text(xml)
    register = load_device_types(f)
    assert register.get_tech_types(DeviceType.MOSFET) == [TechType.N]


def test_load_device_types_unknown_tech_type_raises(tmp_path) -> None:
    """Unknown TechType text → lines 84-85."""
    xml = """<deviceTypes>
    <deviceType name="Mosfet">
        <techTypes><techType>bad_tech</techType></techTypes>
        <pinTypes><pinType>Drain</pinType></pinTypes>
    </deviceType>
</deviceTypes>"""
    f = tmp_path / "t.xcat"
    f.write_text(xml)
    with pytest.raises(KeyError, match="Unknown tech type"):
        load_device_types(f)


def test_load_device_types_empty_pin_text_skipped(tmp_path) -> None:
    """Empty <pinType> text → line 93 continue."""
    xml = """<deviceTypes>
    <deviceType name="Mosfet">
        <techTypes><techType>n</techType></techTypes>
        <pinTypes><pinType>  </pinType><pinType>Drain</pinType></pinTypes>
    </deviceType>
</deviceTypes>"""
    f = tmp_path / "t.xcat"
    f.write_text(xml)
    register = load_device_types(f)
    pins = register.get_pin_types(DeviceType.MOSFET)
    assert len(pins) == 1 and pins[0].pin_type == PinType.DRAIN


def test_load_device_types_unknown_auto_connection_raises(tmp_path) -> None:
    """autoConnection value not in PinType enum → lines 108-109."""
    xml = """<deviceTypes>
    <deviceType name="Mosfet">
        <techTypes><techType>n</techType></techTypes>
        <pinTypes>
            <pinType autoConnection="BadPinType">Drain</pinType>
        </pinTypes>
    </deviceType>
</deviceTypes>"""
    f = tmp_path / "t.xcat"
    f.write_text(xml)
    with pytest.raises(KeyError, match="Unknown autoConnection pin type"):
        load_device_types(f)
