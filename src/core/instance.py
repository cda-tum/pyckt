from __future__ import annotations

from dataclasses import dataclass, field

from .common import UnknownParameterError, require_non_empty


@dataclass(frozen=True, slots=True)
class CellTripleId:
    """Stable identifier for a hierarchical cell view: library/cell/view."""
    library_name: str
    cell_name: str
    view_name: str = "schematic"

    def qualified_name(self) -> str:
        return f"{self.library_name}/{self.cell_name}/{self.view_name}"


@dataclass(slots=True)
class Instance:
    """Reference to a child cell used by hierarchical netlists."""
    name: str
    cell_id: CellTripleId
    connections: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, str | float | int] = field(default_factory=dict)

    def connect(self, pin_name: str, net_name: str) -> None:
        require_non_empty(pin_name, "pin_name")
        require_non_empty(net_name, "net_name")
        self.connections[pin_name] = net_name

    def set_param(self, key: str, value: str | float | int) -> None:
        self.parameters[key] = value

    def get_parameter(self, key: str) -> str | float | int:
        try:
            return self.parameters[key]
        except KeyError as exc:
            raise UnknownParameterError(
                f"{self.name}: unknown parameter '{key}'"
            ) from exc
