"""
Technology file parser.

Reads ``TechnologieFile.xml`` (XML) and extracts transistor process parameters
for NMOS and PMOS devices, plus the global thermal voltage.

These parameters are used by the automatic sizing engine and the synthesis
module to compute expected circuit performance.

Maps to ``CircuitInformation::TechnologyFile`` in the C++ ACST code.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TransistorTechParams:
    """Process parameters for one transistor flavour (NMOS or PMOS).

    All values use SI / micro-scale units as annotated.

    Attributes
    ----------
    threshold_voltage : float
        Vth [V].
    mu_cox : float
        μ·Cox [A/V²].
    early_voltage : float
        VA [V/μm].
    overlap_capacitance : float
        Cgdov [F/m].
    gate_oxide_capacitance : float
        Cox [F/m²].
    cj : float
        Zero-bias bulk junction capacitance [F/m²].
    cjsw : float
        Zero-bias sidewall bulk junction capacitance [F/m].
    pb : float
        Bulk junction contact potential [V].
    lateral_diffusion : float
        Ldiff [m].
    slope_factor : float
        n (subthreshold slope factor).
    lambda_strong : float
        Channel-length coefficient (strong inversion).
    lambda_weak : float
        Channel-length coefficient (weak inversion).
    min_area : float
        Amin [μm²].
    min_length : float
        Lmin [μm] — used as integer in program.
    min_width : float
        Wmin [μm] — used as integer in program.
    """

    threshold_voltage: float
    mu_cox: float
    early_voltage: float
    overlap_capacitance: float
    gate_oxide_capacitance: float
    cj: float
    cjsw: float
    pb: float
    lateral_diffusion: float
    slope_factor: float
    lambda_strong: float
    lambda_weak: float
    min_area: float
    min_length: float
    min_width: float


# ── XML tag → (attribute, dataclass field) mapping ────────────────────────
# Each entry: (xml_tag, xml_attribute, TransistorTechParams field name)

_FIELD_MAP: list[tuple[str, str, str]] = [
    ("thresholdVoltage", "vth", "threshold_voltage"),
    ("mobilityOxideCapacity", "muCox", "mu_cox"),
    ("earlyVoltage", "earlyVoltage", "early_voltage"),
    ("overlapCapacity", "Cgdov", "overlap_capacitance"),
    ("gateOxideCapacity", "Cox", "gate_oxide_capacitance"),
    ("zeroBiasBulkJunctionCapacitance", "Cj", "cj"),
    ("zeroBiasSidewallBulkJunctionCapacitance", "Cjsw", "cjsw"),
    ("bulkJunctionContactPotential", "pb", "pb"),
    ("lateralDiffusionLength", "Ldiff", "lateral_diffusion"),
    ("slopeFactor", "n", "slope_factor"),
    ("channelLengthCoefficientStrongInversion", "lamda", "lambda_strong"),
    ("channelLengthCoefficientWeakInversion", "lamda", "lambda_weak"),
    ("minArea", "Amin", "min_area"),
    ("minLength", "Lmin", "min_length"),
    ("minWidth", "Wmin", "min_width"),
]


@dataclass
class TechnologyParams:
    """Complete technology parameters for both NMOS and PMOS.

    Attributes
    ----------
    thermal_voltage : float
        Vt [V].
    nmos : TransistorTechParams
        NMOS process parameters.
    pmos : TransistorTechParams
        PMOS process parameters.
    """

    thermal_voltage: float
    nmos: TransistorTechParams
    pmos: TransistorTechParams

    @classmethod
    def from_file(cls, filepath: str | Path) -> TechnologyParams:
        """Parse *filepath* (``TechnologieFile.xml``) and return params.

        Parameters
        ----------
        filepath : str | Path
            Path to the technology XML file.

        Returns
        -------
        TechnologyParams

        Raises
        ------
        FileNotFoundError
            If *filepath* does not exist.
        ET.ParseError
            If the XML is malformed (after repair attempts).
        KeyError
            If a required element or attribute is missing.

        Example
        -------
        >>> tech = TechnologyParams.from_file("tests/data/TechnologyFile.xml")
        >>> tech.nmos.threshold_voltage
        0.405
        >>> tech.pmos.threshold_voltage
        -0.564
        """
        text = Path(filepath).read_text(encoding="utf-8")

        # The real file has no single root element — <general>, <pmos>,
        # <nmos> are top-level siblings.  Wrap in a synthetic root so
        # ET.fromstring() succeeds.
        wrapped = f"<root>{text}</root>"

        try:
            root = ET.fromstring(wrapped)
        except ET.ParseError:
            # Repair: fix triple-dash XML comments (<!--- … --->) that
            # appear in some legacy ACST files.
            repaired = re.sub(r"<!---", "<!--", wrapped)
            repaired = re.sub(r"--->", "-->", repaired)
            root = ET.fromstring(repaired)

        # ── Thermal voltage ───────────────────────────────────────────
        general = root.find("general")
        if general is None:
            raise KeyError("Missing <general> section in technology file")
        vt_elem = general.find("thermalVoltage")
        if vt_elem is None:
            raise KeyError("Missing <thermalVoltage> in <general> section")
        vt_raw = vt_elem.get("Vt")
        if vt_raw is None:
            raise KeyError("Missing 'Vt' attribute on <thermalVoltage>")
        thermal_voltage = float(vt_raw)

        # ── NMOS / PMOS sections ──────────────────────────────────────
        nmos_elem = root.find("nmos")
        if nmos_elem is None:
            raise KeyError("Missing <nmos> section in technology file")
        pmos_elem = root.find("pmos")
        if pmos_elem is None:
            raise KeyError("Missing <pmos> section in technology file")

        nmos = _parse_transistor_params(nmos_elem)
        pmos = _parse_transistor_params(pmos_elem)

        return cls(thermal_voltage=thermal_voltage, nmos=nmos, pmos=pmos)


def _parse_transistor_params(element: ET.Element) -> TransistorTechParams:
    """Extract :class:`TransistorTechParams` from an ``<nmos>`` or ``<pmos>`` element.

    Uses :data:`_FIELD_MAP` to iterate every expected child element, read its
    attribute, and convert to ``float``.

    Parameters
    ----------
    element : ET.Element
        The ``<nmos>`` or ``<pmos>`` XML element.

    Returns
    -------
    TransistorTechParams

    Raises
    ------
    KeyError
        If a required child element or attribute is missing.
    """
    values: dict[str, float] = {}
    for tag, attr, field in _FIELD_MAP:
        child = element.find(tag)
        if child is None:
            raise KeyError(
                f"Missing <{tag}> element in <{element.tag}>"
            )
        raw = child.get(attr)
        if raw is None:
            raise KeyError(
                f"Missing attribute '{attr}' on <{tag}> in <{element.tag}>"
            )
        values[field] = float(raw)
    return TransistorTechParams(**values)
