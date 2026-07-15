"""
ckt_io — Input/output parsers and writers for ACST file formats.

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

from ckt_io.circuit_info_parser import (
    CircuitInformation,
    CircuitParameter,
    Specifications,
    load_circuit_information,
    parse_circuit_parameters,
    parse_specifications,
)
from ckt_io.device_types_parser import load_device_types
from ckt_io.hspice_mapping import DeviceLineMapping, HSpiceMapping
from ckt_io.hspice_parser import HSpiceParser
from ckt_io.hspice_writer import AcstNetlistWriter, HSpiceWriter
from ckt_io.supply_nets_parser import SupplyNetConfig
from ckt_io.technology_parser import TechnologyParams, TransistorTechParams

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
