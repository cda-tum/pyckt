"""Tests for §8e recognition-rule learning (acst-style rulegen artifact)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from recognition.rule_learning import RuleLearner
from recognition.writer import AcstPairLibraryWriter


def _recognise(inputs_dir):
    from pyckt.io.device_types_parser import load_device_types
    from pyckt.io.hspice_mapping import HSpiceMapping
    from pyckt.io.hspice_parser import HSpiceParser
    from pyckt.io.supply_nets_parser import SupplyNetConfig
    from recognition.library import Library
    from recognition.recognizer import StructureRecognizer

    base = inputs_dir / "RuleGeneration"
    dt = load_device_types(str(base / "deviceTypes.xcat"))
    mp = HSpiceMapping.from_file(str(base / "HSpiceMapping.xcat"))
    sn = SupplyNetConfig.from_file(str(base / "supplyNets.xcat"))
    ckt = HSpiceParser(mp, sn, dt).parse(str(base / "cascodedSymmetricalCMOSOTA.hspice"))
    return StructureRecognizer(Library.from_directory()).recognize(ckt)


# ── learner ────────────────────────────────────────────────────────────────


class TestRuleLearner:
    @pytest.fixture(scope="class")
    def library(self, inputs_dir):
        sc = _recognise(inputs_dir)
        return RuleLearner("SymmetricalCascodeOpAmp").learn(sc)

    def test_learns_a_hierarchy_of_composites(self, library):
        # acst learns 10 composite items for this op-amp; pyckt matches.
        assert len(library.items) == 10
        assert all(i.name.startswith("SymmetricalCascodeOpAmp") for i in library.items)

    def test_culminates_in_single_top_structure(self, library):
        levels = library.levels()
        top = max(levels)
        # the highest level holds exactly the whole op-amp (one learned item)
        assert len(levels[top]) == 1
        assert top >= 5

    def test_each_item_pairs_two_named_children(self, library):
        for item in library.items:
            assert item.child1_name and item.child2_name
            assert item.level == library_level_of_parent(library, item)

    def test_persistence_is_parent_minus_child_level(self, library):
        # a learned child's persistence equals (max parent level - its level)
        by_name = {i.name: i for i in library.items}
        for item in library.items:
            for child in (item.child1_name, item.child2_name):
                if child in by_name:
                    assert by_name[child].persistence is not None
                    assert by_name[child].persistence >= item.level - by_name[child].level


def library_level_of_parent(library, item):
    # the item's own level (helper for readability)
    return item.level


# ── writer ──────────────────────────────────────────────────────────────────


class TestAcstPairLibraryWriter:
    @pytest.fixture(scope="class")
    def written(self, inputs_dir, tmp_path_factory):
        sc = _recognise(inputs_dir)
        lib = RuleLearner("SymmetricalCascodeOpAmp").learn(sc)
        out = tmp_path_factory.mktemp("rulegen") / "SymmetricalCascodeOpAmpLibrary.xml"
        AcstPairLibraryWriter().write(lib, out)
        return out, lib

    def test_index_has_item_files_levels_and_dominance(self, written):
        out, lib = written
        root = ET.parse(out).getroot()
        assert root.tag == "pairLibrary"
        files = root.findall("pairLibraryItemFiles/pairLibraryItemFile")
        assert len(files) == len(lib.items)
        assert root.find("hierarchyLevels") is not None
        assert root.find("dominanceRelations") is not None

    def test_item_files_written_with_acst_schema(self, written):
        out, lib = written
        items_dir = out.parent / "Items"
        assert items_dir.is_dir()
        # the top item file exists and has the expected schema
        top = max(lib.levels())
        top_item = lib.levels()[top][0]
        item_xml = ET.parse(items_dir / f"{top_item.name}.xml").getroot()
        assert item_xml.tag == "pairLibraryItem"
        assert item_xml.findtext("structureName") == top_item.name
        assert item_xml.find("pairConnection") is not None
        assert item_xml.find("recognitionRules/connectionRules") is not None
        assert item_xml.find("recognitionRules/techTypeRule") is not None

    def test_pair_connection_pins_map_to_children(self, written):
        out, lib = written
        items_dir = out.parent / "Items"
        # pick a mid-hierarchy item with a pairConnection
        item = next(i for i in lib.items if i.pair_connection)
        xml = ET.parse(items_dir / f"{item.name}.xml").getroot()
        ppt = xml.find("pairConnection/pairPinType")
        assert ppt.find("structurePinType/structureName").text == item.name
        assert ppt.find("childPinType/childNumber").text in ("1", "2")


# ── analysis wiring ──────────────────────────────────────────────────────────


def test_rulegen_acst_format_emits_pairlibrary(inputs_dir, tmp_path):
    import argparse

    from recognition.analysis import RuleGenAnalysis

    src = inputs_dir / "RuleGeneration"
    out = tmp_path / "lib.xml"
    args = argparse.Namespace(
        circuit_netlist=str(src / "cascodedSymmetricalCMOSOTA.hspice"),
        device_types_file=str(src / "deviceTypes.xcat"),
        hspice_mapping_file=str(src / "HSpiceMapping.xcat"),
        hspice_supplynet_file=str(src / "supplyNets.xcat"),
        xml_structrec_library_file=None,
        output_file=str(out),
        output_format="acst",
        structure_name="SymmetricalCascodeOpAmp",
    )
    analysis = RuleGenAnalysis(args)
    analysis.initialize()
    analysis.compute()
    analysis.write()

    root = ET.parse(out).getroot()
    assert root.tag == "pairLibrary"
    assert (out.parent / "Items").is_dir()
