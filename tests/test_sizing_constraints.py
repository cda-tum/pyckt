"""Tests for the sizing constraint formulation layer (Week 6).

Covers files 1–4 of the sizing module:
  - variables.py   — SizingVariable, TransistorVariables, VoltageVariable,
                     SizingVariableRegistry
  - constraints.py — base constraint types, SHM equations, KCL, sizing rules,
                     spec constraints, poles-and-zeros constraints
  - result.py      — DeviceSizing, ExpectedPerformance, SizingResult
  - problem.py     — SizingProblem.build() assembly

Week 7 Phase 1 implements constraint posting through a solver-adapter API.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pyckt.core import (
    Circuit,
    Device,
    DeviceType,
    Net,
    NetId,
    PinType,
    Supply,
    SupplyType,
    TechType,
    Terminal,
)

from pyckt.sizing.variables import (
    SizingVariable,
    SizingVariableRegistry,
    TransistorVariables,
    VoltageVariable,
)
from pyckt.sizing.constraints import (
    AreaEquation,
    BoundsConstraint,
    Constraint,
    CurrentEquation,
    EqualityConstraint,
    GainConstraint,
    KCLConstraints,
    KCLEquation,
    LinearConstraint,
    OverdriveEquation,
    OutputConductanceEquation,
    PhaseMarginConstraint,
    PolesAndZerosConstraints,
    ProductConstraint,
    RatioConstraint,
    SaturationCondition,
    SizingRuleConstraints,
    SpecConstraints,
    TransconductanceEquation,
    TransistorConstraints,
)
from pyckt.sizing.result import (
    DeviceSizing,
    ExpectedPerformance,
    SizingResult,
)
from pyckt.sizing.problem import SizingProblem

from pyckt.io.technology_parser import TransistorTechParams, TechnologyParams

from recognition.model import (
    ArrayStructure,
    StructureId,
)
from recognition.rulegen import (
    EqualLengthRule,
    EqualWLRule,
    MatchedPairRule,
)
from partitioning.result import PartitionResult, PartType, StageType
from pyckt.io.circuit_info_parser import (
    CircuitParameter,
    CircuitInformation,
    Specifications,
)


class _MockAdapter:
    """Minimal solver-adapter double for exercising `Constraint.post()` paths."""

    def __init__(self):
        self.calls: list[tuple] = []
        self._tmp_counter = 0

    def var(self, sv):
        return 1

    def tmp_var(self, lower, upper, label="tmp"):
        self._tmp_counter += 1
        return self._tmp_counter

    def add_equality(self, a, b):
        self.calls.append(("add_equality", a.name, b.name))

    def add_product(self, result, a, b):
        self.calls.append(("add_product", result.name, a.name, b.name))

    def add_multiplication(self, target, a, b):
        # The real adapter takes raw IntVars (not SizingVariable wrappers);
        # the mock receives whatever `tmp_var()` / `var()` returned (ints
        # here), so just record stringified positional arguments.
        self.calls.append(("add_multiplication", target, a, b))

    def add_linear(self, terms, relation, bound):
        self.calls.append(("add_linear", [(c, v.name) for c, v in terms], relation, bound))

    def add_var_bounds(self, var, lower, upper):
        self.calls.append(("add_var_bounds", var.name, lower, upper))

    def add_raw_constraint(self, expr):
        self.calls.append(("add_raw_constraint", str(expr)))


# ── _solver_call / var() guard coverage ─────────────────────────────

class _NoVarAdapter(_MockAdapter):
    """Adapter that deliberately omits `var()` to trigger TypeError guards."""
    var = None  # type: ignore[assignment]


def test_solver_call_missing_method_raises_type_error():
    """_solver_call raises TypeError when the adapter lacks the requested method."""
    from pyckt.sizing.constraints import _solver_call
    adapter = object()  # has no add_equality
    with pytest.raises(TypeError, match="add_equality"):
        _solver_call(adapter, "add_equality", 1, 2)


def test_ratio_constraint_post_no_var_raises():
    """RatioConstraint.post raises TypeError when adapter has no `var()`."""
    from pyckt.sizing.constraints import RatioConstraint
    from pyckt.sizing.variables import SizingVariable
    a = SizingVariable("a", 1, 100)
    b = SizingVariable("b", 1, 100)
    c = SizingVariable("c", 1, 100)
    d = SizingVariable("d", 1, 100)
    constraint = RatioConstraint(a, b, c, d)
    with pytest.raises(TypeError, match="var"):
        constraint.post(_NoVarAdapter())


def test_current_equation_post_no_var_raises():
    """CurrentEquation.post raises TypeError when adapter has no `var()`."""
    from pyckt.sizing.constraints import CurrentEquation
    from pyckt.sizing.variables import TransistorVariables
    from pyckt.core.device import TechType
    tv = TransistorVariables("mx", TechType.N, _nmos_tech())
    constraint = CurrentEquation(tv, _nmos_tech())
    with pytest.raises(TypeError, match="var"):
        constraint.post(_NoVarAdapter())


def test_transconductance_equation_post_no_var_raises():
    """TransconductanceEquation.post raises TypeError when adapter has no `var()`."""
    from pyckt.sizing.constraints import TransconductanceEquation
    from pyckt.sizing.variables import TransistorVariables
    from pyckt.core.device import TechType
    tv = TransistorVariables("mx", TechType.N, _nmos_tech())
    constraint = TransconductanceEquation(tv)
    with pytest.raises(TypeError, match="var"):
        constraint.post(_NoVarAdapter())


# ── Test data path ────────────────────────────────────────────────────

DATA = Path(__file__).resolve().parent / "data"


def _have_test_data() -> bool:
    return (DATA / "TechnologyFile.xml").exists() and (
        DATA / "CircuitParameterAndSpecifications.xml"
    ).exists()


# ── Tech param helpers ────────────────────────────────────────────────

def _nmos_tech() -> TransistorTechParams:
    return TransistorTechParams(
        threshold_voltage=0.405,
        mu_cox=0.0001693,
        early_voltage=4.4,
        overlap_capacitance=6.20e-10,
        gate_oxide_capacitance=0.006058,
        cj=0.001812,
        cjsw=5.341e-10,
        pb=0.5,
        lateral_diffusion=3.162e-5,
        slope_factor=1.75,
        lambda_strong=0.024,
        lambda_weak=0.07,
        min_area=10.0,
        min_length=1.0,
        min_width=1.0,
    )


def _pmos_tech() -> TransistorTechParams:
    return TransistorTechParams(
        threshold_voltage=-0.564,
        mu_cox=0.00003574,
        early_voltage=2.86,
        overlap_capacitance=6.66e-10,
        gate_oxide_capacitance=0.006058,
        cj=0.001894,
        cjsw=3.626e-10,
        pb=0.99,
        lateral_diffusion=9.968e-4,
        slope_factor=1.31,
        lambda_strong=0.029,
        lambda_weak=0.074,
        min_area=10.0,
        min_length=1.0,
        min_width=1.0,
    )


def _nmos_device(name: str) -> Device:
    return Device(name, DeviceType.MOSFET, TechType.N)


def _pmos_device(name: str) -> Device:
    return Device(name, DeviceType.MOSFET, TechType.P)


# ── Minimal circuit builder ───────────────────────────────────────────

def _make_net(name: str, supply_type: SupplyType = SupplyType.NO_SUPPLY) -> Net:
    net = Net(NetId(name))
    net.supply = Supply(supply_type)
    return net


def _wire(circuit: Circuit, dev: Device, net: Net, pin_type: PinType) -> None:
    t = Terminal(dev, pin_type, net)
    dev.add_terminal(t)
    net.add_terminal(t)
    circuit.add_terminal(t)


def _build_simple_circuit() -> Circuit:
    """Two-transistor half-circuit: NMOS + PMOS sharing one internal net."""
    circuit = Circuit(name="simple")

    vdd = _make_net("vdd!", SupplyType.VDD)
    gnd = _make_net("gnd!", SupplyType.GND)
    mid = _make_net("mid")

    mn = _nmos_device("mn")
    mp = _pmos_device("mp")

    circuit.add_device(mn)
    circuit.add_device(mp)
    circuit.add_net(vdd)
    circuit.add_net(gnd)
    circuit.add_net(mid)

    # mn: drain=mid, gate=mid, source=gnd, bulk=gnd
    _wire(circuit, mn, mid, PinType.DRAIN)
    _wire(circuit, mn, mid, PinType.GATE)
    _wire(circuit, mn, gnd, PinType.SOURCE)
    _wire(circuit, mn, gnd, PinType.BULK)

    # mp: drain=mid, gate=mid, source=vdd, bulk=vdd
    _wire(circuit, mp, mid, PinType.DRAIN)
    _wire(circuit, mp, mid, PinType.GATE)
    _wire(circuit, mp, vdd, PinType.SOURCE)
    _wire(circuit, mp, vdd, PinType.BULK)

    return circuit


def _simple_specs() -> Specifications:
    return Specifications(
        min_gain=80.0,
        min_transit_freq=2.75,
        max_slew_rate=3.5,
        max_power=10.0,
        max_area=15000.0,
        vout_min=1.0,
        vout_max=3.0,
        phase_margin=60.0,
    )


def _simple_params() -> CircuitParameter:
    return CircuitParameter(
        supply_voltage=("vdd!", 5.0),
        ground=("gnd!", 0.0),
        input_plus=("inp", 2.5),
        input_minus=("inn", 2.5),
        output_net="out",
        bias_current=("ibias", 10.0),
        load_capacities=[("cl", 20.0)],
    )


def _make_array_structure(name: str, tech: TechType, devices: list[Device]) -> ArrayStructure:
    sid = StructureId(name, 0)
    arr = ArrayStructure(sid, tech_type=tech)
    for d in devices:
        arr.add_device(d)
    return arr


def _build_single_stage_partition(
    tc_devs: list[Device],
    load_devs: list[Device],
    bias_devs: list[Device],
) -> PartitionResult:
    result = PartitionResult()
    tc_struct = _make_array_structure("DifferentialPair", TechType.N, tc_devs)
    load_struct = _make_array_structure("CurrentMirror", TechType.P, load_devs)
    result.assign(tc_struct, PartType.TRANSCONDUCTANCE, StageType.FIRST, "tc")
    result.assign(load_struct, PartType.LOAD, StageType.FIRST, "load")
    if bias_devs:
        bias_struct = _make_array_structure("CurrentMirror", TechType.N, bias_devs)
        result.assign(bias_struct, PartType.BIAS, StageType.FIRST, "bias")
    return result


def _kcl_constraints_for_simple_circuit(
    registered_devices: tuple[str, ...] = ("mn", "mp"),
) -> list[KCLEquation]:
    circuit = _build_simple_circuit()
    reg = SizingVariableRegistry()
    for name in registered_devices:
        dev = circuit.find_device(name)
        if dev is not None:
            reg.add_transistor(dev, _nmos_tech(), _pmos_tech())
    return KCLConstraints(circuit, reg).as_constraints()


# ═══════════════════════════════════════════════════════════════════════
#  TestSizingVariables
# ═══════════════════════════════════════════════════════════════════════

class TestSizingVariable:
    def test_repr(self):
        v = SizingVariable("x", 0, 100, "test")
        assert "x" in repr(v)
        assert "0..100" in repr(v)

    def test_lower_upper(self):
        v = SizingVariable("y", 5, 50)
        assert v.lower == 5
        assert v.upper == 50

    def test_description_default_empty(self):
        v = SizingVariable("z", 0, 1)
        assert v.description == ""


class TestTransistorVariables:
    def test_creates_nine_variables(self):
        tv = TransistorVariables("m0", TechType.N, _nmos_tech())
        assert len(tv.all_variables) == 9

    def test_variable_names_include_device(self):
        tv = TransistorVariables("mx", TechType.N, _nmos_tech())
        names = [v.name for v in tv.all_variables]
        assert all("mx" in n for n in names)

    def test_width_lower_bound_from_tech(self):
        tv = TransistorVariables("m0", TechType.N, _nmos_tech())
        assert tv.width.lower >= 1

    def test_length_lower_bound_from_tech(self):
        tv = TransistorVariables("m0", TechType.N, _nmos_tech())
        assert tv.length.lower >= 1

    def test_pmos_tech_type_stored(self):
        tv = TransistorVariables("mp", TechType.P, _pmos_tech())
        assert tv.tech_type == TechType.P

    def test_repr_contains_name(self):
        tv = TransistorVariables("mq", TechType.N, _nmos_tech())
        assert "mq" in repr(tv)

    def test_all_variables_are_sizing_variables(self):
        tv = TransistorVariables("m0", TechType.N, _nmos_tech())
        assert all(isinstance(v, SizingVariable) for v in tv.all_variables)


class TestVoltageVariable:
    def test_var_name_prefixed(self):
        vv = VoltageVariable("tail")
        assert vv.var.name.startswith("V_")
        assert "tail" in vv.var.name

    def test_upper_equals_supply(self):
        vv = VoltageVariable("net", supply_voltage_mv=3300)
        assert vv.var.upper == 3300

    def test_lower_is_zero(self):
        vv = VoltageVariable("net")
        assert vv.var.lower == 0

    def test_repr(self):
        vv = VoltageVariable("out")
        assert "out" in repr(vv)


class TestSizingVariableRegistry:
    def test_add_transistor_nmos(self):
        reg = SizingVariableRegistry()
        dev = _nmos_device("mn")
        tv = reg.add_transistor(dev, _nmos_tech(), _pmos_tech())
        assert tv.tech_type == TechType.N
        assert "mn" in reg.transistors

    def test_add_transistor_pmos(self):
        reg = SizingVariableRegistry()
        dev = _pmos_device("mp")
        tv = reg.add_transistor(dev, _nmos_tech(), _pmos_tech())
        assert tv.tech_type == TechType.P

    def test_get_transistor(self):
        reg = SizingVariableRegistry()
        dev = _nmos_device("m0")
        tv = reg.add_transistor(dev, _nmos_tech(), _pmos_tech())
        assert reg.get_transistor("m0") is tv

    def test_get_transistor_missing_raises(self):
        reg = SizingVariableRegistry()
        with pytest.raises(KeyError):
            reg.get_transistor("nonexistent")

    def test_add_voltage(self):
        reg = SizingVariableRegistry()
        vv = reg.add_voltage("tail")
        assert "tail" in reg.voltages
        assert vv.var.name.startswith("V_")

    def test_add_voltage_idempotent(self):
        reg = SizingVariableRegistry()
        vv1 = reg.add_voltage("x")
        vv2 = reg.add_voltage("x")
        assert vv1 is vv2

    def test_total_variables_count(self):
        reg = SizingVariableRegistry()
        reg.add_transistor(_nmos_device("m0"), _nmos_tech(), _pmos_tech())
        reg.add_transistor(_pmos_device("m1"), _nmos_tech(), _pmos_tech())
        reg.add_voltage("net1")
        # 2 transistors × 9 vars + 1 voltage
        assert reg.total_variables == 2 * 9 + 1

    def test_get_voltage_missing_raises(self):
        reg = SizingVariableRegistry()
        with pytest.raises(KeyError):
            reg.get_voltage("missing")


# ═══════════════════════════════════════════════════════════════════════
#  TestTransistorConstraints
# ═══════════════════════════════════════════════════════════════════════

class TestTransistorConstraints:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tv = TransistorVariables("m0", TechType.N, _nmos_tech())
        self.tc = TransistorConstraints(self.tv)
        self.constraints = self.tc.as_constraints()

    def test_returns_six_constraints(self):
        assert len(self.constraints) == 6

    def test_all_are_constraint_instances(self):
        assert all(isinstance(c, Constraint) for c in self.constraints)

    @pytest.mark.parametrize(
        "constraint_type",
        [
            CurrentEquation,
            OverdriveEquation,
            TransconductanceEquation,
            OutputConductanceEquation,
            AreaEquation,
            SaturationCondition,
        ],
    )
    def test_has_expected_constraint_type(self, constraint_type):
        assert any(isinstance(c, constraint_type) for c in self.constraints)

    def test_descriptions_contain_device_name(self):
        for c in self.constraints:
            assert "m0" in c.description()

    def test_post_calls_solver_adapter(self):
        adapter = _MockAdapter()
        for c in self.constraints:
            c.post(adapter)
        assert adapter.calls


# ── Primitive constraint types ─────────────────────────────────────────

class TestPrimitiveConstraints:
    @pytest.mark.parametrize(
        ("constraint", "tokens"),
        [
            (
                EqualityConstraint(SizingVariable("a", 0, 10), SizingVariable("b", 0, 10)),
                ["a", "b"],
            ),
            (
                ProductConstraint(
                    SizingVariable("r", 0, 1000),
                    SizingVariable("a", 0, 100),
                    SizingVariable("b", 0, 100),
                ),
                ["r", "a", "b"],
            ),
            (
                LinearConstraint([(2, SizingVariable("v", 0, 100))], ">=", 50),
                ["v", ">="],
            ),
            (BoundsConstraint(SizingVariable("v", 0, 1000), 10, 500, "test"), ["10", "500"]),
            (
                RatioConstraint(
                    SizingVariable("W1", 1, 100),
                    SizingVariable("L1", 1, 10),
                    SizingVariable("W2", 1, 100),
                    SizingVariable("L2", 1, 10),
                ),
                ["W1", "L1"],
            ),
        ],
    )
    def test_description_contains_expected_tokens(self, constraint, tokens):
        desc = constraint.description()
        assert all(token in desc for token in tokens)

    def test_all_post_call_adapter(self):
        v = SizingVariable("v", 0, 10)
        prims = [
            EqualityConstraint(v, v),
            ProductConstraint(v, v, v),
            LinearConstraint([(1, v)], "==", 5),
            BoundsConstraint(v, 0, 10),
            RatioConstraint(v, v, v, v),
        ]
        adapter = _MockAdapter()
        for c in prims:
            c.post(adapter)
        assert adapter.calls

    def test_constraint_repr_uses_base_repr(self):
        a = SizingVariable("a", 0, 10)
        b = SizingVariable("b", 0, 10)
        c = EqualityConstraint(a, b)
        r = repr(c)
        assert "EqualityConstraint(" in r
        assert "a == b" in r


# ═══════════════════════════════════════════════════════════════════════
#  TestKCLConstraints
# ═══════════════════════════════════════════════════════════════════════

class TestKCLConstraints:
    def test_internal_net_constraints_are_kcl_only(self):
        constraints = _kcl_constraints_for_simple_circuit()
        assert any(c.net_name == "mid" for c in constraints)
        assert all(
            isinstance(c, KCLEquation)
            and c.net_name not in ("vdd!", "gnd!")
            and "KCL" in c.description()
            for c in constraints
        )

    @pytest.mark.parametrize(
        ("device", "pin", "expected"),
        [
            (_nmos_device("x"), PinType.DRAIN, True),
            (_nmos_device("x"), PinType.SOURCE, False),
            (_pmos_device("x"), PinType.SOURCE, True),
            (_pmos_device("x"), PinType.DRAIN, False),
        ],
    )
    def test_is_incoming_direction_rules(self, device, pin, expected):
        assert KCLConstraints._is_incoming(device, pin) is expected

    def test_missing_devices_skipped(self):
        """Devices not in registry should be silently skipped."""
        constraints = _kcl_constraints_for_simple_circuit(registered_devices=("mn",))
        # With only one registered device on the internal net, KCL is incomplete.
        assert constraints == []

    def test_kcl_post_calls_adapter(self):
        constraints = _kcl_constraints_for_simple_circuit()
        assert constraints
        adapter = _MockAdapter()
        constraints[0].post(adapter)
        assert any(c[0] == "add_linear" for c in adapter.calls)


# ═══════════════════════════════════════════════════════════════════════
#  TestSizingRuleConstraints
# ═══════════════════════════════════════════════════════════════════════

class TestSizingRuleConstraints:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.reg = SizingVariableRegistry()
        self.mn = _nmos_device("m1")
        self.mp = _pmos_device("m2")
        self.reg.add_transistor(self.mn, _nmos_tech(), _pmos_tech())
        self.reg.add_transistor(self.mp, _nmos_tech(), _pmos_tech())

    def test_matched_pair_generates_w_and_l_equality(self):
        rule = MatchedPairRule("DP", "matched", ["m1", "m2"], "matched")
        src = SizingRuleConstraints([rule], self.reg)
        constraints = src.as_constraints()
        eq = [c for c in constraints if isinstance(c, EqualityConstraint)]
        assert len(eq) == 2  # W == W  and  L == L

    def test_equal_length_generates_l_equality_only(self):
        rule = EqualLengthRule("CM", "equal_length", ["m1", "m2"], "eq L")
        src = SizingRuleConstraints([rule], self.reg)
        constraints = src.as_constraints()
        assert len(constraints) == 1
        assert isinstance(constraints[0], EqualityConstraint)
        assert constraints[0].a.name.endswith("_L")
        assert constraints[0].b.name.endswith("_L")

    def test_equal_wl_generates_ratio_constraint(self):
        rule = EqualWLRule("CM", "equal_wl", ["m1", "m2"], "eq W/L")
        src = SizingRuleConstraints([rule], self.reg)
        constraints = src.as_constraints()
        assert len(constraints) == 1
        assert isinstance(constraints[0], RatioConstraint)

    def test_device_not_in_registry_skipped(self):
        rule = MatchedPairRule("X", "matched", ["m1", "unknown"], "x")
        src = SizingRuleConstraints([rule], self.reg)
        # Only 1 device in registry → len(tvs) < 2 → no constraints
        assert src.as_constraints() == []

    def test_single_device_skipped(self):
        rule = EqualLengthRule("X", "equal_length", ["m1"], "single")
        src = SizingRuleConstraints([rule], self.reg)
        assert src.as_constraints() == []

    def test_three_device_matched_pair(self):
        self.reg.add_transistor(_nmos_device("m3"), _nmos_tech(), _pmos_tech())
        rule = MatchedPairRule("DP3", "matched", ["m1", "m2", "m3"], "3way")
        src = SizingRuleConstraints([rule], self.reg)
        constraints = src.as_constraints()
        # (m1==m2, m1==m3) × 2 (W and L each)
        assert len(constraints) == 4


# ═══════════════════════════════════════════════════════════════════════
#  TestSpecConstraints
# ═══════════════════════════════════════════════════════════════════════

class TestSpecConstraints:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.mn = _nmos_device("m_tc")
        self.mp = _pmos_device("m_load")
        self.mbias = _nmos_device("m_bias")
        self.reg = SizingVariableRegistry()
        self.reg.add_transistor(self.mn, _nmos_tech(), _pmos_tech())
        self.reg.add_transistor(self.mp, _nmos_tech(), _pmos_tech())
        self.reg.add_transistor(self.mbias, _nmos_tech(), _pmos_tech())
        self.partition = _build_single_stage_partition(
            [self.mn], [self.mp], [self.mbias]
        )
        self.tech = TechnologyParams(
            thermal_voltage=0.026,
            nmos=_nmos_tech(),
            pmos=_pmos_tech(),
        )

    def _constraints(self, specs: Specifications) -> list[Constraint]:
        return SpecConstraints(
            specs,
            self.partition,
            self.reg,
            _simple_params(),
            self.tech,
        ).as_constraints()

    @pytest.mark.parametrize(
        ("specs", "expected_type"),
        [
            (Specifications(min_gain=80.0), GainConstraint),
            (Specifications(min_transit_freq=2.75), BoundsConstraint),
            (Specifications(max_slew_rate=3.5), BoundsConstraint),
            (Specifications(max_power=10.0), BoundsConstraint),
            (Specifications(max_area=15000.0), LinearConstraint),
            (Specifications(vout_min=1.0), BoundsConstraint),
        ],
    )
    def test_spec_generates_expected_constraint_type(self, specs, expected_type):
        constraints = self._constraints(specs)
        assert any(isinstance(c, expected_type) for c in constraints)

    def test_no_gain_constraint_when_zero(self):
        constraints = self._constraints(Specifications(min_gain=0.0))
        assert not any(isinstance(c, GainConstraint) for c in constraints)

    def test_empty_specs_produce_no_constraints(self):
        assert self._constraints(Specifications()) == []

    def test_all_constraints_are_constraint_instances(self):
        for c in self._constraints(_simple_specs()):
            assert isinstance(c, Constraint)

    def test_all_post_call_adapter(self):
        adapter = _MockAdapter()
        for c in self._constraints(_simple_specs()):
            c.post(adapter)
        assert adapter.calls

    def test_bandwidth_no_transconductance_devices_returns_empty(self):
        specs = Specifications(min_transit_freq=2.75)
        empty_partition = PartitionResult()
        sc = SpecConstraints(specs, empty_partition, self.reg, _simple_params(), self.tech)
        assert sc.as_constraints() == []

    def test_power_constraints_with_zero_vdd_returns_empty(self):
        specs = Specifications(max_power=10.0)
        params = _simple_params()
        params.supply_voltage = ("vdd!", 0.0)
        sc = SpecConstraints(specs, self.partition, self.reg, params, self.tech)
        assert sc.as_constraints() == []

    def test_devices_for_unknown_part_returns_empty(self):
        sc = SpecConstraints(_simple_specs(), self.partition, self.reg, _simple_params(), self.tech)
        assert sc._devices_for_part("unknown", StageType.FIRST) == []

    def test_gain_constraint_description_without_label(self):
        tv = self.reg.get_transistor("m_tc")
        c = GainConstraint(tv.gm, tv.gds, tv.gds, gain_linear=10)
        desc = c.description()
        assert tv.gm.name in desc
        assert str(c.gain_linear) in desc


# ═══════════════════════════════════════════════════════════════════════
#  TestPolesAndZerosConstraints
# ═══════════════════════════════════════════════════════════════════════

class TestPolesAndZerosConstraints:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.mn = _nmos_device("m_tc")
        self.mp = _pmos_device("m_load")
        self.reg = SizingVariableRegistry()
        self.reg.add_transistor(self.mn, _nmos_tech(), _pmos_tech())
        self.reg.add_transistor(self.mp, _nmos_tech(), _pmos_tech())

    def _make_single_stage(self) -> PartitionResult:
        return _build_single_stage_partition([self.mn], [self.mp], [])

    def _make_two_stage(self) -> PartitionResult:
        mn2 = _nmos_device("m_tc2")
        self.reg.add_transistor(mn2, _nmos_tech(), _pmos_tech())
        result = PartitionResult()
        tc1 = _make_array_structure("DifferentialPair", TechType.N, [self.mn])
        tc2 = _make_array_structure("DifferentialPair", TechType.N, [mn2])
        result.assign(tc1, PartType.TRANSCONDUCTANCE, StageType.FIRST, "tc1")
        result.assign(tc2, PartType.TRANSCONDUCTANCE, StageType.SECOND, "tc2")
        return result

    def test_single_stage_returns_empty(self):
        pz = PolesAndZerosConstraints(
            self._make_single_stage(), self.reg, _simple_specs(), _simple_params()
        )
        assert pz.as_constraints() == []

    def test_two_stage_returns_phase_margin_constraint(self):
        pz = PolesAndZerosConstraints(
            self._make_two_stage(), self.reg, _simple_specs(), _simple_params()
        )
        constraints = pz.as_constraints()
        assert len(constraints) == 1
        assert isinstance(constraints[0], PhaseMarginConstraint)

    def test_phase_margin_description(self):
        pz = PolesAndZerosConstraints(
            self._make_two_stage(), self.reg, _simple_specs(), _simple_params()
        )
        c = pz.as_constraints()[0]
        assert len(c.description()) > 0

    def test_phase_margin_post_calls_adapter(self):
        pz = PolesAndZerosConstraints(
            self._make_two_stage(), self.reg, _simple_specs(), _simple_params()
        )
        c = pz.as_constraints()[0]
        adapter = _MockAdapter()
        c.post(adapter)
        assert any(call[0] == "add_linear" for call in adapter.calls)

    def test_two_stage_missing_first_stage_structs_returns_empty(self):
        mn2 = _nmos_device("m_tc2_missing_first")
        self.reg.add_transistor(mn2, _nmos_tech(), _pmos_tech())
        result = PartitionResult()
        tc2 = _make_array_structure("DifferentialPair", TechType.N, [mn2])
        result.assign(tc2, PartType.TRANSCONDUCTANCE, StageType.SECOND, "tc2")
        pz = PolesAndZerosConstraints(result, self.reg, _simple_specs(), _simple_params())
        assert pz.as_constraints() == []

    def test_two_stage_with_empty_device_lists_returns_empty(self):
        result = PartitionResult()
        tc1 = _make_array_structure("DifferentialPair", TechType.N, [])
        tc2 = _make_array_structure("DifferentialPair", TechType.N, [])
        result.assign(tc1, PartType.TRANSCONDUCTANCE, StageType.FIRST, "tc1")
        result.assign(tc2, PartType.TRANSCONDUCTANCE, StageType.SECOND, "tc2")
        pz = PolesAndZerosConstraints(result, self.reg, _simple_specs(), _simple_params())
        assert pz.as_constraints() == []


# ═══════════════════════════════════════════════════════════════════════
#  TestSizingResult
# ═══════════════════════════════════════════════════════════════════════

class TestDeviceSizing:
    def test_physical_unit_accessors(self):
        d = DeviceSizing("m0", width=10, length=2, current=50_000, vgs=800, vds=700,
                         vov=400, gm=2_000_000, gds=100_000, area=20)
        assert d.width_um == 10.0
        assert d.length_um == 2.0
        assert d.current_ua == pytest.approx(50.0)
        assert d.vgs_v == pytest.approx(0.8)
        assert d.vov_v == pytest.approx(0.4)
        assert d.gm_uav == pytest.approx(2000.0)
        assert d.area_um2 == 20.0

    def test_summary_line(self):
        d = DeviceSizing("m0", width=10, length=2, current=50_000)
        line = d.summary_line()
        assert "m0" in line
        assert "10/2" in line


class TestExpectedPerformance:
    def test_summary(self):
        perf = ExpectedPerformance(
            gain_db=80.0, transit_freq_mhz=2.75, slew_rate=3.5,
            power_mw=0.5, total_area_um2=1200.0, phase_margin_deg=60.0,
        )
        s = perf.summary()
        assert "80.0" in s
        assert "2.75" in s
        assert "60.0" in s


class TestSizingResult:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.raw = {
            "m0": {"width": 10, "length": 2, "current": 50_000, "gm": 2_000_000,
                   "vgs": 800, "vds": 700, "vov": 400, "gds": 100_000, "area": 20},
            "m1": {"width": 5, "length": 2, "current": 50_000, "gm": 1_000_000,
                   "vgs": 900, "vds": 800, "vov": 350, "gds": 50_000, "area": 10},
        }
        self.result = SizingResult.from_solver_values(self.raw)

    def test_device_names_sorted(self):
        assert self.result.device_names == ["m0", "m1"]

    def test_get_device(self):
        d = self.result.get_device("m0")
        assert d.width == 10

    @pytest.mark.parametrize(
        ("attr", "expected"),
        [
            ("total_current_na", 100_000),
            ("total_area_um2", 30.0),
            ("solver_status", "optimal"),
        ],
    )
    def test_aggregate_properties(self, attr, expected):
        assert getattr(self.result, attr) == expected

    def test_summary_contains_device_names(self):
        s = self.result.summary()
        assert "m0" in s
        assert "m1" in s

    def test_repr(self):
        r = repr(self.result)
        assert "2" in r
        assert "optimal" in r

    def test_default_status_unsolved(self):
        r = SizingResult()
        assert r.solver_status == "unsolved"


# ═══════════════════════════════════════════════════════════════════════
#  TestSizingProblemBuild (unit — no real files needed)
# ═══════════════════════════════════════════════════════════════════════

class TestSizingProblemUnit:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.mn = _nmos_device("mn")
        self.mp = _pmos_device("mp")
        self.circuit = _build_simple_circuit()
        self.tech = TechnologyParams(
            thermal_voltage=0.026, nmos=_nmos_tech(), pmos=_pmos_tech()
        )
        self.partition = _build_single_stage_partition([self.mn], [self.mp], [])
        self.circuit_info = CircuitInformation(
            parameters=_simple_params(),
            specifications=_simple_specs(),
            technology=self.tech,
        )
        self.problem = SizingProblem.build(
            self.circuit, self.partition, [], self.circuit_info
        )

    def test_num_transistors(self):
        # 2 MOSFETs in the simple circuit
        assert self.problem.num_transistors == 2

    def test_num_nets_excludes_supply(self):
        # "mid" is internal; vdd!/gnd! are power → only "mid" has voltage var
        assert self.problem.num_nets == 1
        assert set(self.problem.variables.voltages.keys()) == {"mid"}

    def test_total_variables(self):
        expected_min = self.problem.num_transistors * 9 + self.problem.num_nets
        assert self.problem.num_variables == expected_min

    def test_has_shm_constraints(self):
        # 6 SHM per transistor
        assert self.problem.num_constraints >= self.problem.num_transistors * 6

    def test_summary_contains_transistor_names(self):
        s = self.problem.summary()
        assert "mn" in s
        assert "mp" in s

    def test_repr(self):
        r = repr(self.problem)
        assert "transistors" in r
        assert "vars" in r
        assert "constraints" in r

    def test_with_sizing_rules(self):
        rule = MatchedPairRule("DP", "matched", ["mn", "mp"], "matched pair")
        problem = SizingProblem.build(
            self.circuit, self.partition, [rule], self.circuit_info
        )
        # Should add at least 2 extra EqualityConstraints (W and L)
        assert problem.num_constraints > self.problem.num_constraints


# ═══════════════════════════════════════════════════════════════════════
#  Integration — build from real test data files
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _have_test_data(), reason="test data not available")
class TestSizingProblemIntegration:
    """Full pipeline: parse real .hspice → recognize → partition → build problem."""

    @pytest.fixture(scope="class")
    def problem(self):
        from pyckt.io import (
            HSpiceMapping, HSpiceParser, SupplyNetConfig,
            load_device_types, load_circuit_information,
        )
        from recognition.library import Library
        from recognition.recognizer import StructureRecognizer, RuleGenerator
        from partitioning.partitioner import Partitioner

        device_types = load_device_types(DATA / "deviceTypes.xcat")
        mapping = HSpiceMapping.from_file(DATA / "HSpiceMapping.xcat")
        supply_nets = SupplyNetConfig.from_file(DATA / "supplyNets.xcat")
        circuit = HSpiceParser(mapping, supply_nets, device_types).parse(
            DATA / "cascodedSymmetricalCMOSOTA.hspice"
        )
        circuit_info = load_circuit_information(
            DATA / "CircuitParameterAndSpecifications.xml",
            DATA / "TechnologyFile.xml",
        )
        library = Library.from_directory()
        sc = StructureRecognizer(library).recognize(circuit)
        partition = Partitioner(circuit_info.parameters).partition(sc)
        rules = RuleGenerator().generate(sc)
        return SizingProblem.build(circuit, partition, rules, circuit_info)

    def test_has_transistors(self, problem):
        assert problem.num_transistors > 0

    def test_has_variables(self, problem):
        assert problem.num_variables == problem.num_transistors * 9 + problem.num_nets

    def test_has_shm_constraints(self, problem):
        assert problem.num_constraints >= problem.num_transistors * 6

    def test_summary_non_empty(self, problem):
        s = problem.summary()
        assert "transistors" in s.lower() or "Transistors" in s

    def test_repr_sensible(self, problem):
        r = repr(problem)
        assert "transistors" in r
