"""
pyckt.io — Input/output parsers and writers for ACST file formats.

This module provides parsers for every input file format used by ACST
and a writer for HSpice netlist output.

Parsers
-------
- :class:`HSpiceParser`           — ``.hspice`` circuit netlists
- :class:`HSpiceMapping`          — ``HSpiceMapping.xcat`` device-line rules
- :class:`DeviceLineMapping`      — single device-type parsing rule
- :class:`SupplyNetConfig`        — ``supplyNets.xcat`` supply/ground labels
- :func:`load_device_types`       — ``deviceTypes.xcat`` → DeviceTypeRegister
- :class:`TechnologyParams`       — ``TechnologieFile.xml`` process params
- :class:`TransistorTechParams`   — per-flavour (NMOS/PMOS) params
- :class:`CircuitParameter`       — operating conditions / pin assignments
- :class:`Specifications`         — performance specs
- :class:`CircuitInformation`     — aggregate container

Writer
------
- :class:`HSpiceWriter`           — Circuit → ``.ckt`` HSpice output
- :class:`AcstNetlistWriter`      — Circuit → ACST topology-library ``.ckt``
"""

from pyckt.io.circuit_info_parser import (
    CircuitInformation,
    CircuitParameter,
    Specifications,
    load_circuit_information,
    parse_circuit_parameters,
    parse_specifications,
)
from pyckt.io.device_types_parser import load_device_types
from pyckt.io.hspice_mapping import DeviceLineMapping, HSpiceMapping
from pyckt.io.hspice_parser import HSpiceParser
from pyckt.io.hspice_writer import AcstNetlistWriter, HSpiceWriter
from pyckt.io.supply_nets_parser import SupplyNetConfig
from pyckt.io.technology_parser import TechnologyParams, TransistorTechParams

__all__ = [
    # mapping
    "DeviceLineMapping",
    "HSpiceMapping",
    # supply
    "SupplyNetConfig",
    # device types
    "load_device_types",
    # hspice parser
    "HSpiceParser",
    # technology
    "TechnologyParams",
    "TransistorTechParams",
    # circuit info
    "CircuitInformation",
    "CircuitParameter",
    "Specifications",
    "load_circuit_information",
    "parse_circuit_parameters",
    "parse_specifications",
    # writer
    "HSpiceWriter",
    "AcstNetlistWriter",
]
