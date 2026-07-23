"""Sizing variable system — integer-domain variables for the constraint solver.

Every continuous analog quantity (width, length, current, voltage, gm, …) is
mapped to an **integer** variable so the constraint solver (OR-Tools CP-SAT)
operates in a pure-integer domain.  Scale factors are documented per variable.

C++ ref: ``AutomaticSizing/incl/ConstraintProgram/Variables/``
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ckt_io.technology_parser import TransistorTechParams

from core.device import Device, TechType

# ── Single variable ──────────────────────────────────────────────────────


@dataclass
class SizingVariable:
    """One integer variable in the constraint problem.

    Attributes
    ----------
    name : str
        Solver-visible name, e.g. ``"m0_W"`` or ``"V_tail"``.
    lower : int
        Inclusive lower bound.
    upper : int
        Inclusive upper bound.
    description : str
        Human-readable purpose, used in logs and summaries.
    """

    name: str
    lower: int
    upper: int
    description: str = ""

    def __repr__(self) -> str:
        return f"SizingVariable({self.name!r}, [{self.lower}..{self.upper}])"


# ── Per-transistor variable bundle ───────────────────────────────────────


class TransistorVariables:
    """All sizing variables for one MOSFET (or matched group).

    The transistor model constraints (``TransistorConstraints``) relate
    these variables via the SHM equations.

    Scaling conventions
    -------------------
    ======  ============  ===========
    Var     Physical unit Scale
    ======  ============  ===========
    W, L    μm            ×1 (integer μm)
    Id      nA            ×1 (integer nA for solver precision)
    Vgs…    mV            ×1 (integer mV)
    gm      nA/V          ×1
    gds     nA/V          ×1
    area    μm²           ×1
    ======  ============  ===========

    C++ ref: ``AutomaticSizing::TransistorVariable``
    """

    def __init__(
        self,
        device_name: str,
        tech_type: TechType,
        tech_params: TransistorTechParams,
    ) -> None:
        self.device_name = device_name
        self.tech_type = tech_type
        self.tech = tech_params

        w_min = max(1, int(tech_params.min_width))
        l_min = max(1, int(tech_params.min_length))

        # Primary decision variables
        self.width = SizingVariable(
            f"{device_name}_W", w_min, 1000,
            f"{device_name} channel width [μm]",
        )
        self.length = SizingVariable(
            f"{device_name}_L", l_min, 100,
            f"{device_name} channel length [μm]",
        )

        # Derived electrical variables
        self.current = SizingVariable(
            f"{device_name}_Id", 1, 10_000_000,
            f"{device_name} drain current [nA]",
        )
        self.vgs = SizingVariable(
            f"{device_name}_Vgs", 1, 5000,
            f"{device_name} gate-source voltage [mV]",
        )
        self.vds = SizingVariable(
            f"{device_name}_Vds", 1, 5000,
            f"{device_name} drain-source voltage [mV]",
        )
        self.vov = SizingVariable(
            f"{device_name}_Vov", 1, 5000,
            f"{device_name} overdrive voltage [mV]",
        )
        self.gm = SizingVariable(
            f"{device_name}_gm", 1, 100_000_000,
            f"{device_name} transconductance [nA/V]",
        )
        self.gds = SizingVariable(
            f"{device_name}_gds", 0, 100_000_000,
            f"{device_name} output conductance [nA/V]",
        )
        self.area = SizingVariable(
            f"{device_name}_area", 1, 1_000_000,
            f"{device_name} gate area [μm²]",
        )

    @property
    def all_variables(self) -> list[SizingVariable]:
        """Return every variable in this bundle."""
        return [
            self.width, self.length,
            self.current,
            self.vgs, self.vds, self.vov,
            self.gm, self.gds,
            self.area,
        ]

    def __repr__(self) -> str:
        return (
            f"TransistorVariables({self.device_name!r}, "
            f"W=[{self.width.lower}..{self.width.upper}], "
            f"L=[{self.length.lower}..{self.length.upper}])"
        )


# ── Per-net voltage variable ─────────────────────────────────────────────


class VoltageVariable:
    """Variable for one internal net voltage [mV].

    C++ ref: ``AutomaticSizing::VoltageVariable``
    """

    def __init__(self, net_name: str, supply_voltage_mv: int = 5000) -> None:
        self.net_name = net_name
        self.var = SizingVariable(
            f"V_{net_name}", 0, supply_voltage_mv,
            f"net {net_name} voltage [mV]",
        )

    def __repr__(self) -> str:
        return f"VoltageVariable({self.net_name!r})"


# ── Central registry ─────────────────────────────────────────────────────


class SizingVariableRegistry:
    """Central registry of all sizing variables.

    Manages transistor variable bundles and net voltage variables.
    Provides factory methods that automatically pick the correct
    technology parameters (NMOS vs PMOS).

    C++ ref: composite of ``AutomaticSizing::Variables`` and the
    variable-creation code in ``AutomaticSizingAnalysis``.
    """

    def __init__(self) -> None:
        self.transistors: dict[str, TransistorVariables] = {}
        self.voltages: dict[str, VoltageVariable] = {}

    # ── Factories ────────────────────────────────────────────────────

    def add_transistor(
        self,
        device: Device,
        nmos_tech: TransistorTechParams,
        pmos_tech: TransistorTechParams,
    ) -> TransistorVariables:
        """Create and register variables for *device*.

        Picks NMOS or PMOS tech params based on ``device.tech_type``.
        """
        tp = nmos_tech if device.tech_type == TechType.N else pmos_tech
        tv = TransistorVariables(device.name, device.tech_type, tp)
        self.transistors[device.name] = tv
        return tv

    def add_voltage(
        self,
        net_name: str,
        supply_voltage_mv: int = 5000,
    ) -> VoltageVariable:
        """Create and register a voltage variable for *net_name*."""
        if net_name not in self.voltages:
            self.voltages[net_name] = VoltageVariable(net_name, supply_voltage_mv)
        return self.voltages[net_name]

    # ── Look-ups ─────────────────────────────────────────────────────

    def get_transistor(self, name: str) -> TransistorVariables:
        """Return the transistor variable bundle for *name*.

        Raises ``KeyError`` if *name* was never registered.
        """
        return self.transistors[name]

    def get_voltage(self, net_name: str) -> VoltageVariable:
        """Return the voltage variable for *net_name*."""
        return self.voltages[net_name]

    # ── Introspection ────────────────────────────────────────────────

    @property
    def total_variables(self) -> int:
        """Total number of individual ``SizingVariable`` instances."""
        n_tv = sum(len(tv.all_variables) for tv in self.transistors.values())
        return n_tv + len(self.voltages)

    def summary(self) -> str:
        """One-line summary for logging."""
        return (
            f"{len(self.transistors)} transistors "
            f"({self.total_variables} vars), "
            f"{len(self.voltages)} voltage nodes"
        )

    def __repr__(self) -> str:
        return (
            f"SizingVariableRegistry("
            f"transistors={len(self.transistors)}, "
            f"voltages={len(self.voltages)})"
        )
