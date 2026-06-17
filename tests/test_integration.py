"""Integration test: .hspice → recognize → StructureCircuits → rules → XML.

Exercises the full pipeline from a real netlist through structure
recognition, rule generation, and XML output — the final Week 4
acceptance criterion.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pytest

from pyckt.io.device_types_parser import load_device_types
from pyckt.io.hspice_mapping import HSpiceMapping
from pyckt.io.hspice_parser import HSpiceParser
from pyckt.io.supply_nets_parser import SupplyNetConfig

from recognition.library import Library
from recognition.recognizer import StructureRecognizer
from recognition.rulegen import RuleGenerator
from recognition.writer import StructRecXMLWriter, RuleXMLWriter


# ── Fixtures ─────────────────────────────────────────────────────────

DATA = Path(__file__).resolve().parent / "data"


@pytest.fixture(scope="module")
def circuit():
    """Parse the cascoded-symmetrical-CMOS-OTA netlist."""
    device_types = load_device_types(DATA / "deviceTypes.xcat")
    mapping = HSpiceMapping.from_file(DATA / "HSpiceMapping.xcat")
    supply_nets = SupplyNetConfig.from_file(DATA / "supplyNets.xcat")
    return HSpiceParser(mapping, supply_nets, device_types).parse(
        DATA / "cascodedSymmetricalCMOSOTA.hspice"
    )


@pytest.fixture(scope="module")
def library():
    """Load the bundled structure recognition library."""
    return Library.from_directory()


@pytest.fixture(scope="module")
def result(circuit, library):
    """Run the full recognition pipeline."""
    return StructureRecognizer(library).recognize(circuit)


@pytest.fixture(scope="module")
def rules(result):
    """Generate sizing rules from the recognition result."""
    return RuleGenerator().generate(result)


# ── Circuit parsing sanity ───────────────────────────────────────────

class TestCircuitParsing:
    def test_device_count(self, circuit):
        assert len(circuit.mosfets) == 18
        assert len(circuit.capacitors) == 1

    def test_supply_classification(self, circuit):
        assert circuit.find_net("vdd!").is_vdd()
        assert circuit.find_net("gnd!").is_ground()


# ── Array recognition (Level 0) ─────────────────────────────────────

class TestArrayLevel:
    def test_total_arrays(self, result):
        """19 devices → 19 single-device arrays (each transistor in its own array)."""
        assert len(result.get_level(0).structures) == 19

    def test_array_types(self, result):
        names = Counter(s.name for s in result.get_level(0).structures)
        # 3 diode-connected NMOS (m8, m7 with gate==drain), plus PMOS diodes
        assert names["MosfetDiodeArray"] >= 3
        assert names["MosfetNormalArray"] >= 10
        assert names["CapacitorArray"] == 1


# ── Pair recognition (Level 1) ──────────────────────────────────────

class TestPairLevel:
    def test_pairs_found(self, result):
        """Level 1 should have at least 6 pair structures."""
        assert len(result.get_level(1).structures) >= 6

    def test_current_mirrors_found(self, result):
        mirrors = [s for s in result.get_level(1).structures
                   if "CurrentMirror" in s.name]
        assert len(mirrors) >= 2, f"Expected ≥2 current mirrors, got {len(mirrors)}"

    def test_diff_pair_found(self, result):
        dp = [s for s in result.get_level(1).structures
              if "DifferentialPair" in s.name]
        assert len(dp) == 1
        devs = sorted(d.name for d in dp[0].devices)
        assert devs == ["m3", "m4"]

    def test_diff_pair_is_nmos(self, result):
        dp = [s for s in result.get_level(1).structures
              if "DifferentialPair" in s.name][0]
        assert dp.tech_type.value == "n"

    def test_no_spurious_level_shifter(self, result):
        # §8c: the cascoded symmetrical OTA contains no level shifter. acst
        # recognises zero; the old greedy matcher produced a spurious one that
        # persistence-based pruning now correctly removes.
        ls = [s for lvl in result.hierarchy_levels
              for s in result.get_level(lvl).structures
              if "LevelShifter" in s.name]
        assert ls == []

    def test_cascode_pair_found(self, result):
        cp = [s for s in result.get_level(1).structures
              if "CascodePair" in s.name]
        assert len(cp) >= 1


# ── Overall pipeline properties ──────────────────────────────────────

class TestPipelineProperties:
    def test_total_structures(self, result):
        assert result.total_structures >= 25

    def test_all_mosfets_covered(self, result, circuit):
        """Every MOSFET should appear in at least one array."""
        recognized = set()
        for s in result.get_level(0).structures:
            for d in s.devices:
                recognized.add(d.name)
        mosfet_names = {d.name for d in circuit.mosfets}
        assert mosfet_names <= recognized


# ── Rule generation ──────────────────────────────────────────────────

class TestRuleGeneration:
    def test_rule_count(self, rules):
        assert len(rules) >= 8

    def test_mirror_has_equal_length_and_wl(self, rules):
        mirror_rules = [r for r in rules if "CurrentMirror" in r.structure_name]
        types = {r.rule_type for r in mirror_rules}
        assert "equal_length" in types
        assert "equal_wl" in types

    def test_diff_pair_has_matched(self, rules):
        dp_rules = [r for r in rules if "DifferentialPair" in r.structure_name]
        assert any(r.rule_type == "matched" for r in dp_rules)

    def test_m3_m4_matched(self, rules):
        matched = [r for r in rules if r.rule_type == "matched"]
        assert any(sorted(r.devices) == ["m3", "m4"] for r in matched)

    def test_m0_m8_mirror(self, rules):
        wl = [r for r in rules if r.rule_type == "equal_wl"]
        assert any(sorted(r.devices) == ["m0", "m8"] for r in wl)


# ── XML output ───────────────────────────────────────────────────────

class TestXMLOutput:
    def test_structrec_xml_roundtrip(self, result, tmp_path):
        out = tmp_path / "structrec.xml"
        StructRecXMLWriter().write(result, out)
        root = ET.parse(out).getroot()
        assert root.tag == "StructureRecognitionResult"
        structs = root.findall("Structure")
        assert len(structs) >= 6  # top-level structures

    def test_rules_xml_roundtrip(self, rules, tmp_path):
        out = tmp_path / "rules.xml"
        RuleXMLWriter().write(rules, out)
        root = ET.parse(out).getroot()
        assert root.tag == "SizingRules"
        assert len(root.findall("Rule")) == len(rules)

    def test_structrec_xml_has_diff_pair(self, result, tmp_path):
        out = tmp_path / "structrec.xml"
        StructRecXMLWriter().write(result, out)
        root = ET.parse(out).getroot()
        names = [s.get("name") for s in root.findall("Structure")]
        assert "MosfetDifferentialPair" in names
