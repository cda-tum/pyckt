from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .common import InvalidPinError, UnknownParameterError

if TYPE_CHECKING:
    from .instance import CellTripleId
    from .net import Net
    from .terminal import Terminal

class _CaseInsensitiveEnum(Enum):
    @classmethod
    def from_text(cls, raw: str):
        text = raw.strip()
        if not text:
            raise KeyError(f"Empty {cls.__name__}")
        key = text.casefold()
        for member in cls:
            if member.name.casefold() == key or str(member.value).casefold() == key:
                return member
        raise KeyError(f"Unknown {cls.__name__}: {raw!r}")
    
    
class DeviceType(_CaseInsensitiveEnum):
    """Supported device types — matches ACST's deviceTypes.xcat."""
    MOSFET    = "Mosfet"
    BIPOLAR   = "Bipolar"
    CAPACITOR = "Capacitor"
    RESISTOR  = "Resistor"
    INDUCTOR  = "Inductor"
    DIODE     = "Diode"
    WIRE      = "Wire"

class TechType(_CaseInsensitiveEnum):
    """Technology type / doping flavor."""
    N         = "n"
    P         = "p"
    UNDEFINED = "undefined"

class PinType(_CaseInsensitiveEnum):
    """Pin types across all supported device types."""
    # MOSFET pins
    DRAIN     = "Drain"
    GATE      = "Gate"
    SOURCE    = "Source"
    BULK      = "Bulk"
    # Bipolar pins
    COLLECTOR = "Collector"
    BASE      = "Base"
    EMITTER   = "Emitter"
    # Two-terminal device pins
    PLUS      = "Plus"
    MINUS     = "Minus"
    # Diode pins
    ANODE     = "Anode"
    CATHODE   = "Cathode"
    
@dataclass
class PinTypeInfo:
    pin_type: PinType
    optional: bool = False
    auto_connection: PinType | None = None


@dataclass
class DeviceTypeInfo:
    pin_types: list[PinTypeInfo]
    tech_types: list[TechType]

class DeviceTypeRegister:
    """
    Registry of supported device types and their pin configurations.
    Populated from the deviceTypes.xcat file.
    Maps to Core::DeviceTypeRegister in C++.
    """
    def __init__(self):
        self._entries: dict[DeviceType, DeviceTypeInfo] = {}

    def register(self, device_type: DeviceType,
                 pin_types: list[PinTypeInfo],
                 tech_types: list[TechType]) -> None:
        self._entries[device_type] = DeviceTypeInfo(
            pin_types=list(pin_types),
            tech_types=list(tech_types),
        )

    def get_pin_types(self, device_type: DeviceType) -> list[PinTypeInfo]:
        return list(self._entries[device_type].pin_types)

    def get_tech_types(self, device_type: DeviceType) -> list[TechType]:
        return list(self._entries[device_type].tech_types)
    
    
class Device:
    """
    A single circuit device (MOSFET, capacitor, resistor, …).

    Maps to Core::Device in C++.
    Each device has a unique name, a device type, a tech type,
    and terminals connecting its pins to nets.
    """
    def __init__(
        self,
        name: str,
        device_type: DeviceType,
        tech_type: TechType,
        cell_triple_id: CellTripleId | None = None,
    ):
        self.name = name
        self.device_type = device_type
        self.tech_type = tech_type
        self.cell_triple_id = cell_triple_id
        self._terminals: dict[PinType, Terminal] = {}
        self._parameters: dict[str, str | float | int] = {}

    # ── Parameters ──────────────────────────────────────────────────────
    def set_parameter(self, key: str, value: str | float | int) -> None:
        self._parameters[key] = value

    def get_parameter(self, key: str) -> str | float | int:
        try:
            return self._parameters[key]
        except KeyError as exc:
            raise UnknownParameterError(
                f"{self.name}: unknown parameter '{key}'"
            ) from exc

    @property
    def parameters(self) -> dict[str, str | float | int]:
        return dict(self._parameters)

    # ── Terminals ───────────────────────────────────────────────────────
    def add_terminal(self, terminal: Terminal) -> None:
        self._terminals[terminal.pin_type] = terminal

    def get_terminal(self, pin_type: PinType) -> Terminal:
        try:
            return self._terminals[pin_type]
        except KeyError as e:
            raise InvalidPinError(f"{self.name}: missing terminal for {pin_type.name}") from e

    def get_net(self, pin_type: PinType) -> Net:
        return self._terminals[pin_type].net

    @property
    def terminals(self) -> dict[PinType, Terminal]:
        return dict(self._terminals)

    @property
    def is_mosfet(self) -> bool:
        return self.device_type == DeviceType.MOSFET

    @property
    def is_nmos(self) -> bool:
        return self.is_mosfet and self.tech_type == TechType.N

    @property
    def is_pmos(self) -> bool:
        return self.is_mosfet and self.tech_type == TechType.P
