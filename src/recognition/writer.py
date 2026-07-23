"""XML output writers for structure recognition results and sizing rules.

Two structure-recognition schemas are provided:

* :class:`StructRecXMLWriter` — pyckt's native ``<StructureRecognitionResult>``
  format (PascalCase tags, ``<Children>`` wrapper, bare net/device names).
* :class:`AcstStructRecXMLWriter` — the C++ ACST
  ``<acst_results>/<structure_recognition_results>`` schema (lowercase tags,
  children nested directly, leaf devices under ``<devices>``, leading-slash
  net/device names, bracketed instance index).  Selected via
  ``--output-format acst``.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ckt_io.acst_xml import make_root, write_structure, write_tree

from .model import (
    Structure,
    StructureCircuits,
)
from .rule_learning import LearnedItem, LearnedLibrary
from .rulegen import SizingRule


class StructRecXMLWriter:
    """Write recognition results in pyckt's native XML format."""

    def write(self, sc: StructureCircuits, filepath: str | Path) -> None:
        root = ET.Element("StructureRecognitionResult")
        for s in sc.structures_without_parents:
            self._write(root, s)
        tree = ET.ElementTree(root); ET.indent(tree, space="  ")
        tree.write(str(filepath), encoding="unicode", xml_declaration=True)

    def _write(self, parent: ET.Element, s: Structure) -> None:
        elem = ET.SubElement(parent, "Structure", name=s.name, techType=s.tech_type.value)
        if s.is_pair:
            ch = ET.SubElement(elem, "Children")
            self._write(ch, s.child1); self._write(ch, s.child2)  # type: ignore[union-attr]
        elif s.is_array:
            for d in s.devices:
                ET.SubElement(elem, "Transistor", name=d.name)
        if s.pins:
            pe = ET.SubElement(elem, "Pins")
            for pn, pin in sorted(s.pins.items()):
                try:    ET.SubElement(pe, "Pin", name=pn, net=pin.net.name)
                except RuntimeError: ET.SubElement(pe, "Pin", name=pn, net="?")


class AcstStructRecXMLWriter:
    """Write recognition results in the C++ ACST XML schema.

    Mirrors ``acst``'s structure-recognition output so the two tools can be
    diffed tag-for-tag:

    * root ``<acst_results>`` with a ``<date>`` child and a
      ``<structure_recognition_results>`` container;
    * lowercase ``structure`` / ``pins`` / ``pin`` / ``devices`` / ``device``;
    * child structures nested **directly** inside the parent (no ``<Children>``);
    * leaf devices listed under ``<devices>`` with ``deviceType`` / ``techType``;
    * a bracketed instance index on each structure name (``MosfetDiodeArray[5]``);
    * leading-slash net and device names.
    """

    def write(self, sc: StructureCircuits, filepath: str | Path) -> None:
        root, results = make_root("structure_recognition_results")
        for s in sc.structures_without_parents:
            write_structure(results, s)
        write_tree(root, filepath)


class RuleXMLWriter:
    """Write sizing rules to XML."""

    def write(self, rules: list[SizingRule], filepath: str | Path) -> None:
        root = ET.Element("SizingRules")
        for r in rules:
            re_ = ET.SubElement(root, "Rule", type=r.rule_type, structure=r.structure_name)
            for d in r.devices:
                ET.SubElement(re_, "Device").text = d
            ET.SubElement(re_, "Description").text = r.description
        tree = ET.ElementTree(root); ET.indent(tree, space="  ")
        tree.write(str(filepath), encoding="unicode", xml_declaration=True)


class AcstPairLibraryWriter:
    """Write a :class:`~recognition.rule_learning.LearnedLibrary` in acst's
    ``rulegen`` schema: a ``<pairLibrary>`` index plus one ``Items/<name>.xml``
    per learned composite structure.

    The index lists the item files, the hierarchy levels (with persistence),
    and an empty ``<dominanceRelations/>``.  Each item file is a
    ``<pairLibraryItem>`` with its ``pairConnection`` (external pins → child
    pins), ``characteristicConnection``, and ``recognitionRules``
    (techType + connection rules) — mirroring acst's ``NewPairLibraryItem``.
    """

    def write(self, library: LearnedLibrary, filepath: str | Path) -> None:
        out = Path(filepath)
        items_dir = out.parent / "Items"
        items_dir.mkdir(parents=True, exist_ok=True)

        for item in library.items:
            tree = ET.ElementTree(self._item_element(item))
            ET.indent(tree, space="\t")
            tree.write(str(items_dir / f"{item.name}.xml"),
                       encoding="unicode", xml_declaration=True)

        tree = ET.ElementTree(self._index_element(library))
        ET.indent(tree, space="\t")
        tree.write(str(out), encoding="unicode", xml_declaration=True)

    # ── index ─────────────────────────────────────────────────────────

    def _index_element(self, library: LearnedLibrary) -> ET.Element:
        root = ET.Element("pairLibrary")
        files = ET.SubElement(root, "pairLibraryItemFiles")
        for item in library.items:
            ET.SubElement(files, "pairLibraryItemFile").text = f"Items/{item.name}.xml"
        levels = ET.SubElement(root, "hierarchyLevels")
        for level, items in library.levels().items():
            lvl = ET.SubElement(levels, "hierarchyLevel", level=str(level))
            for item in items:
                el = ET.SubElement(lvl, "pairLibraryItem")
                if item.persistence is not None:
                    el.set("persistence", str(item.persistence))
                el.text = item.name
        ET.SubElement(root, "dominanceRelations")
        return root

    # ── one item ──────────────────────────────────────────────────────

    def _item_element(self, item: LearnedItem) -> ET.Element:
        root = ET.Element("pairLibraryItem")
        ET.SubElement(root, "structureName").text = item.name
        ET.SubElement(root, "structureSymmetry").text = str(item.symmetric).lower()

        pc = ET.SubElement(root, "pairConnection")
        for pin_name, child_num, child_struct, child_pin in item.pair_connection:
            ppt = ET.SubElement(pc, "pairPinType")
            self._pin_type(ppt, "structurePinType", item.name, pin_name)
            cpt = ET.SubElement(ppt, "childPinType")
            ET.SubElement(cpt, "childNumber").text = str(child_num)
            self._pin_type(cpt, "structurePinType", child_struct, child_pin)

        if item.characteristic is not None:
            c1_struct, c1_pin, seconds = item.characteristic
            cc = ET.SubElement(root, "characteristicConnection")
            self._pin_type(cc, "firstChildPinType", c1_struct, c1_pin)
            for c2_struct, c2_pin in seconds:
                self._pin_type(cc, "secondChildPinType", c2_struct, c2_pin)

        rules = ET.SubElement(root, "recognitionRules")
        ET.SubElement(rules, "netRules")
        cr = ET.SubElement(rules, "connectionRules")
        for c1_struct, c1_pin, c2_struct, c2_pin, connected in item.connection_rules:
            rule = ET.SubElement(cr, "connectionRule")
            ET.SubElement(rule, "connected").text = str(connected).lower()
            self._pin_type(rule, "firstChildPinType", c1_struct, c1_pin)
            self._pin_type(rule, "secondChildPinType", c2_struct, c2_pin)
        ET.SubElement(rules, "techTypeRule", attribute=item.tech_type_rule)
        return root

    @staticmethod
    def _pin_type(parent: ET.Element, tag: str, struct: str, pin: str) -> None:
        el = ET.SubElement(parent, tag)
        ET.SubElement(el, "structureName").text = struct
        ET.SubElement(el, "structurePinName").text = pin
