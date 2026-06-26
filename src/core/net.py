from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .device import PinType
    from .terminal import Terminal


# ---------------------------------------------------------------------------
# Supply — maps to Core::Supply in C++
# ---------------------------------------------------------------------------

class SupplyType(Enum):
    """Mirrors the C++ Supply type string (VDD / GND / none)."""
    VDD = "vdd"
    GND = "gnd"
    NO_SUPPLY = "none"


@dataclass
class Supply:
    """
    Typed supply annotation for a net.

    Maps to Core::Supply in C++.
    `supply_type` is VDD, GND, or NO_SUPPLY.
    `level` distinguishes stacked supplies (VDD_1 vs VDD_2).  Level 0 = default.
    """
    supply_type: SupplyType = SupplyType.NO_SUPPLY
    level: int = 0

    # --- convenience factories (mirror C++ static helpers) ---
    @classmethod
    def vdd(cls, level: int = 0) -> Supply:
        return cls(SupplyType.VDD, level)

    @classmethod
    def gnd(cls, level: int = 0) -> Supply:
        return cls(SupplyType.GND, level)

    @classmethod
    def no_supply(cls) -> Supply:
        return cls(SupplyType.NO_SUPPLY, 0)

    @property
    def is_vdd(self) -> bool:
        return self.supply_type is SupplyType.VDD

    @property
    def is_gnd(self) -> bool:
        return self.supply_type is SupplyType.GND

    @property
    def is_supply(self) -> bool:
        return self.supply_type is not SupplyType.NO_SUPPLY


# ---------------------------------------------------------------------------
# NetId
# ---------------------------------------------------------------------------

class NetId:
    """Unique, hashable identifier for a net."""
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other): return isinstance(other, NetId) and self.name == other.name
    def __hash__(self): return hash(self.name)
    def __repr__(self): return f"NetId({self.name!r})"


# ---------------------------------------------------------------------------
# Net
# ---------------------------------------------------------------------------

class Net:
    """
    An electrical node connecting multiple terminals (pins).

    Maps to Core::Net in C++.
    Every device pin is wired to exactly one Net; multiple pins can
    share the same Net (that's what makes a connection).
    """
    def __init__(self, net_id: NetId):
        self._id = net_id
        self._terminals: list[Terminal] = []
        self.is_global: bool = False
        self._supply: Supply = Supply.no_supply()

    # --- identity ----------------------------------------------------------
    @property
    def name(self) -> str:
        return self._id.name

    @property
    def net_id(self) -> NetId:
        return self._id

    # --- supply ------------------------------------------------------------
    @property
    def supply(self) -> Supply:
        return self._supply

    @supply.setter
    def supply(self, value: Supply) -> None:
        self._supply = value

    def is_supply(self) -> bool:
        return self._supply.is_supply

    def is_vdd(self) -> bool:
        return self._supply.is_vdd

    def is_ground(self) -> bool:
        return self._supply.is_gnd

    def is_power(self) -> bool:
        return self.is_supply()

    # --- terminals (pins) --------------------------------------------------
    @property
    def terminals(self) -> list[Terminal]:
        return list(self._terminals)

    def add_terminal(self, terminal: Terminal) -> None:
        self._terminals.append(terminal)

    def get_terminals_by_type(self, pin_type: PinType) -> list[Terminal]:
        """Return all terminals on this net that match *pin_type*.

        Mirrors C++ Net::getPins(PinType)."""
        return [t for t in self._terminals if t.pin_type == pin_type]

    def has_terminal_type(self, pin_type: PinType) -> bool:
        """True if at least one terminal of *pin_type* is connected."""
        return any(t.pin_type == pin_type for t in self._terminals)

    def has_terminals(self) -> bool:
        return len(self._terminals) > 0

    def clear_terminals(self) -> None:
        """Remove all terminals from this net (used during net merging)."""
        self._terminals.clear()
