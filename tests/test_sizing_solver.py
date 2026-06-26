"""Tests for sizing.solver — Phase 2 fake-backend + Phase 4 real OR-Tools smoke tests."""

from __future__ import annotations

import pytest

import sizing.solver as solver_mod
from ckt_io.technology_parser import TransistorTechParams
from core import Device, DeviceType, TechType
from sizing.problem import SizingProblem
from sizing.result import DeviceSizing
from sizing.solver import SizingSearchStrategy, SizingSolver
from sizing.variables import SizingVariableRegistry


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


class _ConstraintRecorder:
	def __init__(self):
		self.calls = 0

	def post(self, solver):
		self.calls += 1


class _FakeExpr:
	def __init__(self, text):
		self.text = str(text)

	def __repr__(self):
		return self.text

	def __add__(self, other):
		return _FakeExpr(f"({self})+({other})")

	def __radd__(self, other):
		if other == 0:
			return self
		return _FakeExpr(f"({other})+({self})")

	def __sub__(self, other):
		return _FakeExpr(f"({self})-({other})")

	def __rsub__(self, other):
		return _FakeExpr(f"({other})-({self})")

	def __mul__(self, other):
		return _FakeExpr(f"({self})*({other})")

	def __rmul__(self, other):
		return _FakeExpr(f"({other})*({self})")

	def __eq__(self, other):  # type: ignore[override]
		return _FakeExpr(f"({self})==({other})")

	def __ge__(self, other):
		return _FakeExpr(f"({self})>=({other})")

	def __le__(self, other):
		return _FakeExpr(f"({self})<=({other})")


class _FakeIntVar(_FakeExpr):
	def __init__(self, lb, ub, name):
		super().__init__(name)
		self.lb = lb
		self.ub = ub
		self.name = name


class _FakeCpModelImpl:
	def __init__(self):
		self.vars = []
		self.constraints = []
		self.objective = None
		self.decision_strategy = None

	def NewIntVar(self, lb, ub, name):
		v = _FakeIntVar(lb, ub, name)
		self.vars.append(v)
		return v

	def Add(self, constraint):
		self.constraints.append(constraint)
		return constraint

	def AddMultiplicationEquality(self, result, terms):
		self.constraints.append(("mul_eq", result, terms))

	def Minimize(self, expr):
		self.objective = expr

	def AddDecisionStrategy(self, vars_, choose, select):
		self.decision_strategy = (vars_, choose, select)


class _FakeCpSolverImpl:
	def __init__(self, module):
		from types import SimpleNamespace
		self._module = module
		self.parameters = SimpleNamespace(
			max_time_in_seconds=0.0,
			num_workers=0,
			log_search_progress=False,
		)
		self._values = {}

	def Solve(self, model):
		self._values = {v.name: max(v.lb, min(v.ub, 7)) for v in model.vars}
		return self._module._next_status

	def Value(self, var):
		return self._values.get(var.name, 0)

	def NumBranches(self):
		return 12

	def ObjectiveValue(self):
		return 77.0


class _FakeCpModule:
	CHOOSE_FIRST = 1
	SELECT_MIN_VALUE = 2
	OPTIMAL = 4
	FEASIBLE = 2
	INFEASIBLE = 3
	UNKNOWN = 0
	MODEL_INVALID = 1
	_next_status = OPTIMAL

	@staticmethod
	def CpModel():
		return _FakeCpModelImpl()

	@staticmethod
	def CpSolver():
		return _FakeCpSolverImpl(_FakeCpModule)


def _make_problem_with_one_transistor() -> SizingProblem:
	problem = SizingProblem()
	reg = problem.variables
	dev = Device("mn", DeviceType.MOSFET, TechType.N)
	reg.add_transistor(dev, _nmos_tech(), _nmos_tech())
	return problem


def test_solver_build_model_sets_prepared_and_posts_all_constraints():
	problem = SizingProblem()
	c1 = _ConstraintRecorder()
	c2 = _ConstraintRecorder()
	problem.constraints = [c1, c2]

	solver = SizingSolver(problem)
	assert solver.is_prepared is False

	solver.build_model(object())

	assert c1.calls == 1
	assert c2.calls == 1
	assert solver.is_prepared is True


def test_search_strategy_applies_decision_order(monkeypatch):
	problem = _make_problem_with_one_transistor()
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)

	adapter = solver_mod.CPSATAdapter(problem)
	adapter.build_model()

	strategy = SizingSearchStrategy(adapter, problem)
	strategy.apply()

	assert adapter.model.decision_strategy is not None
	vars_, choose, select = adapter.model.decision_strategy
	assert len(vars_) >= 6
	assert choose == _FakeCpModule.CHOOSE_FIRST
	assert select == _FakeCpModule.SELECT_MIN_VALUE


@pytest.mark.parametrize(
	("status", "expected"),
	[
		(_FakeCpModule.OPTIMAL, "optimal"),
		(_FakeCpModule.FEASIBLE, "feasible"),
		(_FakeCpModule.INFEASIBLE, "infeasible"),
	],
)
def test_solver_solve_status_handling(monkeypatch, status, expected):
	problem = _make_problem_with_one_transistor()
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)
	_FakeCpModule._next_status = status

	solver = SizingSolver(problem)
	result = solver.solve()

	assert result.solver_status == expected
	if expected in ("optimal", "feasible"):
		assert "mn" in result.devices
		assert result.iterations == 12
		assert result.solve_time_seconds >= 0.0
		assert result.objective_value == 77.0
	else:
		assert result.devices == {}


def test_solver_summary_and_repr():
	problem = SizingProblem()
	solver = SizingSolver(problem)
	s = solver.summary()
	r = repr(solver)
	assert "variables" in s
	assert "constraints" in s
	assert "prepared" in s
	assert "timeout" in s
	assert "workers" in s
	assert "SizingSolver(" in r


def test_device_sizing_remaining_accessors():
	d = DeviceSizing("m0", current=250_000, vds=700, gds=123_000)
	assert d.current_ma == 0.25
	assert d.vds_v == 0.7
	assert d.gds_uav == 123.0


def test_variable_registry_summary_and_repr_cover_remaining_lines():
	reg = SizingVariableRegistry()
	dev = Device("mn", DeviceType.MOSFET, TechType.N)
	reg.add_transistor(dev, _nmos_tech(), _nmos_tech())
	reg.add_voltage("mid")

	s = reg.summary()
	r = repr(reg)
	assert "transistors" in s and "voltage nodes" in s
	assert "SizingVariableRegistry(" in r


# ─────────────────────────────────────────────────────────────────────────
# Coverage gap tests — solver.py uncovered branches
# ─────────────────────────────────────────────────────────────────────────

def test_adapter_voltage_variable_loop(monkeypatch):
	"""CPSATAdapter._create_variables covers the voltage-variable branch (lines 82-83)."""
	problem = SizingProblem()
	dev = Device("mn", DeviceType.MOSFET, TechType.N)
	problem.variables.add_transistor(dev, _nmos_tech(), _nmos_tech())
	problem.variables.add_voltage("vmid")  # triggers the voltages loop

	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)
	adapter = solver_mod.CPSATAdapter(problem)
	adapter.build_model()

	# Voltage variable must appear in the cp_vars map
	assert any("vmid" in k for k in adapter.cp_vars)


def test_adapter_add_ge_and_add_le(monkeypatch):
	"""CPSATAdapter.add_ge / add_le post the correct comparisons (lines 107, 110)."""
	problem = _make_problem_with_one_transistor()
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)

	adapter = solver_mod.CPSATAdapter(problem)
	adapter.build_model()
	tv = problem.variables.transistors["mn"]

	adapter.add_ge(tv.width, 3)
	adapter.add_le(tv.width, 50)

	# Both constraints should appear in the model's constraint list
	texts = [str(c) for c in adapter.model.constraints]
	assert any("3" in t for t in texts)
	assert any("50" in t for t in texts)


def test_adapter_add_linear_le_branch(monkeypatch):
	"""CPSATAdapter.add_linear '<='' branch (line 116) is reached."""
	problem = _make_problem_with_one_transistor()
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)

	adapter = solver_mod.CPSATAdapter(problem)
	adapter.build_model()
	tv = problem.variables.transistors["mn"]

	adapter.add_linear([(1, tv.width)], "<=", 100)
	texts = [str(c) for c in adapter.model.constraints]
	assert any("100" in t for t in texts)


def test_adapter_add_linear_bad_relation_raises(monkeypatch):
	"""CPSATAdapter.add_linear raises ValueError for unknown relation (lines 119-125)."""
	problem = _make_problem_with_one_transistor()
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)

	adapter = solver_mod.CPSATAdapter(problem)
	adapter.build_model()
	tv = problem.variables.transistors["mn"]

	with pytest.raises(ValueError, match="Unsupported linear relation"):
		adapter.add_linear([(1, tv.width)], "!=", 5)


def test_adapter_add_var_bounds(monkeypatch):
	"""CPSATAdapter.add_var_bounds posts two constraints (lines 127-128 / ~130-131)."""
	problem = _make_problem_with_one_transistor()
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)

	adapter = solver_mod.CPSATAdapter(problem)
	adapter.build_model()
	tv = problem.variables.transistors["mn"]

	before = len(adapter.model.constraints)
	adapter.add_var_bounds(tv.width, 5, 20)
	assert len(adapter.model.constraints) == before + 2


def test_adapter_add_raw_constraint(monkeypatch):
	"""CPSATAdapter.add_raw_constraint reaches line 135."""
	problem = _make_problem_with_one_transistor()
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)

	adapter = solver_mod.CPSATAdapter(problem)
	adapter.build_model()

	before = len(adapter.model.constraints)
	adapter.add_raw_constraint(_FakeExpr("dummy"))
	assert len(adapter.model.constraints) == before + 1


def test_search_strategy_early_return_on_empty_problem(monkeypatch):
	"""SizingSearchStrategy.apply returns early when no transistors (line 164)."""
	problem = SizingProblem()  # no transistors → ordered_vars will be empty
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)

	adapter = solver_mod.CPSATAdapter(problem)
	adapter.build_model()

	strategy = SizingSearchStrategy(adapter, problem)
	strategy.apply()  # must not raise; decision_strategy stays None

	assert adapter.model.decision_strategy is None


def test_safe_solver_stat_non_callable_attr():
	"""_safe_solver_stat returns a non-callable attribute directly (line 283-284)."""
	class _FakeWithAttr:
		NumBranches = 42  # plain int, not callable

	result = SizingSolver._safe_solver_stat(_FakeWithAttr(), "NumBranches", 0)
	assert result == 42


def test_safe_solver_stat_exception_returns_default():
	"""_safe_solver_stat catches exceptions and returns default (line 283-284)."""
	class _FakeThrowing:
		def NumBranches(self):
			raise RuntimeError("boom")

	result = SizingSolver._safe_solver_stat(_FakeThrowing(), "NumBranches", 99)
	assert result == 99


def test_status_to_text_model_invalid_and_unknown(monkeypatch):
	"""_status_to_text covers model_invalid and unknown branches (lines 294-298)."""
	problem = _make_problem_with_one_transistor()
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)
	adapter = solver_mod.CPSATAdapter(problem)
	cp_model = adapter.cp_model

	assert SizingSolver._status_to_text(cp_model, cp_model.MODEL_INVALID) == "model_invalid"
	assert SizingSolver._status_to_text(cp_model, cp_model.UNKNOWN) == "unknown"
	assert SizingSolver._status_to_text(cp_model, 999) == "status_999"


def test_status_to_text_numeric_fallback(monkeypatch):
	"""_status_to_text returns 'status_N' for completely unknown status int (line 298)."""
	problem = _make_problem_with_one_transistor()
	monkeypatch.setattr(solver_mod, "_get_cp_model_module", lambda: _FakeCpModule)
	adapter = solver_mod.CPSATAdapter(problem)

	assert SizingSolver._status_to_text(adapter.cp_model, 77) == "status_77"


def test_estimate_performance_no_gm_gds_branch():
	"""_estimate_performance takes the else branch (gain_db=0) when gm or gds is absent (line 320)."""
	from sizing.result import DeviceSizing, SizingResult

	result = SizingResult()
	result.devices = {
		"mx": DeviceSizing("mx", width=5, length=2, current=100_000,
		                   vgs=800, vds=700, vov=300,
		                   gm=0,  # zero → excluded from gm_vals
		                   gds=0, area=10),
	}

	solver = SizingSolver(SizingProblem())
	perf = solver._estimate_performance(result)

	assert perf.gain_db == 0.0
	assert perf.power_mw > 0.0  # current still produces a power estimate


def test_safe_solver_stat_returns_default_when_attr_missing():
	"""`_safe_solver_stat` returns the default when `getattr(...)` yields None
	(solver.py line 292)."""
	class _NoAttr:
		pass
	assert SizingSolver._safe_solver_stat(_NoAttr(), "NumBranches", 7) == 7


def test_estimate_performance_with_no_devices_returns_default():
	"""`_estimate_performance` short-circuits to a default
	`ExpectedPerformance()` when `result.devices` is empty (line 319)."""
	from sizing.result import SizingResult

	solver = SizingSolver(SizingProblem())
	result = SizingResult()
	# `result.devices` defaults to an empty dict — passes the early `if not …`.
	assert not result.devices

	perf = solver._estimate_performance(result)
	# Default ExpectedPerformance fields are all zero.
	assert perf.gain_db == 0.0
	assert perf.power_mw == 0.0


# ─────────────────────────────────────────────────────────────────────────
# Coverage gap — result.py line 257  (summary with objective_value set)
# ─────────────────────────────────────────────────────────────────────────

def test_sizing_result_summary_with_objective_value():
	"""SizingResult.summary() includes the objective line when objective_value is set (line 257)."""
	from sizing.result import DeviceSizing, SizingResult

	result = SizingResult(solver_status="optimal", objective_value=42.5)
	result.devices["mx"] = DeviceSizing("mx", width=5, length=2, current=100_000,
	                                     vgs=800, vds=700, vov=300,
	                                     gm=500_000, gds=20_000, area=10)

	summary = result.summary()
	assert "Objective value" in summary
	assert "42.500" in summary


def test_meets_specs_all_pass():
	"""meets_specs() returns True when all active spec fields are satisfied."""
	from types import SimpleNamespace

	from sizing.result import DeviceSizing, ExpectedPerformance, SizingResult

	result = SizingResult(
		devices={"mx": DeviceSizing("mx", width=5, length=2, current=100_000,
		                            vgs=800, vds=700, vov=300,
		                            gm=500_000, gds=20_000, area=10)},
		performance=ExpectedPerformance(
			gain_db=82.0,
			transit_freq_mhz=3.0,
			slew_rate=2.5,
			power_mw=0.4,
			total_area_um2=500.0,
			phase_margin_deg=65.0,
			vout_min_v=0.5,
			vout_max_v=4.0,
		),
	)
	specs = SimpleNamespace(
		min_gain=60.0,
		min_transit_freq=2.0,
		max_slew_rate=5.0,
		max_power=1.0,
		max_area=1000.0,
		phase_margin=45.0,
		vout_max=4.5,
		vout_min=0.2,
	)
	assert result.meets_specs(specs) is True


def test_meets_specs_one_violation():
	"""meets_specs() returns False when any single spec is violated."""
	from types import SimpleNamespace

	from sizing.result import DeviceSizing, ExpectedPerformance, SizingResult

	result = SizingResult(
		devices={"mx": DeviceSizing("mx", area=10)},
		performance=ExpectedPerformance(gain_db=40.0),  # below min_gain=60
	)
	specs = SimpleNamespace(
		min_gain=60.0,
		min_transit_freq=0.0,
		max_slew_rate=0.0,
		max_power=0.0,
		max_area=0.0,
		phase_margin=0.0,
		vout_max=0.0,
		vout_min=0.0,
	)
	assert result.meets_specs(specs) is False


def test_meets_specs_zero_threshold_skipped():
	"""meets_specs() treats zero-valued spec fields as unconstrained."""
	from types import SimpleNamespace

	from sizing.result import DeviceSizing, ExpectedPerformance, SizingResult

	# performance has gain_db=0 but min_gain=0 so it should be skipped
	result = SizingResult(
		devices={"mx": DeviceSizing("mx", area=5)},
		performance=ExpectedPerformance(),  # all zeros
	)
	specs = SimpleNamespace(
		min_gain=0.0, min_transit_freq=0.0, max_slew_rate=0.0,
		max_power=0.0, max_area=0.0, phase_margin=0.0,
		vout_max=0.0, vout_min=0.0,
	)
	assert result.meets_specs(specs) is True


def test_meets_specs_no_devices_returns_false():
	"""meets_specs() returns False for an infeasible (empty devices) result."""
	from types import SimpleNamespace

	from sizing.result import SizingResult

	result = SizingResult(solver_status="infeasible")
	specs = SimpleNamespace(
		min_gain=0.0, min_transit_freq=0.0, max_slew_rate=0.0,
		max_power=0.0, max_area=0.0, phase_margin=0.0,
		vout_max=0.0, vout_min=0.0,
	)
	assert result.meets_specs(specs) is False


# ─────────────────────────────────────────────────────────────────────────
# Phase 4 — real OR-Tools CP-SAT smoke tests
# ─────────────────────────────────────────────────────────────────────────

ortools = pytest.importorskip("ortools", reason="ortools not installed")


def _tiny_problem_with_bounds() -> SizingProblem:
	"""A SizingProblem with one transistor and tight variable bounds.

	All nine per-transistor variables are pinned to a single value each via
	BoundsConstraint.  This guarantees a trivially feasible problem with an
	unambiguous solved-value that we can assert on without relying on any SHM
	physics.  The area variable is also pinned so the minimum-area objective
	has a deterministic result.
	"""
	from sizing.constraints import BoundsConstraint

	problem = SizingProblem()
	reg = problem.variables
	dev = Device("mx", DeviceType.MOSFET, TechType.N)
	reg.add_transistor(dev, _nmos_tech(), _nmos_tech())
	tv = reg.transistors["mx"]

	# Pin every variable to a fixed value so the problem is trivially OPTIMAL.
	pins = [
		(tv.width,   5,       5),
		(tv.length,  2,       2),
		(tv.current, 100_000, 100_000),
		(tv.vgs,     800,     800),
		(tv.vds,     700,     700),
		(tv.vov,     300,     300),
		(tv.gm,      500_000, 500_000),
		(tv.gds,     20_000,  20_000),
		(tv.area,    10,      10),
	]
	for var, lo, hi in pins:
		problem.constraints.append(BoundsConstraint(var, lo, hi))

	return problem


def test_real_ortools_feasible_smoke():
	"""Phase 4: real CP-SAT solve returns OPTIMAL for a trivially pinned problem."""
	problem = _tiny_problem_with_bounds()
	solver = SizingSolver(problem)

	result = solver.solve()

	assert result.solver_status in ("optimal", "feasible")
	assert "mx" in result.devices

	mx = result.devices["mx"]
	assert mx.width == 5
	assert mx.length == 2
	assert mx.current == 100_000
	assert mx.area == 10


def test_real_ortools_infeasible_detection():
	"""Phase 4: mutually exclusive bounds produce an infeasible result, not an exception."""
	from sizing.constraints import BoundsConstraint

	problem = SizingProblem()
	reg = problem.variables
	dev = Device("mx", DeviceType.MOSFET, TechType.N)
	reg.add_transistor(dev, _nmos_tech(), _nmos_tech())
	tv = reg.transistors["mx"]

	# Contradict: width must be <= 3 AND >= 7 simultaneously.
	problem.constraints.append(BoundsConstraint(tv.width, 7, 1000))
	problem.constraints.append(BoundsConstraint(tv.width, 1, 3))

	solver = SizingSolver(problem)
	result = solver.solve()

	assert result.solver_status == "infeasible"
	assert result.devices == {}


def test_real_ortools_objective_minimizes_area():
	"""Phase 4: objective value reflects minimum total area when two widths are feasible."""
	from sizing.constraints import BoundsConstraint

	# Build a problem where width can be 5 or 10 and length is fixed.
	# CP-SAT min-area objective should pick width=5 (area = 5*2 = 10).
	problem = SizingProblem()
	reg = problem.variables
	dev = Device("mx", DeviceType.MOSFET, TechType.N)
	reg.add_transistor(dev, _nmos_tech(), _nmos_tech())
	tv = reg.transistors["mx"]

	problem.constraints.append(BoundsConstraint(tv.width, 5, 10))
	problem.constraints.append(BoundsConstraint(tv.length, 2, 2))
	problem.constraints.append(BoundsConstraint(tv.current, 100_000, 100_000))
	problem.constraints.append(BoundsConstraint(tv.vgs, 800, 800))
	problem.constraints.append(BoundsConstraint(tv.vds, 700, 700))
	problem.constraints.append(BoundsConstraint(tv.vov, 300, 300))
	problem.constraints.append(BoundsConstraint(tv.gm, 500_000, 500_000))
	problem.constraints.append(BoundsConstraint(tv.gds, 20_000, 20_000))

	solver = SizingSolver(problem)
	result = solver.solve()

	assert result.solver_status in ("optimal", "feasible")
	assert result.devices["mx"].width == 5
	assert result.objective_value is not None

