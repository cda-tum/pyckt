"""Sizing result — output data containers for the constraint solver.

Holds solved transistor sizes and computed performance metrics.
These are pure data objects produced by ``solver.py`` and consumed
by ``writer.py`` and ``analysis.py``.

C++ ref: ``AutomaticSizing/incl/Results/``
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Per-device solved values ─────────────────────────────────────────────


@dataclass
class DeviceSizing:
    """Solved sizing values for one MOSFET.

    All values are in integer-scaled units consistent with
    :mod:`sizing.variables`: ``width``/``length`` in μm, ``current`` in nA,
    ``vgs``/``vds``/``vov`` in mV, ``gm``/``gds`` in nA/V, ``area`` in μm².
    """

    name: str
    width: int = 0
    length: int = 0
    current: int = 0
    vgs: int = 0
    vds: int = 0
    vov: int = 0
    gm: int = 0
    gds: int = 0
    area: int = 0

    # ── Physical-unit accessors ──────────────────────────────────────

    @property
    def width_um(self) -> float:
        """Channel width [μm]."""
        return float(self.width)

    @property
    def length_um(self) -> float:
        """Channel length [μm]."""
        return float(self.length)

    @property
    def current_ua(self) -> float:
        """Drain current [μA]."""
        return self.current / 1e3

    @property
    def current_ma(self) -> float:
        """Drain current [mA]."""
        return self.current / 1e6

    @property
    def vgs_v(self) -> float:
        """Gate-source voltage [V]."""
        return self.vgs / 1e3

    @property
    def vds_v(self) -> float:
        """Drain-source voltage [V]."""
        return self.vds / 1e3

    @property
    def vov_v(self) -> float:
        """Overdrive voltage [V]."""
        return self.vov / 1e3

    @property
    def gm_uav(self) -> float:
        """Transconductance [μA/V]."""
        return self.gm / 1e3

    @property
    def gds_uav(self) -> float:
        """Output conductance [μA/V]."""
        return self.gds / 1e3

    @property
    def area_um2(self) -> float:
        """Gate area [μm²]."""
        return float(self.area)

    def summary_line(self) -> str:
        """One-line summary: ``name  W/L = w/l μm  Id = x μA``."""
        return (
            f"{self.name:>8s}  W/L = {self.width}/{self.length} μm  "
            f"Id = {self.current_ua:.1f} μA  "
            f"gm = {self.gm_uav:.1f} μA/V"
        )


# ── Expected performance ─────────────────────────────────────────────────


@dataclass
class ExpectedPerformance:
    """Computed performance metrics from solved transistor sizes.

    Values are in standard engineering units (not integer-scaled).

    Attributes
    ----------
    gain_db : float
        Open-loop voltage gain [dB].
    transit_freq_mhz : float
        Unity-gain frequency [MHz].
    slew_rate : float
        Slew rate [V/μs].
    power_mw : float
        Total power consumption [mW].
    total_area_um2 : float
        Sum of all gate areas [μm²].
    phase_margin_deg : float
        Phase margin [°] (0.0 if not applicable / single-stage).
    vout_min_v : float
        Minimum output voltage [V].
    vout_max_v : float
        Maximum output voltage [V].
    """

    gain_db: float = 0.0
    transit_freq_mhz: float = 0.0
    slew_rate: float = 0.0
    power_mw: float = 0.0
    total_area_um2: float = 0.0
    phase_margin_deg: float = 0.0
    vout_min_v: float = 0.0
    vout_max_v: float = 0.0

    def summary(self) -> str:
        """Multi-line summary of all performance metrics."""
        lines = [
            "Expected Performance",
            "─" * 40,
            f"  Gain           : {self.gain_db:.1f} dB",
            f"  Transit freq   : {self.transit_freq_mhz:.2f} MHz",
            f"  Slew rate      : {self.slew_rate:.2f} V/μs",
            f"  Power          : {self.power_mw:.3f} mW",
            f"  Total area     : {self.total_area_um2:.1f} μm²",
            f"  Phase margin   : {self.phase_margin_deg:.1f}°",
            f"  Vout range     : [{self.vout_min_v:.3f}, {self.vout_max_v:.3f}] V",
        ]
        return "\n".join(lines)


# ── Aggregate result ─────────────────────────────────────────────────────


@dataclass
class SizingResult:
    """Complete output of the sizing solver.

    Bundles per-device solutions and computed performance into a single
    object that ``writer.py`` serialises to XML / HSpice.

    C++ ref: ``AutomaticSizing::Result``
    """

    devices: dict[str, DeviceSizing] = field(default_factory=dict)
    performance: ExpectedPerformance = field(default_factory=ExpectedPerformance)
    solver_status: str = "unsolved"
    iterations: int = 0
    solve_time_seconds: float = 0.0
    objective_value: float | None = None

    # ── Factories ────────────────────────────────────────────────────

    @classmethod
    def from_solver_values(
        cls,
        device_values: dict[str, dict[str, int]],
        *,
        solver_status: str = "optimal",
        iterations: int = 0,
        solve_time_seconds: float = 0.0,
        objective_value: float | None = None,
    ) -> SizingResult:
        """Build a result from raw solver output.

        Parameters
        ----------
        device_values : dict
            ``{device_name: {"width": int, "length": int, …}}``.
        """
        devices = {}
        for name, vals in device_values.items():
            devices[name] = DeviceSizing(
                name=name,
                width=vals.get("width", 0),
                length=vals.get("length", 0),
                current=vals.get("current", 0),
                vgs=vals.get("vgs", 0),
                vds=vals.get("vds", 0),
                vov=vals.get("vov", 0),
                gm=vals.get("gm", 0),
                gds=vals.get("gds", 0),
                area=vals.get("area", 0),
            )
        return cls(
            devices=devices,
            solver_status=solver_status,
            iterations=iterations,
            solve_time_seconds=solve_time_seconds,
            objective_value=objective_value,
        )

    # ── Queries ──────────────────────────────────────────────────────

    def get_device(self, name: str) -> DeviceSizing:
        """Return solved sizing for *name*. Raises ``KeyError``."""
        return self.devices[name]

    @property
    def device_names(self) -> list[str]:
        """Sorted list of all solved device names."""
        return sorted(self.devices.keys())

    @property
    def total_current_na(self) -> int:
        """Sum of all drain currents [nA]."""
        return sum(d.current for d in self.devices.values())

    @property
    def total_area_um2(self) -> float:
        """Sum of all gate areas [μm²]."""
        return sum(d.area for d in self.devices.values())
    def meets_specs(self, specs: object) -> bool:
        """Return ``True`` if all solved performance metrics satisfy *specs*.

        Checks every non-zero specification field against the corresponding
        ``ExpectedPerformance`` value.  A field of zero (the default) is
        treated as "unconstrained" and is skipped.

        Parameters
        ----------
        specs :
            A :class:`ckt_io.circuit_info_parser.Specifications` instance
            (typed as ``object`` to avoid a circular import).

        Returns
        -------
        bool
            ``False`` if any active specification is violated, ``True``
            otherwise.  Also returns ``False`` when no devices are present
            (infeasible result).
        """
        if not self.devices:
            return False
        p = self.performance
        checks = [
            (specs.min_gain,         lambda: p.gain_db >= specs.min_gain),
            (specs.min_transit_freq, lambda: p.transit_freq_mhz >= specs.min_transit_freq),
            (specs.max_slew_rate,    lambda: p.slew_rate <= specs.max_slew_rate),
            (specs.max_power,        lambda: p.power_mw <= specs.max_power),
            (specs.max_area,         lambda: p.total_area_um2 <= specs.max_area),
            (specs.phase_margin,     lambda: p.phase_margin_deg >= specs.phase_margin),
            (specs.vout_max,         lambda: p.vout_max_v <= specs.vout_max),
            (specs.vout_min,         lambda: p.vout_min_v >= specs.vout_min),
        ]
        return all(check() for threshold, check in checks if threshold != 0.0)
    # ── Display ──────────────────────────────────────────────────────

    def summary(self) -> str:
        """Multi-line summary of all device sizings and performance."""
        lines = [
            f"SizingResult — {self.solver_status} ({self.iterations} iterations, {self.solve_time_seconds:.3f}s)",
            "═" * 60,
        ]
        if self.objective_value is not None:
            lines.append(f"Objective value : {self.objective_value:.3f}")
        for name in self.device_names:
            lines.append(self.devices[name].summary_line())
        lines.append("")
        lines.append(self.performance.summary())
        return "\n".join(lines)

    def __repr__(self) -> str:
        n = len(self.devices)
        return f"SizingResult({n} devices, status={self.solver_status!r})"
