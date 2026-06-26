from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .net import Net


class PortType(Enum):
    """Direction of a circuit-boundary port.

    Maps to C++ TerminalType (input / output / inout).
    """
    INPUT  = "input"
    OUTPUT = "output"
    INOUT  = "inout"


class Port:
    """
    A circuit-level I/O port (input, output, or inout).

    Maps to C++ Terminal (the circuit-boundary concept, NOT the pin-edge).
    Each port has a unique name, a direction, and an optional net binding.
    """
    def __init__(self, name: str, port_type: PortType, net: Net | None = None):
        self.name = name
        self.port_type = port_type
        self.net = net

    @property
    def is_input(self) -> bool:
        return self.port_type is PortType.INPUT

    @property
    def is_output(self) -> bool:
        return self.port_type is PortType.OUTPUT

    @property
    def is_inout(self) -> bool:
        return self.port_type is PortType.INOUT

    def __repr__(self) -> str:
        return f"Port({self.name!r}, {self.port_type.name})"
