"""Sizing solver infrastructure and CP-SAT adapter scaffolding.

Week 7 Phase 1 adds a concrete OR-Tools model adapter and constraint-posting
bridge while keeping end-to-end solve/result extraction for the next phase.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any, Protocol

from .problem import SizingProblem
from .result import ExpectedPerformance, SizingResult

if TYPE_CHECKING:
	from .variables import SizingVariable


def _get_cp_model_module():
	"""Import OR-Tools CP-SAT lazily.

	Keeping this import local allows the module to be imported in environments
	where OR-Tools is not yet installed (for documentation, linting, and tests
	that only exercise stubs).
	"""
	try:
		from ortools.sat.python import cp_model  # type: ignore
	except ModuleNotFoundError as exc:  # pragma: no cover - depends on environment
		raise ModuleNotFoundError(
			"OR-Tools is required for CP-SAT adapter usage. "
			"Install it with: pip install ortools"
		) from exc
	return cp_model


class SolverInterface(Protocol):
	"""Minimal solver API required by sizing constraints."""

	def new_int_var(self, lb: int, ub: int, name: str) -> Any:
		"""Create a new integer variable."""

	def add(self, constraint: Any) -> None:
		"""Add one constraint to the underlying model."""

	def maximize(self, objective: Any) -> None:
		"""Register a maximization objective."""

	def solve(self) -> bool:
		"""Run the solver and return success / feasibility."""

	def value(self, variable: Any) -> int:
		"""Read the solved value of a solver variable."""


class CPSATAdapter:
	"""Translate :class:`SizingProblem` into an OR-Tools ``CpModel``.

	This class provides the posting helper surface consumed by
	``sizing.constraints`` ``post(...)`` implementations.
	"""

	def __init__(self, problem: SizingProblem) -> None:
		self.problem = problem
		self.cp_model = _get_cp_model_module()
		self.model = self.cp_model.CpModel()
		self.cp_vars: dict[str, Any] = {}
		self._tmp_counter = 0

	def build_model(self) -> Any:
		"""Create all variables, post constraints, and apply objective."""
		self._create_variables()
		self._post_constraints()
		self._set_objective()
		return self.model

	def _create_variables(self) -> None:
		for tv in self.problem.variables.transistors.values():
			for sv in tv.all_variables:
				self.cp_vars[sv.name] = self.model.NewIntVar(sv.lower, sv.upper, sv.name)
		for vv in self.problem.variables.voltages.values():
			sv = vv.var
			self.cp_vars[sv.name] = self.model.NewIntVar(sv.lower, sv.upper, sv.name)

	def tmp_var(self, lower: int, upper: int, label: str = "tmp") -> Any:
		"""Create an auxiliary integer variable for nonlinear decompositions."""
		self._tmp_counter += 1
		name = f"{label}_{self._tmp_counter}"
		return self.model.NewIntVar(lower, upper, name)

	def _post_constraints(self) -> None:
		for c in self.problem.constraints:
			c.post(self)

	# Normalisation numerator for the integer multi-objective weights.
	_OBJ_NUM = 1_000_000_000

	def _set_objective(self) -> None:
		"""acst-style normalized multi-objective (maximise), with a min-area fallback.

		Mirrors acst ``SearchSpace::initializeCost``: maximise a weighted sum that
		rewards high gain / transit-frequency / slew-rate and low area / power,
		each weight normalised by its spec range.  Requires amplifier topology
		(partition + circuit + circuit_info, retained on the problem); when that
		context is absent — e.g. a bare ``SizingProblem()`` in a unit test — it
		falls back to the original minimise-area objective.
		"""
		if not self._build_acst_objective():
			area_vars = [
				self.var(tv.area)
				for tv in self.problem.variables.transistors.values()
			]
			if area_vars:
				self.model.Minimize(sum(area_vars))

	def _build_acst_objective(self) -> bool:
		"""Build the maximised normalized objective; return False if not possible."""
		import math as _math

		from .topology import input_pair_devices, output_node_devices

		partition = getattr(self.problem, "partition", None)
		circuit = getattr(self.problem, "circuit", None)
		info = getattr(self.problem, "circuit_info", None)
		if partition is None or circuit is None or info is None:
			return False

		tx = self.problem.variables.transistors
		in_devs = [d for d in input_pair_devices(partition) if d.name in tx]
		out_devs = output_node_devices(circuit, info.parameters.output_net, tx)
		if not in_devs or not out_devs:
			return False

		specs = info.specifications
		params = info.parameters
		vdd = params.supply_voltage[1] or 5.0
		cl_pf = params.load_capacities[0][1] if params.load_capacities else 10.0

		# ── aggregate variables tied to device variables ──────────────
		area_max = max(1, int(specs.max_area)) if specs.max_area > 0 else 1_000_000
		area_total = self.tmp_var(0, area_max, "obj_area")
		self.model.Add(area_total == sum(self.var(tx[d].area) for d in tx))

		power_max_na = (
			max(1, int(specs.max_power / vdd * 1e6))
			if specs.max_power > 0 else 100_000_000
		)
		current_total = self.tmp_var(0, power_max_na, "obj_power")
		self.model.Add(
			current_total == sum(self.var(tx[d].current) for d in tx)
		)

		gm_in = self.var(tx[in_devs[0].name].gm)

		gds_out = self.tmp_var(1, 100_000_000, "obj_gds_out")
		self.model.Add(
			gds_out == sum(self.var(tx[d.name].gds) for d in out_devs)
		)

		i_tail = self.tmp_var(0, 1_000_000_000, "obj_i_tail")
		self.model.Add(
			i_tail == sum(self.var(tx[d.name].current) for d in in_devs)
		)

		# faithful gain ratio:  gm_in == gain_var * gds_out  ⇒  gain_var = gm_in/gds_out
		gain_min_lin = max(1, round(10 ** (specs.min_gain / 20.0))) if specs.min_gain > 0 else 1
		gain_max_lin = max(gain_min_lin + 1, round(10 ** ((specs.min_gain + 10) / 20.0)))
		gain_var = self.tmp_var(0, gain_max_lin, "obj_gain")
		self.add_multiplication(gm_in, gain_var, gds_out)

		# Normalisation caps set near acst's operating point (gain +10 dB,
		# Ft ×3, slew ×7 of spec).  Each objective term is a *clamped* reward in
		# [0, SCALE] that saturates at its cap — acst's [0,1] normalisation — so
		# once the design reaches that modest over-satisfaction the area/power
		# penalties pull it back, instead of burning current to chase unbounded
		# performance.
		gm_ft_min = max(1, _math.ceil(2 * _math.pi * specs.min_transit_freq * cl_pf * 1e3)) \
			if specs.min_transit_freq > 0 else 1
		i_sr_min = max(1, _math.ceil(specs.max_slew_rate * cl_pf * 1e3)) \
			if specs.max_slew_rate > 0 else 1
		gm_ft_max = gm_ft_min * 3
		i_tail_max = i_sr_min * 7

		SCALE = 1000
		rewards = [
			self._reward_term("gain", gain_var, gain_min_lin, gain_max_lin, SCALE, up=True),
			self._reward_term("ft", gm_in, gm_ft_min, gm_ft_max, SCALE, up=True),
			self._reward_term("slew", i_tail, i_sr_min, i_tail_max, SCALE, up=True),
			self._reward_term("area", area_total, 0, area_max, SCALE, up=False),
			self._reward_term("power", current_total, 0, power_max_na, SCALE, up=False),
		]
		self.model.Maximize(sum(rewards))
		return True

	def _reward_term(self, label, value_var, lo, hi, scale, up):
		"""A clamped reward in ``[0, scale]`` (acst-style normalisation).

		``up=True``  → reward rises with the value:  scale·(value−lo)/(hi−lo).
		``up=False`` → reward rises as the value falls: scale·(hi−value)/(hi−lo).
		Implemented as a maximised aux var bounded by the (integer-scaled)
		normalised expression, so the solver clamps it at ``scale`` once the
		value reaches its cap — no single dimension can dominate.
		"""
		span = max(1, hi - lo)
		# reward in [0, scale]; the maximiser drives it to its upper envelope
		reward = self.tmp_var(0, scale, f"obj_reward_{label}")
		if up:
			# reward·span <= scale·(value − lo)
			self.model.Add(reward * span <= scale * (value_var - lo))
		else:
			# reward·span <= scale·(hi − value)
			self.model.Add(reward * span <= scale * (hi - value_var))
		return reward

	# --- constraint helper API consumed by constraints.post(...) ---

	def var(self, sv: SizingVariable) -> Any:
		return self.cp_vars[sv.name]

	def add_equality(self, a: SizingVariable, b: SizingVariable) -> None:
		self.model.Add(self.var(a) == self.var(b))

	def add_product(self, result: SizingVariable, a: SizingVariable, b: SizingVariable) -> None:
		self.model.AddMultiplicationEquality(self.var(result), [self.var(a), self.var(b)])

	def add_multiplication(self, target: Any, a: Any, b: Any) -> None:
		"""``target == a * b`` for raw CP-SAT IntVars (not :class:`SizingVariable`).

		Use this when one or more operands are temp vars from :meth:`tmp_var`
		or have already been resolved via :meth:`var`.  The plain Python
		``Add(target == a * b)`` call fails in CP-SAT because LinearExpr ×
		LinearExpr is unsupported — the solver requires the dedicated
		``AddMultiplicationEquality`` API for variable-times-variable
		products.
		"""
		self.model.AddMultiplicationEquality(target, [a, b])

	def add_ge(self, var: SizingVariable, bound: int) -> None:
		self.model.Add(self.var(var) >= int(bound))

	def add_le(self, var: SizingVariable, bound: int) -> None:
		self.model.Add(self.var(var) <= int(bound))

	def add_linear(self, terms: list[tuple[int, SizingVariable]], relation: str, bound: int) -> None:
		expr = sum(int(coeff) * self.var(sv) for coeff, sv in terms)
		if relation == "==":
			self.model.Add(expr == int(bound))
		elif relation == ">=":
			self.model.Add(expr >= int(bound))
		elif relation == "<=":
			self.model.Add(expr <= int(bound))
		else:
			raise ValueError(f"Unsupported linear relation: {relation}")

	def add_var_bounds(self, var: SizingVariable, lower: int, upper: int) -> None:
		self.model.Add(self.var(var) >= int(lower))
		self.model.Add(self.var(var) <= int(upper))

	def add_raw_constraint(self, constraint: Any) -> None:
		"""Attach a pre-built CP-SAT constraint/expression to the model."""
		self.model.Add(constraint)


class SizingSearchStrategy:
	"""Apply deterministic decision ordering for CP-SAT.

	The strategy follows the Week 7 ordering:
	1) transistor lengths, 2) widths, 3) currents, 4) bias voltages.
	"""

	def __init__(self, adapter: CPSATAdapter, problem: SizingProblem) -> None:
		self.adapter = adapter
		self.problem = problem

	def apply(self) -> None:
		ordered_vars: list[Any] = []

		for tv in self.problem.variables.transistors.values():
			ordered_vars.append(self.adapter.var(tv.length))
		for tv in self.problem.variables.transistors.values():
			ordered_vars.append(self.adapter.var(tv.width))
		for tv in self.problem.variables.transistors.values():
			ordered_vars.append(self.adapter.var(tv.current))
		for tv in self.problem.variables.transistors.values():
			ordered_vars.extend(
				[self.adapter.var(tv.vgs), self.adapter.var(tv.vds), self.adapter.var(tv.vov)]
			)

		if not ordered_vars:
			return

		self.adapter.model.AddDecisionStrategy(
			ordered_vars,
			self.adapter.cp_model.CHOOSE_FIRST,
			self.adapter.cp_model.SELECT_MIN_VALUE,
		)


class SizingSolver:
	"""Wrapper around sizing model posting and (later) solving.

	The class already owns a :class:`SizingProblem` and provides a
	``build_model`` hook. In Week 7 Phase 1, CP-SAT model creation is now
	implemented; ``solve()`` remains deferred.
	"""

	def __init__(self, problem: SizingProblem) -> None:
		self.problem = problem
		self._prepared = False
		self._adapter: CPSATAdapter | None = None
		self.timeout_seconds = 300.0
		self.num_workers = 4
		self.log_search_progress = False

	@property
	def is_prepared(self) -> bool:
		"""Whether constraint posting has been attempted."""
		return self._prepared

	def build_model(self, solver: SolverInterface | None = None) -> Any | None:
		"""Build the model either on a provided backend or on CP-SAT.

		- If *solver* is provided, constraints are posted onto that object
		  (backward-compatible path used by unit tests and custom backends).
		- If *solver* is ``None``, a :class:`CPSATAdapter` is created and
		  returned model is OR-Tools ``CpModel``.
		"""
		if solver is not None:
			for constraint in self.problem.constraints:
				constraint.post(solver)
			self._prepared = True
			return None

		self._adapter = CPSATAdapter(self.problem)
		model = self._adapter.build_model()
		self._prepared = True
		return model

	def solve(self) -> SizingResult:
		"""Build, search, and extract a sizing result from CP-SAT."""
		if self._adapter is None:
			self.build_model()
		assert self._adapter is not None

		strategy = SizingSearchStrategy(self._adapter, self.problem)
		strategy.apply()

		cp_model = self._adapter.cp_model
		solver = cp_model.CpSolver()
		solver.parameters.max_time_in_seconds = float(self.timeout_seconds)
		solver.parameters.num_workers = int(self.num_workers)
		solver.parameters.log_search_progress = bool(self.log_search_progress)

		start = time.perf_counter()
		status = solver.Solve(self._adapter.model)
		elapsed = time.perf_counter() - start

		if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
			return self._extract_result(solver, self._adapter, status, elapsed)

		status_text = self._status_to_text(cp_model, status)
		return SizingResult(
			solver_status=status_text,
			iterations=int(self._safe_solver_stat(solver, "NumBranches", 0)),
			solve_time_seconds=elapsed,
		)

	def _extract_result(
		self,
		solver: Any,
		adapter: CPSATAdapter,
		status: int,
		elapsed: float,
	) -> SizingResult:
		device_values: dict[str, dict[str, int]] = {}
		for name, tv in self.problem.variables.transistors.items():
			device_values[name] = {
				"width": int(solver.Value(adapter.var(tv.width))),
				"length": int(solver.Value(adapter.var(tv.length))),
				"current": int(solver.Value(adapter.var(tv.current))),
				"vgs": int(solver.Value(adapter.var(tv.vgs))),
				"vds": int(solver.Value(adapter.var(tv.vds))),
				"vov": int(solver.Value(adapter.var(tv.vov))),
				"gm": int(solver.Value(adapter.var(tv.gm))),
				"gds": int(solver.Value(adapter.var(tv.gds))),
				"area": int(solver.Value(adapter.var(tv.area))),
			}

		status_text = self._status_to_text(adapter.cp_model, status)
		iterations = int(self._safe_solver_stat(solver, "NumBranches", 0))
		objective_value = self._safe_solver_stat(solver, "ObjectiveValue", None)
		result = SizingResult.from_solver_values(
			device_values,
			solver_status=status_text,
			iterations=iterations,
			solve_time_seconds=elapsed,
			objective_value=objective_value,
		)
		result.performance = self._estimate_performance(result)
		return result

	@staticmethod
	def _safe_solver_stat(solver: Any, name: str, default: Any) -> Any:
		attr = getattr(solver, name, None)
		if attr is None:
			return default
		try:
			return attr() if callable(attr) else attr
		except Exception:
			return default

	@staticmethod
	def _status_to_text(cp_model: Any, status: int) -> str:
		if status == cp_model.OPTIMAL:
			return "optimal"
		if status == cp_model.FEASIBLE:
			return "feasible"
		if status == cp_model.INFEASIBLE:
			return "infeasible"
		if hasattr(cp_model, "MODEL_INVALID") and status == cp_model.MODEL_INVALID:
			return "model_invalid"
		if hasattr(cp_model, "UNKNOWN") and status == cp_model.UNKNOWN:
			return "unknown"
		return f"status_{status}"

	def _estimate_performance(self, result: SizingResult) -> ExpectedPerformance:
		"""First-order performance from solved device values + topology.

		Computes gain, transit frequency, slew rate, phase margin and output
		swing using standard single-stage-OTA equations evaluated on the solved
		operating point.  Gain uses the actual gm(input) / gds(output-node) path
		(not an average of every device), and the frequency metrics use the load
		capacitance and supply from the circuit parameters.

		Falls back to a coarse average-gm/gds estimate when the partition /
		circuit context is unavailable (e.g. a solver constructed directly in a
		unit test).
		"""
		if not result.devices:
			return ExpectedPerformance()

		total_area = result.total_area_um2
		partition = getattr(self.problem, "partition", None)
		circuit = getattr(self.problem, "circuit", None)
		info = getattr(self.problem, "circuit_info", None)

		vdd = self._supply_voltage(info)
		cl_pf = self._load_cap_pf(info)
		power_mw = result.total_current_na / 1e6 * vdd

		if partition is None or circuit is None or info is None:
			return self._coarse_performance(result, power_mw, total_area)

		# input-pair transconductance and tail current (first stage)
		gm_in = self._input_gm(result, partition)
		i_tail_na = self._tail_current_na(result, partition)
		# output-node small-signal conductance
		gds_out, vov_p_mv, vov_n_mv = self._output_node(result, circuit, info)

		gain_db = 0.0
		if gm_in > 0 and gds_out > 0:
			gain_db = 20.0 * math.log10(max(gm_in / gds_out, 1e-9))

		ft_mhz = 0.0
		if gm_in > 0 and cl_pf > 0:
			ft_mhz = gm_in / (2.0 * math.pi * cl_pf) * 1e-3

		slew_rate = 0.0
		if i_tail_na > 0 and cl_pf > 0:
			slew_rate = i_tail_na / cl_pf * 1e-3  # V/µs

		phase_margin = self._phase_margin_deg(result, partition, gm_in, cl_pf)

		# output swing: rails minus the output devices' overdrive
		vout_max = vdd - (vov_p_mv / 1000.0 if vov_p_mv else 0.0)
		vout_min = vov_n_mv / 1000.0 if vov_n_mv else 0.0

		return ExpectedPerformance(
			gain_db=gain_db,
			transit_freq_mhz=ft_mhz,
			slew_rate=slew_rate,
			power_mw=power_mw,
			total_area_um2=total_area,
			phase_margin_deg=phase_margin,
			vout_min_v=vout_min,
			vout_max_v=vout_max,
		)

	# ── performance helpers ───────────────────────────────────────────

	@staticmethod
	def _coarse_performance(result, power_mw, total_area):
		gm_vals = [d.gm for d in result.devices.values() if d.gm > 0]
		gds_vals = [d.gds for d in result.devices.values() if d.gds > 0]
		gain_db = 0.0
		if gm_vals and gds_vals:
			gain_lin = (sum(gm_vals) / len(gm_vals)) / max(1.0, sum(gds_vals) / len(gds_vals))
			gain_db = 20.0 * math.log10(max(gain_lin, 1e-9))
		return ExpectedPerformance(
			gain_db=gain_db, power_mw=power_mw, total_area_um2=total_area,
		)

	@staticmethod
	def _supply_voltage(info) -> float:
		try:
			v = info.parameters.supply_voltage[1]
			return float(v) if v else 5.0
		except Exception:
			return 5.0

	@staticmethod
	def _load_cap_pf(info) -> float:
		try:
			caps = info.parameters.load_capacities
			return float(caps[0][1]) if caps else 0.0
		except Exception:
			return 0.0

	def _input_gm(self, result, partition) -> float:
		"""Transconductance of one input-pair device [nA/V]."""
		from .topology import input_pair_devices
		gms = [result.devices[d.name].gm
		       for d in input_pair_devices(partition) if d.name in result.devices]
		return float(max(gms)) if gms else 0.0

	def _tail_current_na(self, result, partition) -> float:
		"""Total tail current of the input pair [nA] (sum of pair currents)."""
		from .topology import input_pair_devices
		currents = [result.devices[d.name].current
		            for d in input_pair_devices(partition) if d.name in result.devices]
		return float(sum(currents)) if currents else 0.0

	def _output_node(self, result, circuit, info):
		"""(sum gds at output net [nA/V], pmos Vov [mV], nmos Vov [mV])."""
		from core.device import DeviceType, PinType, TechType
		out_net = info.parameters.output_net
		gds_sum = 0.0
		vov_p = vov_n = 0
		for dev in circuit.devices:
			if dev.device_type != DeviceType.MOSFET:
				continue
			try:
				drain = dev.get_net(PinType.DRAIN)
			except Exception:
				continue
			if drain.name != out_net or dev.name not in result.devices:
				continue
			sized = result.devices[dev.name]
			gds_sum += sized.gds
			if dev.tech_type == TechType.P:
				vov_p = max(vov_p, sized.vov)
			elif dev.tech_type == TechType.N:
				vov_n = max(vov_n, sized.vov)
		return gds_sum, vov_p, vov_n

	def _phase_margin_deg(self, result, partition, gm_in, cl_pf) -> float:
		"""First-order two-pole PM: dominant output pole + mirror pole.

		PM = 90° − atan(GBW / p2), with the non-dominant (mirror) pole
		p2 = gm_mirror / (2π·C_mirror) and C_mirror ≈ (2/3)·Σ W·L·Cox over the
		first-stage load devices.  Returns 90° when no second pole can be
		estimated (single dominant pole).
		"""
		from partitioning.result import StageType
		if gm_in <= 0 or cl_pf <= 0:
			return 0.0
		load = partition.load_parts(StageType.FIRST)
		gm_mirror = 0.0
		c_mirror_f = 0.0
		for s in load:
			for d in s.devices:
				if d.name not in result.devices:
					continue
				sized = result.devices[d.name]
				gm_mirror = max(gm_mirror, sized.gm)
				tv = self.problem.variables.transistors.get(d.name)
				cox = getattr(tv.tech, "gate_oxide_capacitance", 0.0) if tv else 0.0
				c_mirror_f += (2.0 / 3.0) * (sized.width * 1e-6) * (sized.length * 1e-6) * cox
		gbw_hz = (gm_in * 1e-9) / (2.0 * math.pi * cl_pf * 1e-12)
		if gm_mirror <= 0 or c_mirror_f <= 0:
			return 90.0
		p2_hz = (gm_mirror * 1e-9) / (2.0 * math.pi * c_mirror_f)
		return 90.0 - math.degrees(math.atan(gbw_hz / p2_hz))

	def summary(self) -> str:
		"""Return a short textual summary of the pending solve."""
		return (
			"SizingSolver\n"
			f"  variables   : {self.problem.num_variables}\n"
			f"  constraints : {self.problem.num_constraints}\n"
			f"  timeout     : {self.timeout_seconds}s\n"
			f"  workers     : {self.num_workers}\n"
			f"  prepared    : {self._prepared}"
		)

	def __repr__(self) -> str:
		return (
			f"SizingSolver(vars={self.problem.num_variables}, "
			f"constraints={self.problem.num_constraints})"
		)
