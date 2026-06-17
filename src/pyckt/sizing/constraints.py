"""Sizing constraints — translates circuit physics into solver constraints.

Each constraint class is a **pure data description** of a mathematical
relation.  The ``post(solver)`` method (filled in Week 7) will translate
it into OR-Tools CP-SAT primitives.

C++ ref: ``AutomaticSizing/src/ConstraintProgram/``
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .variables import (
    SizingVariable,
    SizingVariableRegistry,
    TransistorVariables,
)

if TYPE_CHECKING:
    from partitioning.result import PartitionResult, StageType
    from pyckt.core.circuit import Circuit
    from pyckt.core.device import Device, PinType
    from pyckt.io.circuit_info_parser import (
        CircuitParameter,
        Specifications,
    )
    from pyckt.io.technology_parser import TechnologyParams, TransistorTechParams
    from recognition.rulegen import (
        SizingRule,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  Base classes
# ═══════════════════════════════════════════════════════════════════════════


class Constraint(ABC):
    """Abstract base for every sizing constraint."""

    @abstractmethod
    def description(self) -> str:
        """Human-readable description for logs and summaries."""
        ...

    @abstractmethod
    def post(self, solver: object) -> None:
        """Add this constraint to *solver*.

        ``solver`` will be the OR-Tools ``CpModel`` wrapper (Week 7).
        """
        ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.description()})"


def _solver_call(solver: object, method: str, *args):
    """Call *method* on solver adapter with a clear error if unsupported."""
    fn = getattr(solver, method, None)
    if fn is None:
        raise TypeError(
            f"Solver adapter must implement `{method}()` for sizing constraint posting"
        )
    return fn(*args)


# ── Primitive constraint types ───────────────────────────────────────────


class EqualityConstraint(Constraint):
    """``var_a == var_b``."""

    def __init__(self, var_a: SizingVariable, var_b: SizingVariable) -> None:
        self.a = var_a
        self.b = var_b

    def description(self) -> str:
        return f"{self.a.name} == {self.b.name}"

    def post(self, solver: object) -> None:
        _solver_call(solver, "add_equality", self.a, self.b)


class ProductConstraint(Constraint):
    """``result == a * b`` (integer multiplication)."""

    def __init__(
        self,
        result: SizingVariable,
        a: SizingVariable,
        b: SizingVariable,
    ) -> None:
        self.result = result
        self.a = a
        self.b = b

    def description(self) -> str:
        return f"{self.result.name} == {self.a.name} * {self.b.name}"

    def post(self, solver: object) -> None:
        _solver_call(solver, "add_product", self.result, self.a, self.b)


class LinearConstraint(Constraint):
    r"""``\sum coeff_i \cdot var_i  \; \text{rel} \; bound``.

    *rel* is one of ``">="``, ``"<="``, ``"=="``.
    """

    def __init__(
        self,
        terms: list[tuple[int, SizingVariable]],
        relation: str,
        bound: int,
    ) -> None:
        self.terms = terms
        self.relation = relation
        self.bound = bound

    def description(self) -> str:
        parts = " + ".join(f"{c}·{v.name}" for c, v in self.terms)
        return f"{parts} {self.relation} {self.bound}"

    def post(self, solver: object) -> None:
        _solver_call(solver, "add_linear", self.terms, self.relation, self.bound)


class BoundsConstraint(Constraint):
    """``lower <= var <= upper`` (tighten existing bounds)."""

    def __init__(
        self, var: SizingVariable, lower: int, upper: int, label: str = "",
    ) -> None:
        self.var = var
        self.lower = lower
        self.upper = upper
        self.label = label

    def description(self) -> str:
        label = self.label or self.var.name
        return f"{self.lower} <= {label} <= {self.upper}"

    def post(self, solver: object) -> None:
        _solver_call(solver, "add_var_bounds", self.var, self.lower, self.upper)


class RatioConstraint(Constraint):
    """``a_num * b_den == b_num * a_den`` (cross-multiplication for a/b == c/d)."""

    def __init__(
        self,
        a_num: SizingVariable,
        a_den: SizingVariable,
        b_num: SizingVariable,
        b_den: SizingVariable,
    ) -> None:
        self.a_num = a_num
        self.a_den = a_den
        self.b_num = b_num
        self.b_den = b_den

    def description(self) -> str:
        return (
            f"{self.a_num.name}/{self.a_den.name} == "
            f"{self.b_num.name}/{self.b_den.name}"
        )

    def post(self, solver: object) -> None:
        # a_num/a_den == b_num/b_den  ->  a_num*b_den == b_num*a_den
        lhs = _solver_call(
            solver,
            "tmp_var",
            self.a_num.lower * self.b_den.lower,
            self.a_num.upper * self.b_den.upper,
            "ratio_lhs",
        )
        rhs = _solver_call(
            solver,
            "tmp_var",
            self.b_num.lower * self.a_den.lower,
            self.b_num.upper * self.a_den.upper,
            "ratio_rhs",
        )
        model_var = getattr(solver, "var", None)
        if model_var is None:
            raise TypeError("Solver adapter must implement `var()`")
        # `lhs == model_var(a_num) * model_var(b_den)` — variable × variable
        # cannot go through `add_raw_constraint`; CP-SAT requires the
        # dedicated `AddMultiplicationEquality` API exposed via
        # `add_multiplication` on the adapter (Phase 5 bug-fix).
        _solver_call(solver, "add_multiplication", lhs, model_var(self.a_num), model_var(self.b_den))
        _solver_call(solver, "add_multiplication", rhs, model_var(self.b_num), model_var(self.a_den))
        _solver_call(solver, "add_raw_constraint", lhs == rhs)


# ═══════════════════════════════════════════════════════════════════════════
#  Transistor model constraints (SHM — Simple Handcalculation Model)
# ═══════════════════════════════════════════════════════════════════════════


class TransistorConstraints:
    """MOSFET SHM constraints for **one** transistor.

    Generates 6 constraints encoding the first-order equations:

    1. **Current equation** (strong-inversion saturation):
       $I_D = \\frac{\\mu C_{ox}}{2} \\cdot \\frac{W}{L} \\cdot V_{ov}^2$

    2. **Overdrive equation**: $V_{ov} = V_{GS} - |V_{th}|$

    3. **Transconductance**: $g_m = \\frac{2 I_D}{V_{ov}}$

    4. **Output conductance**: $g_{ds} = I_D \\cdot \\lambda$

    5. **Area**: $\\text{area} = W \\cdot L$

    6. **Saturation condition**: $V_{DS} \\ge V_{ov}$

    All quantities are in integer-scaled units (nA, mV, μm).

    C++ ref: ``TransistorConstraintsSHM``
    """

    def __init__(self, tv: TransistorVariables) -> None:
        self.tv = tv

    def as_constraints(self) -> list[Constraint]:
        """Return the 6 SHM constraints for this transistor."""
        tv = self.tv
        tp = tv.tech
        constraints: list[Constraint] = []

        # 1. Current equation
        constraints.append(CurrentEquation(tv, tp))

        # 2. Overdrive: Vov = Vgs - |Vth|
        vth_mv = int(abs(tp.threshold_voltage) * 1000)
        constraints.append(OverdriveEquation(tv, vth_mv))

        # 3. gm = 2·Id / Vov
        constraints.append(TransconductanceEquation(tv))

        # 4. gds = Id · λ
        constraints.append(OutputConductanceEquation(tv, tp))

        # 5. area = W · L
        constraints.append(AreaEquation(tv))

        # 6. Vds >= Vov (saturation)
        constraints.append(SaturationCondition(tv))

        return constraints


# ── Individual SHM equation constraints ──────────────────────────────────


class CurrentEquation(Constraint):
    r"""$I_D \cdot L = \frac{\mu C_{ox}}{2} \cdot W \cdot V_{ov}^2$ (scaled to integers).

    In nA/μm/mV units:
    ``Id_nA * L_um = (mu_cox / 2) * W_um * Vov_mV^2 * scale``

    The scale factor converts V² → mV² and A → nA consistently.
    """

    def __init__(self, tv: TransistorVariables, tp: TransistorTechParams) -> None:
        self.tv = tv
        self.tp = tp
        # μCox in A/V² → convert to nA/mV²/μm:
        # nA = A * 1e9, mV² = V² * 1e6, μm = m * 1e6
        # Id_nA * L_um = (muCox * 1e9 / 2) * W_um * Vov_mV² / 1e6
        # Simplifies to: Id_nA * L_um = (muCox * 1e3 / 2) * W_um * Vov_mV²
        self.mu_cox_scaled = tp.mu_cox * 1e3 / 2.0

    def description(self) -> str:
        return f"{self.tv.device_name}: Id·L = μCox/2 · W · Vov²"

    def post(self, solver: object) -> None:
        # Id*L = muCoxScaled * W * Vov^2
        # Use integer scaling to avoid float coefficients:
        # IdL * K_DEN ≈ WVov2 * K_NUM (within a ±TOL_PCT% band — see below)
        k_den = 1_000_000
        k_num = max(1, int(round(self.mu_cox_scaled * k_den)))

        # Strict integer equality `id_l*k_den == w_vov2*k_num` would force
        # id_l to be a multiple of `k_num // gcd(k_den, k_num)` (1693 for
        # NMOS, 1787 for PMOS in the typical 0.35 μm tech).  When KCL ties
        # NMOS and PMOS currents at a shared node, both must agree on a
        # common multiple — LCM ≈ 3 mA — which is physically unrealistic
        # for an OTA running at tens of μA.  The result is a *spurious*
        # CP-SAT infeasibility verdict on perfectly-realisable circuits.
        #
        # SHM is itself a ±10% approximation of MOSFET behaviour, so a
        # ±1% slack at the constraint level is well below the model
        # accuracy and restores the continuous nature of the equation
        # without sacrificing meaningful precision.
        tol_pct = 1
        scale = 100  # multiply both sides so the band is integer-clean
        lo_coeff = scale - tol_pct  # 99
        hi_coeff = scale + tol_pct  # 101

        tv = self.tv
        var = getattr(solver, "var", None)
        if var is None:
            raise TypeError("Solver adapter must implement `var()`")

        id_l = _solver_call(
            solver,
            "tmp_var",
            tv.current.lower * tv.length.lower,
            tv.current.upper * tv.length.upper,
            "id_l",
        )
        vov2 = _solver_call(
            solver,
            "tmp_var",
            tv.vov.lower * tv.vov.lower,
            tv.vov.upper * tv.vov.upper,
            "vov2",
        )
        w_vov2 = _solver_call(
            solver,
            "tmp_var",
            tv.width.lower * (tv.vov.lower * tv.vov.lower),
            tv.width.upper * (tv.vov.upper * tv.vov.upper),
            "w_vov2",
        )

        # Variable-times-variable products go via `add_multiplication`
        # (Week 9 Phase 5 bug-fix #1); `add_raw_constraint` only accepts
        # linear expressions (LinearExpr * scalar), so the tolerance-band
        # encoding below is fine — both sides of the inequalities are
        # `LinearExpr * int_constant`.
        _solver_call(solver, "add_multiplication", id_l, var(tv.current), var(tv.length))
        _solver_call(solver, "add_multiplication", vov2, var(tv.vov), var(tv.vov))
        _solver_call(solver, "add_multiplication", w_vov2, var(tv.width), vov2)
        # ±tol_pct% band:  lo_coeff*RHS  ≤  scale*LHS  ≤  hi_coeff*RHS
        _solver_call(
            solver, "add_raw_constraint",
            id_l * k_den * scale <= w_vov2 * k_num * hi_coeff,
        )
        _solver_call(
            solver, "add_raw_constraint",
            id_l * k_den * scale >= w_vov2 * k_num * lo_coeff,
        )


class OverdriveEquation(Constraint):
    """$V_{ov} = V_{GS} - |V_{th}|$ (all in mV)."""

    def __init__(self, tv: TransistorVariables, vth_mv: int) -> None:
        self.tv = tv
        self.vth_mv = vth_mv

    def description(self) -> str:
        return f"{self.tv.device_name}: Vov = Vgs - {self.vth_mv} mV"

    def post(self, solver: object) -> None:
        _solver_call(
            solver,
            "add_linear",
            [(1, self.tv.vov), (-1, self.tv.vgs)],
            "==",
            -self.vth_mv,
        )


class TransconductanceEquation(Constraint):
    r"""$g_m \cdot V_{ov} = 2 \cdot I_D$ (all in nA, mV, nA/V).

    Cross-multiplied to avoid division:
    ``gm_nAV * Vov_mV = 2 * Id_nA * 1000`` (×1000 converts mV → V).
    """

    def __init__(self, tv: TransistorVariables) -> None:
        self.tv = tv

    def description(self) -> str:
        return f"{self.tv.device_name}: gm·Vov = 2·Id·1000"

    def post(self, solver: object) -> None:
        tv = self.tv
        var = getattr(solver, "var", None)
        if var is None:
            raise TypeError("Solver adapter must implement `var()`")
        gm_vov = _solver_call(
            solver,
            "tmp_var",
            tv.gm.lower * tv.vov.lower,
            tv.gm.upper * tv.vov.upper,
            "gm_vov",
        )
        # `gm * vov` is variable × variable → `add_multiplication` (Phase 5
        # bug-fix); `2000 * var(tv.current)` is scalar × variable → ok.
        _solver_call(solver, "add_multiplication", gm_vov, var(tv.gm), var(tv.vov))
        # ±1% tolerance band — strict equality `gm_vov == 2000 * Id` would
        # force gm_vov to be a multiple of 2000, which combined with KCL
        # produces spurious infeasibility on realistic specs.  See the
        # long comment on `CurrentEquation.post()` for the full rationale.
        scale, tol_pct = 100, 1
        _solver_call(
            solver, "add_raw_constraint",
            gm_vov * scale <= 2000 * var(tv.current) * (scale + tol_pct),
        )
        _solver_call(
            solver, "add_raw_constraint",
            gm_vov * scale >= 2000 * var(tv.current) * (scale - tol_pct),
        )


class OutputConductanceEquation(Constraint):
    r"""$g_{ds} = I_D \cdot \lambda$.

    ``gds_nAV = Id_nA * lambda`` (λ has units 1/V, so gds is in nA/V).
    """

    def __init__(self, tv: TransistorVariables, tp: TransistorTechParams) -> None:
        self.tv = tv
        # Use strong-inversion lambda for saturation region
        self.lambda_val = tp.lambda_strong

    def description(self) -> str:
        return f"{self.tv.device_name}: gds = Id · λ ({self.lambda_val:.4f})"

    def post(self, solver: object) -> None:
        lam_scale = 1_000_000
        lam_int = int(round(self.lambda_val * lam_scale))
        # ±1% tolerance band — see the long comment on
        # `CurrentEquation.post()` for the divisibility-rationale.  Strict
        # equality `gds * lam_scale == lam_int * Id` would force gds to
        # be a multiple of `lam_int // gcd(lam_scale, lam_int)` (3 for
        # NMOS λ=0.024, 1000 for PMOS λ=0.029) and combined with KCL the
        # joint feasible set becomes empty for realistic OTA specs.
        scale, tol_pct = 100, 1
        _solver_call(
            solver, "add_linear",
            [(lam_scale * scale, self.tv.gds),
             (-lam_int * (scale + tol_pct), self.tv.current)],
            "<=", 0,
        )
        _solver_call(
            solver, "add_linear",
            [(lam_scale * scale, self.tv.gds),
             (-lam_int * (scale - tol_pct), self.tv.current)],
            ">=", 0,
        )


class AreaEquation(Constraint):
    """$\\text{area} = W \\cdot L$."""

    def __init__(self, tv: TransistorVariables) -> None:
        self.tv = tv

    def description(self) -> str:
        return f"{self.tv.device_name}: area = W · L"

    def post(self, solver: object) -> None:
        _solver_call(solver, "add_product", self.tv.area, self.tv.width, self.tv.length)


class SaturationCondition(Constraint):
    """$V_{DS} \\ge V_{ov}$ (ensures strong-inversion saturation)."""

    def __init__(self, tv: TransistorVariables) -> None:
        self.tv = tv

    def description(self) -> str:
        return f"{self.tv.device_name}: Vds >= Vov"

    def post(self, solver: object) -> None:
        _solver_call(
            solver,
            "add_linear",
            [(1, self.tv.vds), (-1, self.tv.vov)],
            ">=",
            0,
        )


# ═══════════════════════════════════════════════════════════════════════════
#  KCL constraints
# ═══════════════════════════════════════════════════════════════════════════


class KCLEquation(Constraint):
    """KCL at one internal net: ``Σ incoming_Id = Σ outgoing_Id``.

    C++ ref: ``KCLConstraints``
    """

    def __init__(
        self,
        net_name: str,
        incoming: list[TransistorVariables],
        outgoing: list[TransistorVariables],
    ) -> None:
        self.net_name = net_name
        self.incoming = incoming
        self.outgoing = outgoing

    def description(self) -> str:
        inc = " + ".join(tv.device_name for tv in self.incoming) or "0"
        out = " + ".join(tv.device_name for tv in self.outgoing) or "0"
        return f"KCL@{self.net_name}: {inc} = {out}"

    def post(self, solver: object) -> None:
        terms: list[tuple[int, SizingVariable]] = []
        for tv in self.incoming:
            terms.append((1, tv.current))
        for tv in self.outgoing:
            terms.append((-1, tv.current))
        _solver_call(solver, "add_linear", terms, "==", 0)


class KCLConstraints:
    """Generate KCL equations for every internal net.

    Current direction convention (SHM mode):
    - **NMOS**: current flows Drain → Source (conventional)
    - **PMOS**: current flows Source → Drain

    At each non-supply net, sum of currents in = sum of currents out.

    C++ ref: ``AutomaticSizing::KCLConstraints``
    """

    def __init__(
        self,
        circuit: Circuit,
        variables: SizingVariableRegistry,
    ) -> None:
        self.circuit = circuit
        self.variables = variables

    def as_constraints(self) -> list[Constraint]:
        from pyckt.core.device import DeviceType, PinType

        constraints: list[Constraint] = []
        for net in self.circuit.nets:
            if net.is_power():
                continue
            incoming: list[TransistorVariables] = []
            outgoing: list[TransistorVariables] = []
            for terminal in net.terminals:
                dev = terminal.device
                if dev.device_type != DeviceType.MOSFET:
                    continue
                if dev.name not in self.variables.transistors:
                    continue
                tv = self.variables.get_transistor(dev.name)
                pin = terminal.pin_type
                # Only drain and source pins carry current
                if pin not in (PinType.DRAIN, PinType.SOURCE):
                    continue
                if self._is_incoming(dev, pin):
                    incoming.append(tv)
                else:
                    outgoing.append(tv)
            if incoming and outgoing:
                constraints.append(KCLEquation(net.name, incoming, outgoing))
        return constraints

    @staticmethod
    def _is_incoming(device: Device, pin: PinType) -> bool:
        """True if current flows *into* the net through this pin.

        NMOS: current enters at Drain, leaves at Source.
        PMOS: current enters at Source, leaves at Drain.
        """
        from pyckt.core.device import PinType, TechType

        if device.tech_type == TechType.N:
            return pin == PinType.DRAIN
        else:  # PMOS
            return pin == PinType.SOURCE


# ═══════════════════════════════════════════════════════════════════════════
#  Sizing rule constraints (from structure recognition)
# ═══════════════════════════════════════════════════════════════════════════


class SizingRuleConstraints:
    """Translate structural sizing rules into equality constraints.

    Rule types (from ``recognition.rulegen``):

    - ``EqualLengthRule``: $L_a = L_b$
    - ``EqualWLRule``:     $W_a / L_a = W_b / L_b$ (via cross-multiply)
    - ``MatchedPairRule``: $W_a = W_b \\wedge L_a = L_b$

    C++ ref: ``SizingRulesConstraints``
    """

    def __init__(
        self,
        rules: list[SizingRule],
        variables: SizingVariableRegistry,
    ) -> None:
        self.rules = rules
        self.variables = variables

    def as_constraints(self) -> list[Constraint]:
        from recognition.rulegen import EqualLengthRule, EqualWLRule, MatchedPairRule

        constraints: list[Constraint] = []
        for rule in self.rules:
            # Collect only devices that exist in the variable registry
            tvs = []
            for d in rule.devices:
                if d in self.variables.transistors:
                    tvs.append(self.variables.get_transistor(d))
            if len(tvs) < 2:
                continue

            if isinstance(rule, MatchedPairRule):
                for i in range(1, len(tvs)):
                    constraints.append(
                        EqualityConstraint(tvs[0].width, tvs[i].width)
                    )
                    constraints.append(
                        EqualityConstraint(tvs[0].length, tvs[i].length)
                    )
            elif isinstance(rule, EqualWLRule):
                for i in range(1, len(tvs)):
                    constraints.append(
                        RatioConstraint(
                            tvs[0].width, tvs[0].length,
                            tvs[i].width, tvs[i].length,
                        )
                    )
            elif isinstance(rule, EqualLengthRule):
                for i in range(1, len(tvs)):
                    constraints.append(
                        EqualityConstraint(tvs[0].length, tvs[i].length)
                    )
        return constraints


# ═══════════════════════════════════════════════════════════════════════════
#  Performance specification constraints
# ═══════════════════════════════════════════════════════════════════════════


class SpecConstraints:
    """High-level performance specs → solver constraints.

    Translates specifications (gain, BW, SR, power, area, swing, CMRR, PSRR)
    into constraints on transistor-level variables using the partition result
    to identify which devices play which roles.

    C++ ref: ``CircuitSpecificationConstraints``
    """

    def __init__(
        self,
        specs: Specifications,
        partition: PartitionResult,
        variables: SizingVariableRegistry,
        circuit_params: CircuitParameter,
        tech: TechnologyParams,
        circuit: object | None = None,
    ) -> None:
        self.specs = specs
        self.partition = partition
        self.variables = variables
        self.params = circuit_params
        self.tech = tech
        self.circuit = circuit

    def as_constraints(self) -> list[Constraint]:
        constraints: list[Constraint] = []
        constraints.extend(self._gain_constraints())
        constraints.extend(self._bandwidth_constraints())
        constraints.extend(self._slew_rate_constraints())
        constraints.extend(self._power_constraints())
        constraints.extend(self._area_constraints())
        constraints.extend(self._swing_constraints())
        constraints.extend(self._overdrive_constraints())
        return constraints

    # ── Minimum gate overdrive ───────────────────────────────────────

    def _overdrive_constraints(self) -> list[Constraint]:
        r"""Every transistor must keep $V_{ov} \ge V_{over}$ (the spec's gate
        overdrive), so devices stay in strong inversion / saturation.

        Without this floor the balanced objective (which rewards $g_m$, hence
        $f_T$) drives $V_{ov}\to 0$ — physically into sub-threshold where the
        SHM model is invalid.  acst enforces the same overdrive minimum.
        """
        constraints: list[Constraint] = []
        if self.specs.gate_overdrive <= 0:
            return constraints
        vov_min_mv = int(self.specs.gate_overdrive * 1000)
        for tv in self.variables.transistors.values():
            constraints.append(BoundsConstraint(
                tv.vov, max(tv.vov.lower, vov_min_mv), tv.vov.upper,
                f"min overdrive: {tv.device_name} Vov >= {vov_min_mv} mV",
            ))
        return constraints

    # ── Gain ─────────────────────────────────────────────────────────

    def _gain_constraints(self) -> list[Constraint]:
        r"""Single-stage: $A_v = g_{m,\text{tc}} \cdot (r_{o,n} \| r_{o,p})$.

        In integer domain:  $A_v = g_m / (g_{ds,n} + g_{ds,p})$
        where all are in nA/V.

        For two-stage: $A_v = A_{v1} \cdot A_{v2}$.
        """
        from partitioning.result import StageType

        constraints: list[Constraint] = []
        if self.specs.min_gain <= 0:
            return constraints

        # Gain in linear scale from dB
        gain_int = int(10 ** (self.specs.min_gain / 20.0))

        tc_devs = self._devices_for_part("transconductance", StageType.FIRST)
        tc_devs = [d for d in tc_devs if d.name in self.variables.transistors]
        out_devs = self._output_node_devices()

        if not tc_devs:
            return constraints

        gm_in = self.variables.get_transistor(tc_devs[0].name).gm

        if out_devs:
            # A_v = gm_in / g_out, where g_out is the small-signal conductance
            # at the OUTPUT node (the cascoded output devices, with low gds) —
            # NOT the input pair's own gds.  Putting the diff-pair gds in the
            # denominator (the old formulation) forced its overdrive ~0, which
            # capped the tail current and broke the slew-rate spec.
            # Post:  gm_in - gain * Σ gds_out >= 0
            terms: list[tuple[int, SizingVariable]] = [(1, gm_in)]
            for dev in out_devs:
                terms.append((-gain_int,
                              self.variables.get_transistor(dev.name).gds))
            constraints.append(LinearConstraint(terms, ">=", 0))
        else:
            # fall back to the single-device approximation when the output node
            # cannot be resolved (no circuit context)
            load_devs = self._devices_for_part("load", StageType.FIRST)
            if load_devs:
                tc_tv = self.variables.get_transistor(tc_devs[0].name)
                load_tv = self.variables.get_transistor(load_devs[0].name)
                constraints.append(GainConstraint(
                    tc_tv.gm, tc_tv.gds, load_tv.gds, gain_int,
                    f"gain >= {self.specs.min_gain} dB",
                ))
        return constraints

    def _output_node_devices(self) -> list[Device]:
        """MOSFETs whose drain is on the output net (set the output resistance)."""
        from .topology import output_node_devices

        return output_node_devices(
            self.circuit, self.params.output_net, self.variables.transistors
        )

    # ── Bandwidth ────────────────────────────────────────────────────

    def _bandwidth_constraints(self) -> list[Constraint]:
        r"""$f_T = g_m / (2\pi \cdot C_L)$.

        Rearranged: $g_m \ge 2\pi \cdot f_T \cdot C_L$.
        """
        from partitioning.result import StageType

        constraints: list[Constraint] = []
        if self.specs.min_transit_freq <= 0:
            return constraints

        tc_devs = self._devices_for_part("transconductance", StageType.FIRST)
        if not tc_devs:
            return constraints

        # CL in pF, ft in MHz → gm in nA/V
        # gm_nAV >= 2π · ft_MHz · 1e6 · CL_pF · 1e-12 · 1e9
        # = 2π · ft · CL · 1e3
        cl_pf = self.params.load_capacities[0][1] if self.params.load_capacities else 10.0
        ft_mhz = self.specs.min_transit_freq
        # round the threshold UP so the integer floor still satisfies ft >= spec
        gm_min = math.ceil(2 * math.pi * ft_mhz * cl_pf * 1e3)

        tc_tv = self.variables.get_transistor(tc_devs[0].name)
        constraints.append(BoundsConstraint(
            tc_tv.gm, gm_min, tc_tv.gm.upper,
            f"BW: gm >= {gm_min} nA/V for ft >= {ft_mhz} MHz",
        ))
        return constraints

    # ── Slew rate ────────────────────────────────────────────────────

    def _slew_rate_constraints(self) -> list[Constraint]:
        r"""$SR = I_{\text{tail}} / C_L \;\Rightarrow\; I_{\text{tail}} \ge SR \cdot C_L$.

        The slewing current is the input pair's **tail** current — the sum of the
        first-stage transconductance device currents.  We bind those currents
        directly (each device carries its share of the tail) rather than the
        bias mirror, which is not what charges/discharges :math:`C_L`.
        """
        from partitioning.result import StageType

        constraints: list[Constraint] = []
        if self.specs.max_slew_rate <= 0:
            return constraints

        tc_devs = self._devices_for_part("transconductance", StageType.FIRST)
        tc_devs = [d for d in tc_devs if d.name in self.variables.transistors]
        if not tc_devs:
            return constraints

        # SR [V/μs] · CL [pF] = [V·pF/μs] = 1e3 nA  →  I_tail_nA = SR · CL · 1e3
        cl_pf = self.params.load_capacities[0][1] if self.params.load_capacities else 10.0
        sr = self.specs.max_slew_rate
        # round UP so the per-device integer floor still satisfies SR >= spec
        i_tail_min = math.ceil(sr * cl_pf * 1e3)
        per_dev = -(-i_tail_min // len(tc_devs))  # ceil division

        for dev in tc_devs:
            tv = self.variables.get_transistor(dev.name)
            constraints.append(BoundsConstraint(
                tv.current, max(tv.current.lower, per_dev), tv.current.upper,
                f"SR: I({dev.name}) >= {per_dev} nA for SR >= {sr} V/μs",
            ))
        return constraints

    # ── Power ────────────────────────────────────────────────────────

    def _power_constraints(self) -> list[Constraint]:
        r"""$P = V_{DD} \cdot I_{\text{total}}$.

        Rearranged: $I_{\text{total}} \le P_{\max} / V_{DD}$.
        """
        constraints: list[Constraint] = []
        if self.specs.max_power <= 0:
            return constraints

        vdd = self.params.supply_voltage[1]  # V
        if vdd <= 0:
            return constraints
        # P_max in mW, Vdd in V → I_max in mA → nA
        i_max_na = int(self.specs.max_power / vdd * 1e6)  # mW/V = mA, * 1e6 = nA

        # Apply to all bias transistors (they set supply current)
        for tv in self.variables.transistors.values():
            constraints.append(BoundsConstraint(
                tv.current, tv.current.lower, min(i_max_na, tv.current.upper),
                f"power: Id <= {i_max_na} nA",
            ))
        return constraints

    # ── Area ─────────────────────────────────────────────────────────

    def _area_constraints(self) -> list[Constraint]:
        """$\\sum W_i \\cdot L_i \\le A_{\\max}$."""
        constraints: list[Constraint] = []
        if self.specs.max_area <= 0:
            return constraints

        area_vars = [
            (1, tv.area) for tv in self.variables.transistors.values()
        ]
        constraints.append(LinearConstraint(
            area_vars, "<=", int(self.specs.max_area),
        ))
        return constraints

    # ── Output swing ─────────────────────────────────────────────────

    def _swing_constraints(self) -> list[Constraint]:
        """Constrain overdrive voltages to guarantee output swing."""
        from partitioning.result import StageType

        constraints: list[Constraint] = []
        # Vout_min requires output NMOS Vov ≤ Vout_min (in mV)
        if self.specs.vout_min > 0:
            load_devs = self._devices_for_part("load", StageType.FIRST)
            for dev in load_devs:
                if dev.name in self.variables.transistors:
                    tv = self.variables.get_transistor(dev.name)
                    vout_min_mv = int(self.specs.vout_min * 1000)
                    constraints.append(BoundsConstraint(
                        tv.vov, tv.vov.lower, vout_min_mv,
                        f"swing: {dev.name} Vov <= {vout_min_mv} mV",
                    ))
        return constraints

    # ── Helpers ──────────────────────────────────────────────────────

    def _devices_for_part(
        self, part_name: str, stage: StageType,
    ) -> list[Device]:
        """Retrieve leaf devices for a partition role.

        *part_name*: ``"transconductance"``, ``"load"``, or ``"bias"``.
        """

        if part_name == "transconductance":
            structures = self.partition.transconductance_parts(stage)
        elif part_name == "load":
            structures = self.partition.load_parts(stage)
        elif part_name == "bias":
            structures = self.partition.bias_parts(stage)
        else:
            return []
        devices: list[Device] = []
        for s in structures:
            devices.extend(s.devices)
        return devices


# ── Gain constraint (custom) ─────────────────────────────────────────────


class GainConstraint(Constraint):
    r"""$g_m \ge \text{gain} \cdot (g_{ds,1} + g_{ds,2})$."""

    def __init__(
        self,
        gm: SizingVariable,
        gds_1: SizingVariable,
        gds_2: SizingVariable,
        gain_linear: int,
        label: str = "",
    ) -> None:
        self.gm = gm
        self.gds_1 = gds_1
        self.gds_2 = gds_2
        self.gain_linear = gain_linear
        self.label = label

    def description(self) -> str:
        return self.label or f"{self.gm.name} >= {self.gain_linear} · ({self.gds_1.name} + {self.gds_2.name})"

    def post(self, solver: object) -> None:
        _solver_call(
            solver,
            "add_linear",
            [
                (1, self.gm),
                (-self.gain_linear, self.gds_1),
                (-self.gain_linear, self.gds_2),
            ],
            ">=",
            0,
        )


# ═══════════════════════════════════════════════════════════════════════════
#  Poles and zeros constraints
# ═══════════════════════════════════════════════════════════════════════════


class PolesAndZerosConstraints:
    """Frequency-domain stability constraints.

    **Single-stage**: inherently stable (~90° PM from single dominant pole).
    Only constrains GBW.

    **Two-stage** (with Miller compensation):
    - Dominant pole: $p_1 = 1 / (R_{out1} \\cdot C_c \\cdot A_2)$
    - Second pole:   $p_2 = g_{m2} / C_L$
    - GBW:           $\\text{GBW} = g_{m1} / C_c$
    - Phase margin:  $p_2 > 2.2 \\cdot \\text{GBW}$ (for PM ≈ 60°)

    C++ ref: ``PolesAndZeros``
    """

    def __init__(
        self,
        partition: PartitionResult,
        variables: SizingVariableRegistry,
        specs: Specifications,
        circuit_params: CircuitParameter,
    ) -> None:
        self.partition = partition
        self.variables = variables
        self.specs = specs
        self.params = circuit_params

    def as_constraints(self) -> list[Constraint]:
        if self.partition.is_two_stage():
            return self._two_stage_constraints()
        return self._single_stage_constraints()

    def _single_stage_constraints(self) -> list[Constraint]:
        """Single-stage: GBW = gm / (2π·CL).

        Single dominant pole → PM is inherently ~90°, no extra constraint.
        """
        # GBW constraint is already handled by SpecConstraints._bandwidth_constraints
        return []

    def _two_stage_constraints(self) -> list[Constraint]:
        """Two-stage: ensure non-dominant pole is far enough from GBW.

        $p_2 > k \\cdot \\text{GBW}$ where k ≈ 2.2 for 60° PM.
        Translates to: $g_{m2} / C_L > 2.2 \\cdot g_{m1} / C_c$.
        Rearranged:    $g_{m2} \\cdot C_c > 2.2 \\cdot g_{m1} \\cdot C_L$.
        """
        from partitioning.result import StageType

        constraints: list[Constraint] = []

        tc1_structs = self.partition.transconductance_parts(StageType.FIRST)
        tc2_structs = self.partition.transconductance_parts(StageType.SECOND)
        if not tc1_structs or not tc2_structs:
            return constraints

        tc1_devs = []
        for s in tc1_structs:
            tc1_devs.extend(s.devices)
        tc2_devs = []
        for s in tc2_structs:
            tc2_devs.extend(s.devices)

        if not tc1_devs or not tc2_devs:
            return constraints

        tc1_tv = self.variables.get_transistor(tc1_devs[0].name)
        tc2_tv = self.variables.get_transistor(tc2_devs[0].name)

        # Phase margin constraint: gm2 >= 2.2 * gm1 * CL / Cc
        # Since Cc and CL are external values (not solver variables for now),
        # we approximate: gm2 >= 2.2 * gm1 (assuming Cc ≈ CL)
        # A more precise formulation would include Cc as a variable
        pm_factor = int(2.2 * 10)  # scaled by 10 for integer math
        constraints.append(PhaseMarginConstraint(
            tc1_tv.gm, tc2_tv.gm, pm_factor,
            "PM: gm2 >= 2.2·gm1 (60° target)",
        ))
        return constraints


class PhaseMarginConstraint(Constraint):
    """$g_{m2} \\cdot 10 \\ge \\text{factor} \\cdot g_{m1}$ (factor = 22 for PM ≈ 60°)."""

    def __init__(
        self,
        gm1: SizingVariable,
        gm2: SizingVariable,
        factor_x10: int,
        label: str = "",
    ) -> None:
        self.gm1 = gm1
        self.gm2 = gm2
        self.factor_x10 = factor_x10
        self.label = label

    def description(self) -> str:
        return self.label or f"{self.gm2.name}·10 >= {self.factor_x10}·{self.gm1.name}"

    def post(self, solver: object) -> None:
        _solver_call(
            solver,
            "add_linear",
            [(10, self.gm2), (-self.factor_x10, self.gm1)],
            ">=",
            0,
        )
