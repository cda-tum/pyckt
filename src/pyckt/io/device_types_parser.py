"""
Device-types file parser.

Reads ``deviceTypes.xcat`` (XML) and populates a
:class:`~pyckt.core.DeviceTypeRegister` with the pin and tech-type
information for each device category (Mosfet, Capacitor, …).

The file defines:
  - Which :class:`~pyckt.core.PinType` values each device type uses.
  - Which pins are optional (Bulk) and their auto-connection rules.
  - Which :class:`~pyckt.core.TechType` flavours exist per device type.

Maps to ``Core::DeviceTypeRegister::fromFile`` in the C++ ACST code.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from pyckt.core import (
    DeviceType,
    DeviceTypeRegister,
    PinType,
    PinTypeInfo,
    TechType,
)


def load_device_types(filepath: str | Path) -> DeviceTypeRegister:
    """Parse *filepath* (``deviceTypes.xcat``) and return a populated register.

    This is a module-level factory rather than a classmethod on
    :class:`DeviceTypeRegister` because the core module should stay
    independent of I/O concerns (XML parsing).

    Parameters
    ----------
    filepath : str | Path
        Path to a ``deviceTypes.xcat`` XML file.

    Returns
    -------
    DeviceTypeRegister
        Fully populated register ready for use by other parsers.

    Raises
    ------
    FileNotFoundError
        If *filepath* does not exist.
    ET.ParseError
        If the XML is malformed.
    KeyError
        If a device-type name or pin-type name does not match the core enums.

    Example
    -------
    >>> register = load_device_types("tests/data/deviceTypes.xcat")
    >>> pins = register.get_pin_types(DeviceType.MOSFET)
    >>> [p.pin_type.value for p in pins]
    ['Drain', 'Gate', 'Source', 'Bulk']
    """
    register = DeviceTypeRegister()
    tree = ET.parse(Path(filepath))
    root = tree.getroot()

    for dt_elem in root.findall("deviceType"):
        name = (dt_elem.get("name") or "").strip()
        if not name:
            continue

        try:
            device_type = DeviceType.from_text(name)
        except KeyError as exc:
            raise KeyError(f"Unknown device type name in XML: {name!r}") from exc

        tech_types: list[TechType] = []
        for tech_elem in dt_elem.findall("./techTypes/techType"):
            text = (tech_elem.text or "").strip()
            if not text:
                continue
            try:
                tech_types.append(TechType.from_text(text))
            except KeyError as exc:
                raise KeyError(
                    f"Unknown tech type {text!r} for device type {name!r}"
                ) from exc

        pin_infos: list[PinTypeInfo] = []
        for pin_elem in dt_elem.findall("./pinTypes/pinType"):
            pin_text = (pin_elem.text or "").strip()
            if not pin_text:
                continue

            try:
                pin_type = PinType.from_text(pin_text)
            except KeyError as exc:
                raise KeyError(
                    f"Unknown pin type {pin_text!r} for device type {name!r}"
                ) from exc

            optional = (pin_elem.get("optional", "false").strip().lower() == "true")
            auto_connection_attr = (pin_elem.get("autoConnection") or "").strip()
            auto_connection = None
            if auto_connection_attr:
                try:
                    auto_connection = PinType.from_text(auto_connection_attr)
                except KeyError as exc:
                    raise KeyError(
                        "Unknown autoConnection pin type "
                        f"{auto_connection_attr!r} for device type {name!r}"
                    ) from exc

            pin_infos.append(
                PinTypeInfo(
                    pin_type=pin_type,
                    optional=optional,
                    auto_connection=auto_connection,
                )
            )

        register.register(device_type, pin_infos, tech_types)

    return register
