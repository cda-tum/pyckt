"""Tests for the structure recognition library loader.

Verifies that the XML library data is parsed correctly into
Python dataclasses, covering:
  - Library loading (master, array, pair)
  - Item counts and active-item lists
  - Array item fields (connections, rules, parallel nets)
  - Pair item fields (symmetry, helper, characteristic, tech-type)
  - Hierarchy levels and persistence values
  - Dominance relations (regular + current-mirror)
"""

from pathlib import Path

import pytest

from recognition.library import (
    _DEFAULT_LIB_DIR,
    PERSISTENCE_MAX,
    ArrayLibrary,
    DevicePinType,
    HierarchyEntry,
    Library,
    PairLibrary,
    StructurePinType,
)

# ── Shared fixtures ────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def library() -> Library:
    """Load the full library once for all tests in this module."""
    return Library.from_directory()


@pytest.fixture(scope="module")
def array_lib(library: Library) -> ArrayLibrary:
    return library.array_library


@pytest.fixture(scope="module")
def pair_lib(library: Library) -> PairLibrary:
    return library.pair_library


# ═══════════════════════════════════════════════════════════════════════
#  Library loading
# ═══════════════════════════════════════════════════════════════════════


class TestLibraryLoading:
    def test_loading_paths(self, library: Library):
        """Default, Path, and str arguments all load non-empty libraries."""
        assert library.array_library is not None
        assert library.pair_library is not None
        lib_path = Library.from_directory(_DEFAULT_LIB_DIR)
        lib_str  = Library.from_directory(str(_DEFAULT_LIB_DIR))
        assert len(lib_path.array_library) > 0
        assert len(lib_str.array_library) > 0

    def test_repr(self, library: Library):
        r = repr(library)
        assert "ArrayLibrary" in r
        assert "PairLibrary" in r

    def test_missing_directory_raises(self):
        with pytest.raises(FileNotFoundError, match="/nonexistent/path"):
            Library.from_directory("/nonexistent/path")

    # ── issue #47: acst wrapper-file form of --library ────────────────

    def test_wrapper_file_loads_same_as_directory(self, library: Library):
        """A wrapper file with any name (acst's Library.xml form) loads the
        same library as pointing at its directory."""
        fixture = (Path(__file__).parent / "data" / "inputs"
                   / "RuleGeneration" / "Library.xml")
        lib = Library.from_directory(fixture)
        assert len(lib.pair_library.items) == len(library.pair_library.items)
        assert len(lib.array_library) == len(library.array_library)

    def test_wrapper_file_with_absolute_references(self, tmp_path):
        """Wrapper references may be absolute paths."""
        wrapper = tmp_path / "MyLib.xml"
        wrapper.write_text(
            "<library>"
            "<arrayLibraries><arrayLibraryFile>"
            f"{_DEFAULT_LIB_DIR / 'Array' / 'ArrayLibrary.xml'}"
            "</arrayLibraryFile></arrayLibraries>"
            "<pairLibraries><pairLibraryFile>"
            f"{_DEFAULT_LIB_DIR / 'Analog' / 'AnalogLibrary.xml'}"
            "</pairLibraryFile></pairLibraries>"
            "</library>"
        )
        lib = Library.from_directory(wrapper)
        assert len(lib.pair_library.items) > 0

    def test_non_wrapper_file_raises_value_error(self, tmp_path):
        """A file without the library references fails with a clear error
        naming the file, instead of a puzzling downstream crash."""
        bogus = tmp_path / "NotALibrary.xml"
        bogus.write_text("<pairLibraryItem></pairLibraryItem>")
        with pytest.raises(ValueError, match="NotALibrary.xml"):
            Library.from_directory(bogus)


# ═══════════════════════════════════════════════════════════════════════
#  Array library
# ═══════════════════════════════════════════════════════════════════════


class TestArrayLibrary:
    def test_counts(self, array_lib: ArrayLibrary):
        """13 items total, 13 active; correct per-type split."""
        assert len(array_lib) == 13
        assert len(array_lib.active) == 13
        assert len([n for n in array_lib.items if n.startswith("Mosfet")]) == 5
        assert len([n for n in array_lib.items if n.startswith("Bipolar")]) == 4
        assert {"CapacitorArray", "ResistorArray", "DiodeArray", "InductorArray"}.issubset(
            array_lib.items.keys()
        )

    def test_active_names(self, array_lib: ArrayLibrary):
        names = array_lib.active_names
        for expected in ("MosfetNormalArray", "MosfetDiodeArray", "CapacitorArray",
                         "ResistorArray", "DiodeArray", "InductorArray"):
            assert expected in names

    def test_lookup(self, array_lib: ArrayLibrary):
        assert "MosfetNormalArray" in array_lib
        assert "FakeArray" not in array_lib
        with pytest.raises(KeyError):
            array_lib.get_item("NonexistentArray")


class TestArrayItems:
    def test_normal_array(self, array_lib: ArrayLibrary):
        item = array_lib.get_item("MosfetNormalArray")
        assert item.device_type_rule == "Mosfet"
        assert {c.structure_pin.pin_name for c in item.connections} == {"Drain", "Gate", "Source", "Bulk"}
        assert len(item.connection_rules) == 3
        assert all(not r.connected for r in item.connection_rules)
        assert {p.pin_name for p in item.parallel_nets} == {"Drain", "Source", "Gate"}

    def test_diode_array(self, array_lib: ArrayLibrary):
        item = array_lib.get_item("MosfetDiodeArray")
        # No Gate in arrayConnection (diode-connected via rule, not explicit pin)
        assert len(item.connections) == 3
        connected = [r for r in item.connection_rules if r.connected]
        assert len(connected) == 1
        assert connected[0].pin1.pin_name == "Drain"
        assert connected[0].pin2.pin_name == "Gate"

    def test_dummy_and_off_arrays(self, array_lib: ArrayLibrary):
        dummy = array_lib.get_item("MosfetDummyArray")
        assert len(dummy.connections) == 0
        assert all(r.connected for r in dummy.connection_rules)

        off = array_lib.get_item("MosfetOffArray")
        gs = [r for r in off.connection_rules if r.connected and r.pin1.pin_name == "Gate"]
        assert len(gs) == 1 and gs[0].pin2.pin_name == "Source"

    def test_passive_and_bipolar_arrays(self, array_lib: ArrayLibrary):
        cap = array_lib.get_item("CapacitorArray")
        assert cap.device_type_rule == "Capacitor"
        assert {c.structure_pin.pin_name for c in cap.connections} == {"Plus", "Minus"}

        res = array_lib.get_item("ResistorArray")
        assert res.device_type_rule == "Resistor"
        assert len(res.connections) == 2

        bip = array_lib.get_item("BipolarNormalArray")
        assert bip.device_type_rule == "Bipolar"
        assert {c.structure_pin.pin_name for c in bip.connections} == {"Base", "Emitter", "Collector"}


# ═══════════════════════════════════════════════════════════════════════
#  Pair library
# ═══════════════════════════════════════════════════════════════════════


class TestPairLibrary:
    def test_counts_and_levels(self, pair_lib: PairLibrary):
        # 52 originals + 4 FUBOCO-gallery composites (issue #31): the two
        # diode analog inverters at level 1, the two non-inverting inverters
        # at level 2.
        assert len(pair_lib) == 56
        assert pair_lib.hierarchy_levels == [1, 2, 3]
        assert len(pair_lib.get_level_entries(1)) == 23
        assert len(pair_lib.get_level_entries(2)) == 29
        assert len(pair_lib.get_level_entries(3)) == 4
        assert pair_lib.get_level_entries(99) == []

    def test_lookup(self, pair_lib: PairLibrary):
        assert "MosfetSimpleCurrentMirror" in pair_lib
        assert "FakePair" not in pair_lib
        with pytest.raises(KeyError):
            pair_lib.get_item("NonexistentPair")

    def test_dominance_counts(self, pair_lib: PairLibrary):
        assert len(pair_lib.dominance) == 6
        assert len([d for d in pair_lib.dominance if not d.for_current_mirrors]) == 3
        assert len([d for d in pair_lib.dominance if d.for_current_mirrors]) == 3


# ═══════════════════════════════════════════════════════════════════════
#  Pair items — spot checks
# ═══════════════════════════════════════════════════════════════════════


class TestPairItems:
    def test_scm(self, pair_lib: PairLibrary):
        item = pair_lib.get_item("MosfetSimpleCurrentMirror")
        assert item.symmetry is False
        assert item.is_helper_structure is False
        assert item.tech_type_rule == "same"
        assert {m.pair_pin.pin_name for m in item.connections} == {"Input", "Source", "Output"}
        cc = item.characteristic
        assert cc.first_child_pin == StructurePinType("MosfetDiodeArray", "Drain")
        assert cc.second_child_pins[0] == StructurePinType("MosfetNormalArray", "Gate")
        assert len([r for r in item.connection_rules if r.connected]) == 2
        assert len(item.net_rules) == 0

    def test_diff_pair(self, pair_lib: PairLibrary):
        item = pair_lib.get_item("MosfetDifferentialPair")
        assert item.symmetry is True
        assert item.tech_type_rule == "same"
        assert {m.pair_pin.pin_name for m in item.connections} == {
            "Input1", "Input2", "Output1", "Output2", "Source"
        }
        assert len(item.net_rules) == 2
        assert all(nr.supply == "no_supply" and nr.structure_pin.pin_name == "Source"
                   for nr in item.net_rules)
        cc = item.characteristic
        assert cc.first_child_pin.pin_name == "Source"
        assert cc.second_child_pins[0].pin_name == "Source"

    def test_helper_structure(self, pair_lib: PairLibrary):
        item = pair_lib.get_item("MosfetDifferentialStage")
        assert item.is_helper_structure is True
        assert item.tech_type_rule == "noRule"
        assert len(item.connection_rules) == 0
        names = {sp.structure_name for sp in item.characteristic.second_child_pins}
        assert "MosfetNormalArray" in names
        assert "BipolarNormalArray" in names

    def test_tech_type_rules(self, pair_lib: PairLibrary):
        """same / different / noRule all parsed correctly."""
        assert pair_lib.get_item("MosfetFoldedCascodeDifferentialPair").tech_type_rule == "different"
        assert pair_lib.get_item("ResistorRow").tech_type_rule == "noRule"
        assert pair_lib.get_item("MosfetCascodeCurrentMirror").tech_type_rule == "same"

    def test_twoport_characteristics(self, pair_lib: PairLibrary):
        rr = pair_lib.get_item("ResistorRow")
        assert rr.symmetry is False
        assert rr.characteristic.first_child_pin.structure_name == "ResistorArray"
        assert rr.characteristic.second_child_pins[0].structure_name == "ResistorArray"

        cmsd = pair_lib.get_item("CommonModeSignalDetector")
        assert cmsd.characteristic.first_child_pin.structure_name == "CapacitorRow"
        assert cmsd.characteristic.second_child_pins[0].structure_name == "ResistorRow"

    def test_cascode_cm_connections(self, pair_lib: PairLibrary):
        item = pair_lib.get_item("MosfetCascodeCurrentMirror")
        assert item.symmetry is False
        assert len(item.connections) == 5


# ═══════════════════════════════════════════════════════════════════════
#  Hierarchy entries and persistence
# ═══════════════════════════════════════════════════════════════════════


class TestHierarchyEntries:
    def test_persistence_values(self, pair_lib: PairLibrary):
        """Level-1 entries carry correct persistence values."""
        entries = {e.name: e.persistence for e in pair_lib.get_level_entries(1)}
        assert entries["MosfetSimpleCurrentMirror"] == PERSISTENCE_MAX
        assert entries["MosfetCascodePair"] == 1
        assert entries["MosfetDifferentialPair"] == 2

    def test_persistence_by_level(self, pair_lib: PairLibrary, library: Library):
        """Level 3 and arrays are all permanent; level 2 is mixed."""
        assert all(e.persistence == PERSISTENCE_MAX for e in pair_lib.get_level_entries(3))
        p_vals = {e.persistence for e in pair_lib.get_level_entries(2)}
        assert PERSISTENCE_MAX in p_vals
        assert 1 in p_vals
        assert all(e.persistence == PERSISTENCE_MAX for e in library.array_library.active)


# ═══════════════════════════════════════════════════════════════════════
#  Dominance relations
# ═══════════════════════════════════════════════════════════════════════


class TestDominanceRelations:
    def test_general_dominance(self, pair_lib: PairLibrary):
        by_dom = {
            tuple(sorted(d.dominating)): d
            for d in pair_lib.dominance if not d.for_current_mirrors
        }
        xcp = by_dom[("MosfetCrossCoupledPair",)]
        assert "MosfetSimpleCurrentMirror" in xcp.dominated
        assert "MosfetCascodePair" in xcp.dominated
        assert len(xcp.dominated) == 6

        dp = by_dom[("MosfetDifferentialPair",)]
        assert "MosfetCascodedAnalogInverter" in dp.dominated

        bxcp = next(d for d in pair_lib.dominance if "BipolarCrossCoupledPair" in d.dominating)
        assert "BipolarSimpleCurrentMirror" in bxcp.dominated
        assert len(bxcp.dominated) == 4

    def test_cm_dominance(self, pair_lib: PairLibrary):
        cm = {
            tuple(sorted(d.dominating)): d
            for d in pair_lib.dominance if d.for_current_mirrors
        }
        cascode = cm[("MosfetCascodeCurrentMirror",)]
        assert "MosfetWideSwingCurrentMirror" in cascode.dominated
        assert "MosfetSimpleCurrentMirror" in cascode.dominated

        wilson = cm[("MosfetImprovedWilsonCurrentMirror", "MosfetWilsonCurrentMirror")]
        assert len(wilson.dominating) == 2

        wsc = cm[("MosfetWideSwingCascodeCurrentMirror",)]
        assert "MosfetWideSwingCurrentMirror" in wsc.dominated


# ═══════════════════════════════════════════════════════════════════════
#  Dataclass basics
# ═══════════════════════════════════════════════════════════════════════


class TestMissingBranches:
    """Targeted tests for previously uncovered branches."""

    def test_text_helper_none_text(self):
        """_text() returns '' when elem.text is None (library.py line 374)."""
        import xml.etree.ElementTree as ET

        from recognition.library import _text
        elem = ET.fromstring("<item/>")
        assert elem.text is None
        assert _text(elem) == ""

    def test_persistence_fallback_child_element(self, tmp_path):
        """pairLibraryItem with <persistence> child element (not attribute) is parsed (line 719)."""

        from recognition.library import PairLibrary

        # Minimal AnalogLibrary.xml with child-element persistence form
        xml = """\
<AnalogLibrary>
  <hierarchyLevels>
    <hierarchyLevel level="1">
      <pairLibraryItem></pairLibraryItem>
      <pairLibraryItem>MyPair<persistence>3</persistence></pairLibraryItem>
    </hierarchyLevel>
  </hierarchyLevels>
</AnalogLibrary>
"""
        analog_dir = tmp_path / "Analog"
        analog_dir.mkdir()
        (analog_dir / "AnalogLibrary.xml").write_text(xml)
        lib = PairLibrary.from_xml(analog_dir)
        entries = lib.get_level_entries(1)
        assert len(entries) == 1
        assert entries[0].name == "MyPair"
        assert entries[0].persistence == 3


class TestDataclasses:
    def test_structure_pin_type(self):
        a = StructurePinType("MosfetNormalArray", "Drain")
        b = StructurePinType("MosfetNormalArray", "Drain")
        assert a == b
        assert hash(a) == hash(b)
        assert len({a, b}) == 1
        with pytest.raises(AttributeError):
            a.pin_name = "Gate"

    def test_other_dataclasses(self):
        dp = DevicePinType("Mosfet", "Gate")
        with pytest.raises(AttributeError):
            dp.pin_name = "Drain"
        assert HierarchyEntry(name="Test").persistence == PERSISTENCE_MAX
