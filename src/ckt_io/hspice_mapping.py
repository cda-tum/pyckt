"""
HSpice device-line mapping parser.

Reads ``HSpiceMapping.xcat`` (XML) and builds a lookup table that tells the
HSpice netlist parser how to interpret each device line.  One
:class:`DeviceLineMapping` per device-type identifier (``m``, ``c``, ``r``, …).

Maps to ``HSpice::DeviceLineMapping`` in the C++ ACST code.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from core import DeviceType, PinType, TechType

# ── Data model ────────────────────────────────────────────────────────────


@dataclass
class DeviceLineMapping:
    """How to interpret one type of device line in HSpice format.

    Attributes
    ----------
    identifier : str
        Single-character prefix that triggers this mapping (``"m"``, ``"c"``…).
    device_type : DeviceType
        Core device type produced by this mapping.
    pin_positions : dict[PinType, int]
        Token-index of each pin in the netlist line (0-based device-name,
        then 1-based pins).
    has_model : bool
        ``True`` when the line includes a model-name token (Mosfet, Bipolar).
    model_position : int | None
        Token index of the model-name token, or ``None`` when *has_model*
        is ``False``.
    model_map : dict[str, TechType] | None
        Mapping from model-name string → :class:`TechType`, e.g.
        ``{"nmos": TechType.N, "pmos": TechType.P}``.  ``None`` when no
        model is used.
    fixed_tech : TechType | None
        The :class:`TechType` to assign when no model line exists
        (e.g. ``TechType.UNDEFINED`` for Capacitor/Resistor).
    """

    identifier: str
    device_type: DeviceType
    pin_positions: dict[PinType, int] = field(default_factory=dict)
    has_model: bool = False
    model_position: int | None = None
    model_map: dict[str, TechType] | None = None
    fixed_tech: TechType | None = None


# ── Mapping collection ────────────────────────────────────────────────────


class HSpiceMapping:
    """Collection of :class:`DeviceLineMapping` entries parsed from
    ``HSpiceMapping.xcat``.

    Maps to ``HSpice::DeviceLineMapping`` in C++.

    Usage::

        mapping = HSpiceMapping.from_file("HSpiceMapping.xcat")
        m_rule  = mapping.get_mapping("m")   # → DeviceLineMapping for MOSFETs
    """

    def __init__(self) -> None:
        self._mappings: dict[str, DeviceLineMapping] = {}

    # ── public API ────────────────────────────────────────────────────

    @classmethod
    def from_file(cls, filepath: str | Path) -> HSpiceMapping:
        """Parse *filepath* and return a populated :class:`HSpiceMapping`.

        Parameters
        ----------
        filepath : str | Path
            Path to an ``HSpiceMapping.xcat`` XML file.

        Returns
        -------
        HSpiceMapping

        Raises
        ------
        FileNotFoundError
            If *filepath* does not exist.
        ET.ParseError
            If the XML is malformed.
        """
        path = Path(filepath)

        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as parse_error:
            # Known quirk in some ACST examples:
            # final closing tag is </deviceLineMapping> instead of
            # </deviceLineMapper>. Try a one-shot repair fallback.
            raw = path.read_text(encoding="utf-8", errors="ignore")
            repaired = _repair_known_mapping_xml_issues(raw)
            try:
                root = ET.fromstring(repaired)
            except ET.ParseError:
                raise parse_error

        mapping = cls()

        for elem in root.findall("./deviceLineMapping"):
            identifier = (elem.get("identifier") or "").strip().lower()
            if not identifier:
                continue

            device_type_text = (elem.findtext("deviceTypeName") or "").strip()
            if not device_type_text:
                raise KeyError(
                    f"Missing deviceTypeName for identifier {identifier!r}"
                )
            try:
                device_type = DeviceType.from_text(device_type_text)
            except KeyError as exc:
                raise KeyError(
                    f"Unknown device type {device_type_text!r} "
                    f"for identifier {identifier!r}"
                ) from exc

            pin_positions: dict[PinType, int] = {}
            for pin_elem in elem.findall("./pins/pin"):
                pin_type_text = (pin_elem.get("pinType") or "").strip()
                position_text = (pin_elem.get("position") or "").strip()
                if not pin_type_text or not position_text:
                    continue

                try:
                    pin_type = PinType.from_text(pin_type_text)
                except KeyError as exc:
                    raise KeyError(
                        f"Unknown pin type {pin_type_text!r} "
                        f"for identifier {identifier!r}"
                    ) from exc

                pin_positions[pin_type] = int(position_text)

            model_elem = elem.find("modelName")
            has_model = model_elem is not None
            model_position: int | None = None
            model_map: dict[str, TechType] | None = None
            fixed_tech: TechType | None = None

            if model_elem is not None:
                model_position_text = (model_elem.get("position") or "").strip()
                if not model_position_text:
                    raise KeyError(
                        f"Missing modelName position for identifier {identifier!r}"
                    )
                model_position = int(model_position_text)

                model_map = {}
                for model in model_elem.findall("./model"):
                    model_name = (model.get("name") or "").strip()
                    tech_text = (model.get("techType") or "").strip()
                    if not model_name or not tech_text:
                        continue
                    try:
                        tech = TechType.from_text(tech_text)
                    except KeyError as exc:
                        raise KeyError(
                            f"Unknown tech type {tech_text!r} in model "
                            f"{model_name!r} for identifier {identifier!r}"
                        ) from exc

                    # Store case-insensitively to match incoming netlist models.
                    model_map[model_name.casefold()] = tech
            else:
                tech_text = (elem.findtext("techType") or "").strip()
                if tech_text:
                    try:
                        fixed_tech = TechType.from_text(tech_text)
                    except KeyError as exc:
                        raise KeyError(
                            f"Unknown fixed tech type {tech_text!r} "
                            f"for identifier {identifier!r}"
                        ) from exc

            mapping._mappings[identifier] = DeviceLineMapping(
                identifier=identifier,
                device_type=device_type,
                pin_positions=pin_positions,
                has_model=has_model,
                model_position=model_position,
                model_map=model_map,
                fixed_tech=fixed_tech,
            )

        return mapping

    def get_mapping(self, identifier: str) -> DeviceLineMapping:
        """Return the mapping for the given single-char *identifier*.

        Parameters
        ----------
        identifier : str
            Case-insensitive first character of a device name (``"m"``, ``"c"``…).

        Raises
        ------
        KeyError
            If no mapping exists for *identifier*.
        """
        return self._mappings[identifier.lower()]

    @property
    def identifiers(self) -> list[str]:
        """Return all registered identifiers."""
        return list(self._mappings.keys())

    def __len__(self) -> int:
        return len(self._mappings)

    def __contains__(self, identifier: str) -> bool:
        return identifier.lower() in self._mappings


def _repair_known_mapping_xml_issues(xml_text: str) -> str:
    """Repair known ACST example quirks in mapping XML.

    Currently handled:
    - Final close tag typo: ``</deviceLineMapping>`` instead of
      ``</deviceLineMapper>``.
    """
    if "</deviceLineMapper>" in xml_text:
        return xml_text

    bad = "</deviceLineMapping>"
    idx = xml_text.rfind(bad)
    if idx == -1:
        return xml_text

    return xml_text[:idx] + "</deviceLineMapper>" + xml_text[idx + len(bad):]
