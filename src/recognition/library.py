"""Structure Recognition Library — XML loader and data model.

Parses the C++ StructRec XML library into Python dataclasses for use
by the recognition engine (Week 4).  The library defines templates for:

- **Arrays** (level 0): groups of identical devices (transistors,
  capacitors, resistors, etc.)
- **Pairs** (levels 1–3): matched structure pairs forming analog
  building blocks (current mirrors, differential pairs, …)

Each template describes:

1. *Connections* — how the structure's external pins map to
   device / child pins.
2. *Recognition rules* — connectivity constraints that must hold
   for a match.
3. *Characteristic connection* — the single defining inter-child
   link (pairs only).

The XML data originates from the C++ ACST project's ``StructRec/xml/``
tree and is shipped verbatim under ``data/structrec/``.

C++ reference
    ``StructRec/incl/Library/*.h``
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List

# ═══════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════

PERSISTENCE_MAX: int = -1
"""Sentinel value meaning *never pruned* — the structure persists
through all recognition phases regardless of how many higher-level
matches consume it."""

_DEFAULT_LIB_DIR: Path = (
    Path(__file__).resolve().parent.parent / "data" / "structrec"
)

# ═══════════════════════════════════════════════════════════════════════
#  Low-level pin / type references
# ═══════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class StructurePinType:
    """Typed reference to a pin on a named structure.

    Used throughout the library to specify which pin of which structure
    is being connected, constrained, or exposed.

    Attributes
    ----------
    structure_name : str
        Name of the owning structure (e.g. ``"MosfetNormalArray"``).
    pin_name : str
        Name of the pin (e.g. ``"Drain"``).
    """

    structure_name: str
    pin_name: str


@dataclass(frozen=True)
class DevicePinType:
    """Typed reference to a pin on a primitive device.

    Attributes
    ----------
    device_type_name : str
        Name of the device type (e.g. ``"Mosfet"``, ``"Capacitor"``).
    pin_name : str
        Name of the pin (e.g. ``"Gate"``).
    """

    device_type_name: str
    pin_name: str


# ═══════════════════════════════════════════════════════════════════════
#  Array library items
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ArrayConnection:
    """Maps one structure-level pin to the underlying device pin.

    For example, ``MosfetNormalArray.Drain`` → ``Mosfet.Drain``.
    """

    structure_pin: StructurePinType
    device_pin: DevicePinType


@dataclass
class ArrayConnectionRule:
    """Connectivity constraint between two device pins within an array.

    If *connected* is ``True``, the two pins **must** share a net;
    if ``False``, they must **not** share a net.
    """

    connected: bool
    pin1: DevicePinType
    pin2: DevicePinType


@dataclass
class ArrayLibraryItem:
    """Definition of one array-level structure template.

    Parsed from an individual ``<arrayLibraryItem>`` XML file under
    ``Array/Items/``.

    Attributes
    ----------
    name : str
        Unique structure name (e.g. ``"MosfetDiodeArray"``).
    connections : list[ArrayConnection]
        Pin mappings from structure to device level.
    device_type_rule : str
        Required device type (e.g. ``"Mosfet"``).
    connection_rules : list[ArrayConnectionRule]
        Connectivity constraints for recognition.
    parallel_nets : list[DevicePinType]
        Device pins whose nets define the grouping key for
        parallel-device detection.
    """

    name: str
    connections: List[ArrayConnection]
    device_type_rule: str
    connection_rules: List[ArrayConnectionRule]
    parallel_nets: List[DevicePinType]


# ═══════════════════════════════════════════════════════════════════════
#  Pair library items
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class ChildPinType:
    """Reference to a child structure's pin, identified by child number.

    Attributes
    ----------
    child_number : int
        ``1`` for the first child, ``2`` for the second.
    structure_pin : StructurePinType
        The pin on the child structure.
    """

    child_number: int
    structure_pin: StructurePinType


@dataclass
class PairPinMapping:
    """Maps one of the pair's external pins to a child's pin.

    For example, ``MosfetSimpleCurrentMirror.Input`` →
    child 1 (``MosfetDiodeArray.Drain``).
    """

    pair_pin: StructurePinType
    child_pin: ChildPinType


@dataclass
class CharacteristicConnection:
    """The defining inter-child connection of a pair.

    The characteristic connection is the single most important
    connectivity pattern that distinguishes this pair type from others.

    *second_child_pins* is a list because some structures allow
    **multiple alternative** second-child pin connections (OR semantics).
    For example, ``MosfetDifferentialStage`` accepts either
    ``MosfetNormalArray.Drain`` **or** ``BipolarNormalArray.Emitter``
    as its second child.

    Attributes
    ----------
    first_child_pin : StructurePinType
        Pin on child 1.
    second_child_pins : list[StructurePinType]
        One or more alternative pins on child 2.
    """

    first_child_pin: StructurePinType
    second_child_pins: List[StructurePinType]


@dataclass
class PairConnectionRule:
    """Connectivity constraint between pins of the two children.

    Attributes
    ----------
    connected : bool
        ``True`` → pins must share a net; ``False`` → must not.
    first_child_pin : StructurePinType
        Pin on child 1.
    second_child_pin : StructurePinType
        Pin on child 2.
    """

    connected: bool
    first_child_pin: StructurePinType
    second_child_pin: StructurePinType


@dataclass
class PairNetRule:
    """Supply-net constraint on a child structure's pin.

    Attributes
    ----------
    structure_pin : StructurePinType
        The pin being constrained.
    child_number : int
        Which child (1 or 2) owns the pin.
    supply : str
        Constraint value: ``"supply"``, ``"no_supply"``,
        ``"vdd"``, or ``"gnd"``.
    """

    structure_pin: StructurePinType
    child_number: int
    supply: str


@dataclass
class PairLibraryItem:
    """Definition of one pair-level structure template.

    Parsed from an individual ``<pairLibraryItem>`` XML file under
    ``Analog/Items/``.

    Attributes
    ----------
    name : str
        Unique structure name (e.g. ``"MosfetSimpleCurrentMirror"``).
    symmetry : bool
        ``True`` if children are interchangeable (e.g. differential
        pair).  The recogniser must try both orderings.
    is_helper_structure : bool
        ``True`` for helper structures (e.g. differential-stage
        wrappers) that don't create a new independent structure but
        mark their children as persistent.
    connections : list[PairPinMapping]
        Pin mappings from pair to children.
    characteristic : CharacteristicConnection
        The defining inter-child connection.
    tech_type_rule : str
        ``"same"`` — both children must have the same tech type.
        ``"different"`` — children must differ (e.g. folded cascode).
        ``"noRule"`` — no constraint.
    net_rules : list[PairNetRule]
        Supply-net constraints.
    connection_rules : list[PairConnectionRule]
        Additional connectivity constraints beyond the characteristic.
    """

    name: str
    symmetry: bool
    is_helper_structure: bool
    connections: List[PairPinMapping]
    characteristic: CharacteristicConnection
    tech_type_rule: str
    net_rules: List[PairNetRule]
    connection_rules: List[PairConnectionRule]


# ═══════════════════════════════════════════════════════════════════════
#  Dominance
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class DominanceRelation:
    """Dominance rule: *dominating* structures beat *dominated* ones.

    When both are recognised in the same region of a circuit, the
    dominated structures are removed.

    Attributes
    ----------
    dominating : list[str]
        Names of structures that win the contest.
    dominated : list[str]
        Names of structures that lose.
    for_current_mirrors : bool
        If ``True``, the rule applies only in current-mirror contexts.
    """

    dominating: List[str]
    dominated: List[str]
    for_current_mirrors: bool = False


# ═══════════════════════════════════════════════════════════════════════
#  Hierarchy entry
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class HierarchyEntry:
    """An item activated at a specific hierarchy level.

    Attributes
    ----------
    name : str
        References the name of an ``ArrayLibraryItem`` or
        ``PairLibraryItem``.
    persistence : int
        ``-1`` (``PERSISTENCE_MAX``) → never pruned.
        *N* (≥ 0) → may be pruned after *N* higher-level matches.
    """

    name: str
    persistence: int = PERSISTENCE_MAX


# ═══════════════════════════════════════════════════════════════════════
#  XML parsing helpers
# ═══════════════════════════════════════════════════════════════════════


def _sanitize_array_xml(text: str) -> str:
    """Fix malformed closing tags in ``ArrayLibrary.xml``.

    The C++ XML contains ``</library_item>`` and ``</libraryItem>``
    as closing tags for ``<arrayLibraryItem>`` — these are invalid XML
    that must be normalised before parsing.
    """
    text = re.sub(r"</library_item>", "</arrayLibraryItem>", text)
    text = re.sub(r"</libraryItem>", "</arrayLibraryItem>", text)
    return text


def _parse_xml_file(filepath: Path) -> ET.Element:
    """Parse an XML file, tolerating common formatting issues.

    Handles:

    * XML declaration appearing after comments (invalid position).
    * Malformed closing tags in array container files.
    * Copyright comment blocks.
    """
    raw = filepath.read_text(encoding="utf-8", errors="replace")
    # Strip XML declaration (may appear after comments — invalid position)
    raw = re.sub(r"<\?xml[^?]*\?>", "", raw)
    # Strip XML comments
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    # Fix malformed closing tags
    raw = _sanitize_array_xml(raw)
    return ET.fromstring(raw.strip())


def _text(elem: ET.Element | None) -> str:
    """Return the stripped text content of *elem*, or ``""`` if absent."""
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


def _parse_structure_pin_type(elem: ET.Element) -> StructurePinType:
    """Parse an element containing ``<structureName>`` + ``<structurePinName>``.

    Works for ``<structurePinType>``, ``<firstChildPinType>``,
    and ``<secondChildPinType>`` elements — they all share the same
    child schema.
    """
    return StructurePinType(
        structure_name=_text(elem.find("structureName")),
        pin_name=_text(elem.find("structurePinName")),
    )


def _parse_device_pin_type(elem: ET.Element) -> DevicePinType:
    """Parse a ``<devicePinType>`` element."""
    return DevicePinType(
        device_type_name=_text(elem.find("deviceTypeName")),
        pin_name=_text(elem.find("devicePinName")),
    )


# ═══════════════════════════════════════════════════════════════════════
#  Array item parsing
# ═══════════════════════════════════════════════════════════════════════


def _parse_array_item(filepath: Path) -> ArrayLibraryItem:
    """Parse a single ``<arrayLibraryItem>`` XML file.

    Parameters
    ----------
    filepath : Path
        Absolute path to the item XML file
        (e.g. ``Array/Items/Mosfet/MosfetNormalArray.xml``).

    Returns
    -------
    ArrayLibraryItem
        Fully populated array item.
    """
    root = _parse_xml_file(filepath)
    name = _text(root.find("structureName"))

    # ── arrayConnection ──────────────────────────────────────────────
    connections: List[ArrayConnection] = []
    ac_elem = root.find("arrayConnection")
    if ac_elem is not None:
        for conn in ac_elem.findall("connection"):
            sp = _parse_structure_pin_type(conn.find("structurePinType"))
            dp = _parse_device_pin_type(conn.find("devicePinType"))
            connections.append(ArrayConnection(structure_pin=sp, device_pin=dp))

    # ── recognitionRules ─────────────────────────────────────────────
    rules_elem = root.find("recognitionRules")
    device_type_rule = ""
    connection_rules: List[ArrayConnectionRule] = []
    if rules_elem is not None:
        device_type_rule = _text(rules_elem.find("deviceTypeRule"))
        cr_elem = rules_elem.find("connectionRules")
        if cr_elem is not None:
            for rule_elem in cr_elem.findall("connectionRule"):
                connected = _text(rule_elem.find("connected")).lower() == "true"
                pins = rule_elem.findall("devicePinType")
                if len(pins) >= 2:
                    connection_rules.append(
                        ArrayConnectionRule(
                            connected=connected,
                            pin1=_parse_device_pin_type(pins[0]),
                            pin2=_parse_device_pin_type(pins[1]),
                        )
                    )

    # ── parallelNets ─────────────────────────────────────────────────
    parallel_nets: List[DevicePinType] = []
    pn_elem = root.find("parallelNets")
    if pn_elem is not None:
        for dp_elem in pn_elem.findall("devicePinType"):
            parallel_nets.append(_parse_device_pin_type(dp_elem))

    return ArrayLibraryItem(
        name=name,
        connections=connections,
        device_type_rule=device_type_rule,
        connection_rules=connection_rules,
        parallel_nets=parallel_nets,
    )


# ═══════════════════════════════════════════════════════════════════════
#  Pair item parsing
# ═══════════════════════════════════════════════════════════════════════


def _parse_pair_item(filepath: Path) -> PairLibraryItem:
    """Parse a single ``<pairLibraryItem>`` XML file.

    Parameters
    ----------
    filepath : Path
        Absolute path to the item XML file.

    Returns
    -------
    PairLibraryItem
        Fully populated pair item.
    """
    root = _parse_xml_file(filepath)
    name = _text(root.find("structureName"))
    symmetry = _text(root.find("structureSymmetry")).lower() == "true"

    hs_elem = root.find("helperStructure")
    is_helper = _text(hs_elem).lower() == "true" if hs_elem is not None else False

    # ── pairConnection ───────────────────────────────────────────────
    connections: List[PairPinMapping] = []
    pc_elem = root.find("pairConnection")
    if pc_elem is not None:
        for ppt in pc_elem.findall("pairPinType"):
            pair_pin = _parse_structure_pin_type(ppt.find("structurePinType"))
            cpt_elem = ppt.find("childPinType")
            child_number = int(_text(cpt_elem.find("childNumber")))
            child_sp = _parse_structure_pin_type(cpt_elem.find("structurePinType"))
            child_pin = ChildPinType(
                child_number=child_number, structure_pin=child_sp
            )
            connections.append(PairPinMapping(pair_pin=pair_pin, child_pin=child_pin))

    # ── characteristicConnection ─────────────────────────────────────
    cc_elem = root.find("characteristicConnection")
    first_pin = _parse_structure_pin_type(cc_elem.find("firstChildPinType"))
    second_pins = [
        _parse_structure_pin_type(e) for e in cc_elem.findall("secondChildPinType")
    ]
    characteristic = CharacteristicConnection(
        first_child_pin=first_pin,
        second_child_pins=second_pins,
    )

    # ── recognitionRules ─────────────────────────────────────────────
    rules_elem = root.find("recognitionRules")

    ttr_elem = rules_elem.find("techTypeRule")
    tech_type_rule = (
        ttr_elem.get("attribute", "noRule") if ttr_elem is not None else "noRule"
    )

    # netRules
    net_rules: List[PairNetRule] = []
    nr_container = rules_elem.find("netRules")
    if nr_container is not None:
        for nr in nr_container.findall("netRule"):
            sp = _parse_structure_pin_type(nr.find("structurePinType"))
            cn = int(_text(nr.find("childNumber")))
            supply = _text(nr.find("supply"))
            net_rules.append(
                PairNetRule(structure_pin=sp, child_number=cn, supply=supply)
            )

    # connectionRules
    connection_rules: List[PairConnectionRule] = []
    cr_container = rules_elem.find("connectionRules")
    if cr_container is not None:
        for cr in cr_container.findall("connectionRule"):
            connected = _text(cr.find("connected")).lower() == "true"
            fp = _parse_structure_pin_type(cr.find("firstChildPinType"))
            sp_rule = _parse_structure_pin_type(cr.find("secondChildPinType"))
            connection_rules.append(
                PairConnectionRule(
                    connected=connected,
                    first_child_pin=fp,
                    second_child_pin=sp_rule,
                )
            )

    return PairLibraryItem(
        name=name,
        symmetry=symmetry,
        is_helper_structure=is_helper,
        connections=connections,
        characteristic=characteristic,
        tech_type_rule=tech_type_rule,
        net_rules=net_rules,
        connection_rules=connection_rules,
    )


# ═══════════════════════════════════════════════════════════════════════
#  ArrayLibrary
# ═══════════════════════════════════════════════════════════════════════


class ArrayLibrary:
    """Collection of all array-level structure templates.

    Loaded from ``Array/ArrayLibrary.xml`` and its referenced item files.
    Arrays are always at hierarchy level 0.

    Attributes
    ----------
    items : dict[str, ArrayLibraryItem]
        All loaded array item definitions, keyed by name.
    active : list[HierarchyEntry]
        Items activated for recognition at level 0.

    C++ reference: ``StructRec::ArrayLibrary``
    """

    def __init__(self) -> None:
        self.items: dict[str, ArrayLibraryItem] = {}
        self.active: list[HierarchyEntry] = []

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def from_xml(cls, array_dir: Path) -> ArrayLibrary:
        """Load the array library from a directory.

        Parameters
        ----------
        array_dir : Path
            Directory containing ``ArrayLibrary.xml`` and the
            ``Items/`` sub-tree.

        Returns
        -------
        ArrayLibrary
        """
        lib = cls()
        root = _parse_xml_file(array_dir / "ArrayLibrary.xml")

        # Load individual item files
        files_elem = root.find("arrayLibraryItemFiles")
        if files_elem is not None:
            for f_elem in files_elem.findall("arrayLibraryItemFile"):
                rel = _text(f_elem)
                if rel:
                    item = _parse_array_item(array_dir / rel)
                    lib.items[item.name] = item

        # Parse active items
        items_elem = root.find("arrayLibraryItems")
        if items_elem is not None:
            for ai in items_elem.findall("arrayLibraryItem"):
                name = _text(ai)
                if name:
                    lib.active.append(HierarchyEntry(name=name))

        return lib

    # ── Accessors ────────────────────────────────────────────────────

    def get_item(self, name: str) -> ArrayLibraryItem:
        """Retrieve an array item by name.

        Raises
        ------
        KeyError
            If no item with *name* exists.
        """
        return self.items[name]

    @property
    def active_names(self) -> list[str]:
        """Names of all active array items."""
        return [e.name for e in self.active]

    def __len__(self) -> int:
        return len(self.items)

    def __contains__(self, name: str) -> bool:
        return name in self.items

    def __repr__(self) -> str:
        return f"ArrayLibrary({len(self.items)} items, {len(self.active)} active)"


# ═══════════════════════════════════════════════════════════════════════
#  PairLibrary
# ═══════════════════════════════════════════════════════════════════════


class PairLibrary:
    """Collection of all pair-level structure templates.

    Loaded from ``Analog/AnalogLibrary.xml`` and its referenced item
    files.  Pairs are organised into hierarchy levels (1, 2, 3).

    Attributes
    ----------
    items : dict[str, PairLibraryItem]
        All loaded pair item definitions, keyed by name.
    levels : dict[int, list[HierarchyEntry]]
        Active items per hierarchy level (level → entries).
    dominance : list[DominanceRelation]
        Dominance rules for conflict resolution.

    C++ reference: ``StructRec::PairLibrary``
    """

    def __init__(self) -> None:
        self.items: dict[str, PairLibraryItem] = {}
        self.levels: dict[int, list[HierarchyEntry]] = {}
        self.dominance: list[DominanceRelation] = []

    # ── Factory ──────────────────────────────────────────────────────

    @classmethod
    def from_xml(cls, analog_dir: Path) -> PairLibrary:
        """Load the pair library from a directory.

        Parameters
        ----------
        analog_dir : Path
            Directory containing ``AnalogLibrary.xml`` and the
            ``Items/`` sub-tree.

        Returns
        -------
        PairLibrary
        """
        lib = cls()
        root = _parse_xml_file(analog_dir / "AnalogLibrary.xml")

        # ── Load individual item files ───────────────────────────────
        files_elem = root.find("pairLibraryItemFiles")
        if files_elem is not None:
            for f_elem in files_elem.findall("pairLibraryItemFile"):
                rel = _text(f_elem)
                if rel:
                    item = _parse_pair_item(analog_dir / rel)
                    lib.items[item.name] = item

        # ── Hierarchy levels ─────────────────────────────────────────
        hl_elem = root.find("hierarchyLevels")
        if hl_elem is not None:
            for level_elem in hl_elem.findall("hierarchyLevel"):
                level = int(level_elem.get("level", "0"))
                entries: list[HierarchyEntry] = []
                for pi in level_elem.findall("pairLibraryItem"):
                    name = _text(pi)
                    if not name:
                        continue
                    # Primary form: persistence as XML attribute
                    # e.g. <pairLibraryItem persistence="1">Name</pairLibraryItem>
                    p_attr = pi.get("persistence")
                    if p_attr is not None:
                        persistence = int(p_attr)
                    else:
                        # Fallback form: persistence as child element
                        # e.g. <pairLibraryItem>Name<persistence>1</persistence></pairLibraryItem>
                        p_elem = pi.find("persistence")
                        persistence = (
                            int(_text(p_elem)) if p_elem is not None else PERSISTENCE_MAX
                        )
                    entries.append(HierarchyEntry(name=name, persistence=persistence))
                lib.levels[level] = entries

        # ── Dominance relations ──────────────────────────────────────
        dom_elem = root.find("dominanceRelations")
        if dom_elem is not None:
            for dr in dom_elem.findall("dominanceRelation"):
                lib.dominance.append(
                    DominanceRelation(
                        dominating=[
                            _text(e) for e in dr.findall("dominatingStructure")
                        ],
                        dominated=[
                            _text(e) for e in dr.findall("dominatedStructure")
                        ],
                        for_current_mirrors=False,
                    )
                )
            for dr in dom_elem.findall("dominanceRelationForCurrentMirrors"):
                lib.dominance.append(
                    DominanceRelation(
                        dominating=[
                            _text(e) for e in dr.findall("dominatingStructure")
                        ],
                        dominated=[
                            _text(e) for e in dr.findall("dominatedStructure")
                        ],
                        for_current_mirrors=True,
                    )
                )

        return lib

    # ── Accessors ────────────────────────────────────────────────────

    def get_item(self, name: str) -> PairLibraryItem:
        """Retrieve a pair item by name.

        Raises
        ------
        KeyError
            If no item with *name* exists.
        """
        return self.items[name]

    def get_level_entries(self, level: int) -> list[HierarchyEntry]:
        """Return active entries for a hierarchy level."""
        return list(self.levels.get(level, []))

    @property
    def hierarchy_levels(self) -> list[int]:
        """Sorted list of available hierarchy levels."""
        return sorted(self.levels.keys())

    def __len__(self) -> int:
        return len(self.items)

    def __contains__(self, name: str) -> bool:
        return name in self.items

    def __repr__(self) -> str:
        lvl = ", ".join(f"L{k}={len(v)}" for k, v in sorted(self.levels.items()))
        return f"PairLibrary({len(self.items)} items, {lvl})"


# ═══════════════════════════════════════════════════════════════════════
#  Library (master)
# ═══════════════════════════════════════════════════════════════════════


class Library:
    """Master library combining array and pair sub-libraries.

    This is the main entry point for loading the complete structure
    recognition library from the bundled XML data directory.

    Attributes
    ----------
    array_library : ArrayLibrary
        All array-level templates (level 0).
    pair_library : PairLibrary
        All pair-level templates (levels 1–3).

    C++ reference: ``StructRec::Library``
    """

    def __init__(
        self,
        array_library: ArrayLibrary,
        pair_library: PairLibrary,
    ) -> None:
        self.array_library = array_library
        self.pair_library = pair_library

    @classmethod
    def from_directory(cls, lib_dir: str | Path | None = None) -> Library:
        """Load the complete library from a directory or wrapper file.

        Parameters
        ----------
        lib_dir : str or Path, optional
            Either a root directory containing ``AnalogLibrary.xml``, or a
            wrapper-file path (acst's ``--xml-structrec-library-file`` form,
            e.g. ``Library.xml``) whose ``<library>`` root references the
            array/pair libraries; references resolve relative to the
            wrapper's own directory.  Defaults to the bundled
            ``data/structrec/`` directory.

        Returns
        -------
        Library
            Fully populated library ready for recognition.

        Raises
        ------
        FileNotFoundError
            If the directory or any referenced XML file is missing.
        ValueError
            If the master file is not a library wrapper (no
            ``arrayLibraryFile``/``pairLibraryFile`` references).
        xml.etree.ElementTree.ParseError
            If an XML file cannot be parsed.
        """
        if lib_dir is None:
            lib_dir = _DEFAULT_LIB_DIR
        lib_dir = Path(lib_dir)
        if not lib_dir.exists():
            raise FileNotFoundError(f"structrec library not found: {lib_dir}")
        # a wrapper file may carry any name (acst ships e.g. Library.xml);
        # a directory must contain the canonical AnalogLibrary.xml
        master_path = lib_dir if lib_dir.is_file() else lib_dir / "AnalogLibrary.xml"
        base_dir = master_path.parent

        master = _parse_xml_file(master_path)

        array_rel = _text(master.find(".//arrayLibraryFile"))
        pair_rel = _text(master.find(".//pairLibraryFile"))
        if not array_rel or not pair_rel:
            raise ValueError(
                f"{master_path} is not a structrec library wrapper: expected "
                "<arrayLibraryFile> and <pairLibraryFile> references under a "
                "<library> root"
            )

        # ── Array library ────────────────────────────────────────────
        array_dir = (base_dir / array_rel).parent
        array_library = ArrayLibrary.from_xml(array_dir)

        # ── Pair library ─────────────────────────────────────────────
        pair_dir = (base_dir / pair_rel).parent
        pair_library = PairLibrary.from_xml(pair_dir)

        return cls(array_library=array_library, pair_library=pair_library)

    def __repr__(self) -> str:
        return f"Library({self.array_library!r}, {self.pair_library!r})"
