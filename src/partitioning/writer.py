"""XML serialisation of partitioning results.

Produces an XML document grouping structures by stage and functional role,
mirroring the C++ ``Partitioning::ResultWriter``.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent

from ckt_io.acst_xml import make_root, write_structure, write_tree

from .result import PartitionResult, PartType, StageType


class PartitionXMLWriter:
    """Write a :class:`PartitionResult` to XML.

    Usage::

        writer = PartitionXMLWriter(result)
        writer.write("partitioning.xml")
    """

    def __init__(self, result: PartitionResult) -> None:
        self._result = result

    # ── Public API ───────────────────────────────────────────────────

    def build_tree(self) -> Element:
        """Build and return the root ``<PartitioningResult>`` element."""
        root = Element("PartitioningResult")

        # First stage
        first = SubElement(root, "FirstStage")
        self._add_role_group(first, "Transconductance",
                             PartType.TRANSCONDUCTANCE, StageType.FIRST)
        self._add_role_group(first, "Load", PartType.LOAD, StageType.FIRST)
        self._add_role_group(first, "Bias", PartType.BIAS, StageType.FIRST)

        # Second stage (only if present)
        if self._result.is_two_stage():
            second = SubElement(root, "SecondStage")
            self._add_role_group(second, "Transconductance",
                                 PartType.TRANSCONDUCTANCE, StageType.SECOND)
            self._add_role_group(second, "Load", PartType.LOAD, StageType.SECOND)
            self._add_role_group(second, "Bias", PartType.BIAS, StageType.SECOND)

        # Capacitance
        caps = self._result.capacitance_parts()
        if caps:
            cap_el = SubElement(root, "Capacitance")
            for s in caps:
                a = self._result.get_part(s)
                se = SubElement(cap_el, "Structure", name=s.name,
                                techType=str(s.tech_type.value))
                if a:
                    se.set("role", a.role_description)
                for d in s.devices:
                    SubElement(se, "Device").text = d.name

        # Bias (stage-undefined)
        bias_undef = [
            a for a in self._result.all_assignments
            if a.part_type is PartType.BIAS and a.stage is StageType.UNDEFINED
        ]
        if bias_undef:
            bias_el = SubElement(root, "Bias")
            for a in bias_undef:
                se = SubElement(bias_el, "Structure", name=a.structure.name,
                                techType=str(a.structure.tech_type.value))
                se.set("role", a.role_description)
                for d in a.structure.devices:
                    SubElement(se, "Device").text = d.name

        # Undefined
        undef = self._result.undefined_parts()
        if undef:
            undef_el = SubElement(root, "Undefined")
            for s in undef:
                se = SubElement(undef_el, "Structure", name=s.name,
                                techType=str(s.tech_type.value))
                for d in s.devices:
                    SubElement(se, "Device").text = d.name

        return root

    def write(self, path: str | Path) -> None:
        """Write the XML tree to *path*."""
        root = self.build_tree()
        indent(root, space="  ")
        tree = ElementTree(root)
        tree.write(str(path), encoding="unicode", xml_declaration=True)

    def to_string(self) -> str:
        """Return the XML as a string."""
        from xml.etree.ElementTree import tostring
        root = self.build_tree()
        indent(root, space="  ")
        return tostring(root, encoding="unicode")

    # ── Helpers ──────────────────────────────────────────────────────

    def _add_role_group(
        self, parent: Element, tag: str,
        part_type: PartType, stage: StageType,
    ) -> None:
        """Add a ``<Tag>`` sub-element with matching structures."""
        if part_type is PartType.TRANSCONDUCTANCE:
            parts = self._result.transconductance_parts(stage)
        elif part_type is PartType.LOAD:
            parts = self._result.load_parts(stage)
        elif part_type is PartType.BIAS:
            parts = self._result.bias_parts(stage)
        else:
            return
        if not parts:
            return
        group = SubElement(parent, tag)
        for s in parts:
            a = self._result.get_part(s)
            se = SubElement(group, "Structure", name=s.name,
                            techType=str(s.tech_type.value))
            if a:
                se.set("role", a.role_description)
            for d in s.devices:
                SubElement(se, "Device").text = d.name


class AcstPartitionXMLWriter:
    """Write an :class:`~partitioning.acst_parts.AcstPartitionResult` in the
    C++ ACST ``<circuit_partitioning_results>`` schema.

    Emits all eight sections acst produces — ``gmParts`` (with
    ``firstStage`` / ``primarySecondStage`` / ``secondarySecondStage`` types and
    ``firstStageType``), ``loadParts``, ``biasParts``, ``capacitances``,
    ``resistorParts``, ``commonModeSignalDetectorParts``,
    ``positiveFeedbackParts`` and ``undefinedParts`` — each part carrying its
    main structures as full nested ``structure`` / ``pins`` / ``devices`` trees
    via the shared :func:`ckt_io.acst_xml.write_structure`.
    """

    def __init__(self, result) -> None:  # AcstPartitionResult
        self._result = result

    def build_tree(self) -> Element:
        root, results = make_root("circuit_partitioning_results")

        gm_parts = SubElement(results, "gmParts")
        for tp in self._ordered_transconductances():
            attrs = {"type": tp.type}
            if tp.is_first_stage() and tp.first_stage_type:
                attrs["firstStageType"] = tp.first_stage_type
            gm_part = SubElement(gm_parts, "gmPart", **attrs)
            self._emit_part(gm_part, tp)

        load_parts = SubElement(results, "loadParts")
        for lp in self._result.load_parts:
            self._emit_part(SubElement(load_parts, "loadPart"), lp)

        bias_parts = SubElement(results, "biasParts")
        for bp in self._result.bias_parts:
            self._emit_part(SubElement(bias_parts, "biasPart"), bp)

        caps = SubElement(results, "capacitances")
        for cp in self._result.capacitance_parts:
            attrs = {"type": cp.type} if cp.type else {}
            self._emit_part(SubElement(caps, "capacitance", **attrs), cp)

        # sections acst always emits, empty for this circuit class
        SubElement(results, "resistorParts")
        SubElement(results, "commonModeSignalDetectorParts")
        SubElement(results, "positiveFeedbackParts")

        undef = SubElement(results, "undefinedParts")
        for up in self._result.undefined_parts:
            self._emit_part(SubElement(undef, "undefinedPart"), up)

        return root

    def _ordered_transconductances(self):
        """gm parts in acst order: firstStage, primary-, secondary-second, rest."""
        order = {"firstStage": 0, "primarySecondStage": 1,
                 "secondarySecondStage": 2, "thirdStage": 3}
        return sorted(self._result.transconductance_parts,
                      key=lambda t: order.get(t.type, 9))

    @staticmethod
    def _emit_part(parent: Element, part) -> None:
        for structure in part.main_structures:
            write_structure(parent, structure)

    def write(self, path: str | Path) -> None:
        write_tree(self.build_tree(), path)

    def to_string(self) -> str:
        from xml.etree.ElementTree import tostring
        root = self.build_tree()
        indent(root, space="\t")
        return tostring(root, encoding="unicode")
