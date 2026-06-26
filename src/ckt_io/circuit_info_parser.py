"""
Circuit information and specifications parser.

Reads ``CircuitParameterAndSpecifications.xml`` (for automatic sizing) or
``CircuitSpecifications.xml`` (for synthesis) and extracts operating conditions,
pin-to-net assignments, and performance specifications.

Data structures produced:

  - :class:`CircuitParameter` — pin/net assignments and operating conditions.
  - :class:`Specifications` — target performance metrics.
  - :class:`CircuitInformation` — aggregate container combining parameters,
    specifications, and technology params.

Maps to ``CircuitInformation::CircuitInformation`` and
``CircuitInformation::CircuitParameter`` in the C++ ACST code.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from ckt_io.technology_parser import TechnologyParams

# ── Operating conditions / pin assignments ────────────────────────────────


@dataclass
class CircuitParameter:
    """Operating conditions and pin-to-net assignments.

    Parsed from the ``<CircuitParameter>`` section of the XML file.

    Attributes
    ----------
    load_capacities : list[tuple[str, float]]
        ``[(device_name, value_pF), …]``.
    supply_voltage : tuple[str, float]
        ``(net_name, voltage_V)``.
    ground : tuple[str, float]
        ``(net_name, voltage_V)``.
    bias_current : tuple[str, float]
        ``(net_name, current_μA)``.
    input_plus : tuple[str, float]
        ``(net_name, voltage_V)``  — non-inverting input.
    input_minus : tuple[str, float]
        ``(net_name, voltage_V)`` — inverting input.
    output_net : str
        Name of the output net.
    """

    load_capacities: list[tuple[str, float]] = field(default_factory=list)
    supply_voltage: tuple[str, float] = ("", 0.0)
    ground: tuple[str, float] = ("", 0.0)
    bias_current: tuple[str, float] = ("", 0.0)
    input_plus: tuple[str, float] = ("", 0.0)
    input_minus: tuple[str, float] = ("", 0.0)
    output_net: str = ""


# ── Performance specifications ────────────────────────────────────────────


@dataclass
class Specifications:
    """Performance specifications for sizing or synthesis.

    Fields that are specific to the synthesis flow are optional (``None``
    when parsing an automatic-sizing file).

    Attributes
    ----------
    min_gain : float
        Minimum gain [dB].
    min_transit_freq : float
        Minimum transit (unity-gain) frequency [MHz].
    max_slew_rate : float
        Maximum slew rate [V/μs].
    min_cmrr : float
        Minimum CMRR [dB].
    min_pos_psrr : float
        Minimum positive PSRR [dB].
    min_neg_psrr : float
        Minimum negative PSRR [dB].
    vout_max : float
        Maximum output voltage [V].
    vout_min : float
        Minimum output voltage [V].
    vcm_max : float
        Maximum common-mode input voltage [V].
    vcm_min : float
        Minimum common-mode input voltage [V].
    gate_overdrive : float
        Gate-overdrive voltage [V].
    max_power : float
        Maximum power consumption [mW].
    max_area : float
        Maximum area [μm²].
    phase_margin : float
        Phase margin [degrees].
    complementary : bool | None
        Synthesis-only: complementary topology flag.
    fully_differential : bool | None
        Synthesis-only: fully-differential flag.
    settling_time : float | None
        Synthesis-only: settling time [ns].
    offset_error_min : float | None
        Synthesis-only: minimum offset error [mV].
    offset_error_max : float | None
        Synthesis-only: maximum offset error [mV].
    """

    min_gain: float = 0.0
    min_transit_freq: float = 0.0
    max_slew_rate: float = 0.0
    min_cmrr: float = 0.0
    min_pos_psrr: float = 0.0
    min_neg_psrr: float = 0.0
    vout_max: float = 0.0
    vout_min: float = 0.0
    vcm_max: float = 0.0
    vcm_min: float = 0.0
    gate_overdrive: float = 0.0
    max_power: float = 0.0
    max_area: float = 0.0
    phase_margin: float = 0.0
    # Synthesis-only fields
    complementary: bool | None = None
    fully_differential: bool | None = None
    settling_time: float | None = None
    offset_error_min: float | None = None
    offset_error_max: float | None = None


# ── Aggregate container ───────────────────────────────────────────────────


@dataclass
class CircuitInformation:
    """Aggregated circuit info needed by the sizing engine.

    Attributes
    ----------
    parameters : CircuitParameter
        Operating conditions and pin assignments.
    specifications : Specifications
        Target performance metrics.
    technology : TechnologyParams
        Process parameters (NMOS + PMOS + thermal voltage).
    """

    parameters: CircuitParameter
    specifications: Specifications
    technology: TechnologyParams


# ── XML reader helper ─────────────────────────────────────────────────────


def _read_xml(filepath: str | Path) -> ET.Element:
    """Read a rootless XML file, wrap in ``<root>``, and repair legacy comments.

    The circuit-information XML files produced by ACST have no single root
    element and may contain triple-dash comments (``<!--- … --->``).
    This helper normalises both issues.
    """
    text = Path(filepath).read_text(encoding="utf-8")
    wrapped = f"<root>{text}</root>"
    try:
        return ET.fromstring(wrapped)
    except ET.ParseError:
        repaired = re.sub(r"<!---", "<!--", wrapped)
        repaired = re.sub(r"--->", "-->", repaired)
        return ET.fromstring(repaired)


def _parse_pin_section(
    parent: ET.Element,
    section_tag: str,
    value_tag: str,
    value_attr: str,
) -> tuple[str, float]:
    """Extract ``(net_name, numeric_value)`` from a pin section."""
    section = parent.find(section_tag)
    if section is None:
        raise KeyError(f"Missing <{section_tag}> in <CircuitParameter>")
    net_elem = section.find("NetName")
    if net_elem is None or net_elem.text is None:
        raise KeyError(f"Missing <NetName> in <{section_tag}>")
    val_elem = section.find(value_tag)
    if val_elem is None:
        raise KeyError(f"Missing <{value_tag}> in <{section_tag}>")
    raw = val_elem.get(value_attr)
    if raw is None:
        raise KeyError(
            f"Missing attribute '{value_attr}' on <{value_tag}>"
        )
    return (net_elem.text.strip(), float(raw.strip()))


# ── Specification field maps ──────────────────────────────────────────────
# Single-attribute elements: (xml_tag, xml_attr, Specifications field name)

_SPEC_SINGLE: list[tuple[str, str, str]] = [
    ("minimumGain", "A", "min_gain"),
    ("minimumTransientFrequency", "ft", "min_transit_freq"),
    ("maximumSlewRate", "SR", "max_slew_rate"),
    ("minimumCMRR", "CMRR", "min_cmrr"),
    ("minimumPosPSRR", "posPSRR", "min_pos_psrr"),
    ("minimumNegPSRR", "negPSRR", "min_neg_psrr"),
    ("GateOverDriveVoltage", "Vover", "gate_overdrive"),
    ("maximumPowerConsumption", "P", "max_power"),
    ("maximumArea", "Area", "max_area"),
    ("phaseMargin", "PM", "phase_margin"),
]

# Dual-attribute elements: (xml_tag, [(xml_attr, field_name), …])

_SPEC_DUAL: list[tuple[str, list[tuple[str, str]]]] = [
    ("OutputVoltageSwing", [("Voutmax", "vout_max"), ("Voutmin", "vout_min")]),
    ("CommonModeInputVoltage", [("Vcmmax", "vcm_max"), ("Vcmmin", "vcm_min")]),
]


# ── Parsing functions ─────────────────────────────────────────────────────


def parse_circuit_parameters(filepath: str | Path) -> CircuitParameter:
    """Parse ``<CircuitParameter>`` section from *filepath*.

    Parameters
    ----------
    filepath : str | Path
        Path to ``CircuitParameterAndSpecifications.xml``.

    Returns
    -------
    CircuitParameter

    Raises
    ------
    FileNotFoundError
        If *filepath* does not exist.
    ET.ParseError
        If the XML is malformed.
    """
    root = _read_xml(filepath)
    cp = root.find("CircuitParameter")
    if cp is None:
        raise KeyError("Missing <CircuitParameter> section")

    # ── Load capacities ───────────────────────────────────────────────
    load_caps: list[tuple[str, float]] = []
    lc_section = cp.find("LoadCapacities")
    if lc_section is not None:
        for lc in lc_section.findall("LoadCapacity"):
            name_elem = lc.find("DeviceName")
            val_elem = lc.find("Value")
            if name_elem is None or name_elem.text is None:
                raise KeyError("Missing <DeviceName> in <LoadCapacity>")
            if val_elem is None or val_elem.text is None:
                raise KeyError("Missing <Value> in <LoadCapacity>")
            load_caps.append(
                (name_elem.text.strip(), float(val_elem.text.strip()))
            )

    # ── Pin sections ──────────────────────────────────────────────────
    supply = _parse_pin_section(cp, "SupplyVoltagePin", "SupplyVoltage", "Vdd")
    ground = _parse_pin_section(cp, "GroundPin", "GroundVoltage", "Gnd")
    bias = _parse_pin_section(cp, "CurrentBiasPin", "BiasCurrent", "Ibias")
    in_minus = _parse_pin_section(cp, "InputPinMinus", "InputVoltage", "Vin")
    in_plus = _parse_pin_section(cp, "InputPinPlus", "InputVoltage", "Vin")

    # ── Output pin (net name only) ────────────────────────────────────
    out_section = cp.find("OutputPin")
    if out_section is None:
        raise KeyError("Missing <OutputPin> in <CircuitParameter>")
    out_net_elem = out_section.find("NetName")
    if out_net_elem is None or out_net_elem.text is None:
        raise KeyError("Missing <NetName> in <OutputPin>")

    return CircuitParameter(
        load_capacities=load_caps,
        supply_voltage=supply,
        ground=ground,
        bias_current=bias,
        input_plus=in_plus,
        input_minus=in_minus,
        output_net=out_net_elem.text.strip(),
    )


def parse_specifications(filepath: str | Path) -> Specifications:
    """Parse ``<Specifications>`` section from *filepath*.

    Works for both ``CircuitParameterAndSpecifications.xml`` (sizing) and
    ``CircuitSpecifications.xml`` (synthesis).  Synthesis-only fields are
    set when present, left as ``None`` otherwise.

    Parameters
    ----------
    filepath : str | Path
        Path to an XML file containing a ``<Specifications>`` element.

    Returns
    -------
    Specifications

    Raises
    ------
    FileNotFoundError
        If *filepath* does not exist.
    ET.ParseError
        If the XML is malformed.
    """
    root = _read_xml(filepath)
    spec_elem = root.find("Specifications")
    if spec_elem is None:
        raise KeyError("Missing <Specifications> section")

    values: dict[str, float] = {}

    # ── Single-attribute fields ───────────────────────────────────────
    for tag, attr, field_name in _SPEC_SINGLE:
        child = spec_elem.find(tag)
        if child is None:
            raise KeyError(f"Missing <{tag}> in <Specifications>")
        raw = child.get(attr)
        if raw is None:
            raise KeyError(f"Missing attribute '{attr}' on <{tag}>")
        values[field_name] = float(raw.strip())

    # ── Dual-attribute fields ─────────────────────────────────────────
    for tag, attrs in _SPEC_DUAL:
        child = spec_elem.find(tag)
        if child is None:
            raise KeyError(f"Missing <{tag}> in <Specifications>")
        for attr, field_name in attrs:
            raw = child.get(attr)
            if raw is None:
                raise KeyError(f"Missing attribute '{attr}' on <{tag}>")
            values[field_name] = float(raw.strip())

    # ── Synthesis-only optional fields ────────────────────────────────
    comp_elem = spec_elem.find("complementary")
    complementary: bool | None = None
    if comp_elem is not None and comp_elem.text:
        complementary = comp_elem.text.strip().lower() == "yes"

    fd_elem = spec_elem.find("fullyDifferential")
    fully_differential: bool | None = None
    if fd_elem is not None and fd_elem.text:
        fully_differential = fd_elem.text.strip().lower() == "yes"

    st_elem = spec_elem.find("settlingTime")
    settling_time: float | None = None
    if st_elem is not None:
        raw = st_elem.get("ts")
        if raw is None:
            raise KeyError("Missing attribute 'ts' on <settlingTime>")
        settling_time = float(raw.strip())

    oe_elem = spec_elem.find("OffsetError")
    offset_min: float | None = None
    offset_max: float | None = None
    if oe_elem is not None:
        raw_min = oe_elem.get("Vmin")
        raw_max = oe_elem.get("Vmax")
        if raw_min is None or raw_max is None:
            raise KeyError("Missing 'Vmin' or 'Vmax' on <OffsetError>")
        offset_min = float(raw_min.strip())
        offset_max = float(raw_max.strip())

    return Specifications(
        **values,
        complementary=complementary,
        fully_differential=fully_differential,
        settling_time=settling_time,
        offset_error_min=offset_min,
        offset_error_max=offset_max,
    )


def load_circuit_information(
    circuit_spec_path: str | Path,
    technology_path: str | Path,
) -> CircuitInformation:
    """Load all circuit info needed by the sizing engine.

    Convenience function that combines :func:`parse_circuit_parameters`,
    :func:`parse_specifications`, and
    :func:`~ckt_io.technology_parser.TechnologyParams.from_file` into a
    single :class:`CircuitInformation` object.

    Parameters
    ----------
    circuit_spec_path : str | Path
        Path to ``CircuitParameterAndSpecifications.xml``.
    technology_path : str | Path
        Path to ``TechnologieFile.xml``.

    Returns
    -------
    CircuitInformation
    """
    params = parse_circuit_parameters(circuit_spec_path)
    specs = parse_specifications(circuit_spec_path)
    tech = TechnologyParams.from_file(technology_path)
    return CircuitInformation(parameters=params, specifications=specs, technology=tech)
