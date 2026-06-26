"""Shared helpers for emitting C++ ACST-compatible XML.

The C++ ``acst`` tool wraps every analysis result in a common envelope::

    <acst_results>
        <date day=".." month=".." year=".." hour=".." minute=".." second=".."/>
        <<mode>-results> ... </<mode>-results>
    </acst_results>

and follows a handful of conventions that differ from pyckt's native schema:

* leading-slash names (``/m8``, ``/net30``),
* specific unit spellings (``mu_m``, ``m_W``, ``mu_A`` …),
* lowercase ``structure`` / ``pins`` / ``pin`` / ``devices`` / ``device`` tags
  with children nested directly and a bracketed instance index,
* tab indentation and no XML declaration.

These helpers centralise those conventions so each mode's acst-format writer
stays small and consistent.  The structure emitter is *duck-typed* (it only
touches ``.name`` / ``.structure_id`` / ``.tech_type`` / ``.pins`` /
``.is_pair`` / ``.child1`` / ``.child2`` / ``.is_array`` / ``.devices``) so this
module does not import the recognition model and avoids a circular import.
"""
from __future__ import annotations

import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

# pyckt native unit string → acst spelling
UNIT_ACST: dict[str, str] = {
    "um": "mu_m",
    "mW": "m_W",
    "um2": "(mu_m)^2",
    "nA": "mu_A",
    "MHz": "M_Hz",
    "V/us": "V/mum_s",
    "deg": "degree",
    # identity spellings (kept explicit so callers can pass native units freely)
    "mV": "mV",
    "V": "V",
    "dB": "dB",
}


def slash(name: str) -> str:
    """Prefix a net/device/component name with ``/`` (the acst root cell path)."""
    return name if name.startswith("/") else f"/{name}"


def acst_unit(native_unit: str) -> str:
    """Translate a pyckt native unit string to its acst spelling."""
    return UNIT_ACST.get(native_unit, native_unit)


def make_root(results_tag: str) -> tuple[ET.Element, ET.Element]:
    """Build ``<acst_results><date/><{results_tag}>`` and return *(root, results)*.

    The caller populates the returned *results* element.
    """
    root = ET.Element("acst_results")
    now = datetime.datetime.now()
    ET.SubElement(
        root, "date",
        day=str(now.day), month=str(now.month), year=str(now.year),
        hour=str(now.hour), minute=str(now.minute), second=str(now.second),
    )
    results = ET.SubElement(root, results_tag)
    return root, results


def write_tree(root: ET.Element, path: str | Path) -> None:
    """Indent (tabs) and write *root* to *path*, acst-style (no XML declaration)."""
    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t")
    tree.write(str(path), encoding="unicode", xml_declaration=False)


def write_structure(parent: ET.Element, s) -> None:
    """Emit one recognised structure (and its subtree) in the acst schema.

    Produces::

        <structure name="MosfetDiodeArray[5]" techType="p" instance="/">
            <pins><pin name=".." net="/.."/> … </pins>
            <structure …> … </structure>          # pair children, nested directly
            <devices><device name="/m.." deviceType="Mosfet" techType="p"
                             instance="/"/></devices>   # array leaves
        </structure>

    *s* is duck-typed to a :class:`recognition.model.Structure`.
    """
    elem = ET.SubElement(
        parent, "structure",
        name=f"{s.name}[{s.structure_id.index}]",
        techType=s.tech_type.value,
        instance="/",
    )
    # acst writes <pins> first, then nested structures / devices.
    if s.pins:
        pe = ET.SubElement(elem, "pins")
        for pn, pin in sorted(s.pins.items()):
            try:
                net = slash(pin.net.name)
            except RuntimeError:
                net = "?"
            ET.SubElement(pe, "pin", name=pn, net=net)
    if s.is_pair:
        write_structure(elem, s.child1)
        write_structure(elem, s.child2)
    elif s.is_array:
        de = ET.SubElement(elem, "devices")
        for d in s.devices:
            ET.SubElement(
                de, "device",
                name=slash(d.name),
                deviceType=d.device_type.value,
                techType=d.tech_type.value,
                instance="/",
            )
