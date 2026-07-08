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

		from .topology import input_pair_devices, output_branches, output_node_devices

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
		# power = Vdd · supply current: count each branch once via the
		# devices hanging off the supply rail (acst calculatePowerConsumption).
		# Summing *every* device double-counts series stacks and, capped at
		# the spec, silently excludes acst's whole operating region.
		supply_devs = self._supply_rail_device_names(circuit, info)
		power_terms = [self.var(tx[d].current) for d in supply_devs if d in tx]
		if not power_terms:
			power_terms = [self.var(tx[d].current) for d in tx]
		current_total = self.tmp_var(0, power_max_na, "obj_power")
		self.model.Add(current_total == sum(power_terms))

		gm_in = self.var(tx[in_devs[0].name].gm)

		# output conductance with the same cascode composition as the gain
		# constraint (g_eff·gm_casc >= gds_casc·gds_bottom per branch) — an
		# aggregate over *raw* gds overstates the conductance of a cascoded
		# output by orders of magnitude and, combined with the gain reward,
		# demands an impossible gm_in (spurious infeasibility).
		gds_out = self.tmp_var(1, 100_000_000, "obj_gds_out")
		branch_terms = []
		for casc, bottom in output_branches(
				circuit, info.parameters.output_net, tx):
			casc_tv = tx[casc.name]
			if bottom is None:
				branch_terms.append(self.var(casc_tv.gds))
				continue
			bot_tv = tx[bottom.name]
			g_eff = self.tmp_var(0, casc_tv.gds.upper, "obj_geff")
			prod = self.tmp_var(
				0, casc_tv.gds.upper * bot_tv.gds.upper, "obj_gds2")
			lhs = self.tmp_var(
				0, casc_tv.gds.upper * casc_tv.gm.upper, "obj_geff_gm")
			self.add_multiplication(
				prod, self.var(casc_tv.gds), self.var(bot_tv.gds))
			self.add_multiplication(lhs, g_eff, self.var(casc_tv.gm))
			self.model.Add(lhs >= prod)
			branch_terms.append(g_eff)
		self.model.Add(gds_out == sum(branch_terms))

		# the load cap slews with the *output branch* current (acst's
		# calculateSlewRate); rewarding the input tail lets the mirror
		# ratio starve the output branch
		i_slew = self.tmp_var(0, 1_000_000_000, "obj_i_slew")
		self.model.Add(
			i_slew == sum(self.var(tx[d.name].current) for d in out_devs)
		)

		# gain ratio as an *inequality*: gain_var·gds_out <= gm_in, so
		# gain_var rides at floor(gm_in/gds_out).  An equality would force
		# gm_in to be an exact integer multiple of gds_out — a divisibility
		# trap that cripples CP-SAT's search on an otherwise-feasible model.
		gain_min_lin = max(1, round(10 ** (specs.min_gain / 20.0))) if specs.min_gain > 0 else 1
		gain_max_lin = max(gain_min_lin + 1, round(10 ** ((specs.min_gain + 10) / 20.0)))
		gain_var = self.tmp_var(0, gain_max_lin, "obj_gain")
		gain_prod = self.tmp_var(0, gain_max_lin * 100_000_000, "obj_gain_prod")
		self.add_multiplication(gain_prod, gain_var, gds_out)
		self.model.Add(gain_prod <= gm_in)

		# Normalisation caps set near acst's operating point (gain +10 dB,
		# Ft ×3, slew ×7 of spec).  Each objective term is a *clamped* reward in
		# [0, SCALE] that saturates at its cap — acst's [0,1] normalisation — so
		# once the design reaches that modest over-satisfaction the area/power
		# penalties pull it back, instead of burning current to chase unbounded
		# performance.
		gm_ft_min = max(1, _math.ceil(2 * _math.pi * specs.min_transit_freq * cl_pf * 1e3)) \
			if specs.min_transit_freq > 0 else 1
		gm_ft_max = gm_ft_min * 3
		# both output branches drive C_L: SR = 2·I_branch/C_L
		i_slew_min = max(1, _math.ceil(specs.max_slew_rate * cl_pf * 1e3)) \
			if specs.max_slew_rate > 0 else 1
		i_slew_max = i_slew_min * 7

		SCALE = 1000
		rewards = [
			self._reward_term("gain", gain_var, gain_min_lin, gain_max_lin, SCALE, up=True),
			self._reward_term("ft", gm_in, gm_ft_min, gm_ft_max, SCALE, up=True),
			self._reward_term("slew", i_slew, i_slew_min, i_slew_max, SCALE, up=True),
			self._reward_term("area", area_total, 0, area_max, SCALE, up=False),
			self._reward_term("power", current_total, 0, power_max_na, SCALE, up=False),
		]
		self.model.Maximize(sum(rewards))
		return True

	@staticmethod
	def _supply_rail_device_names(circuit, info) -> list[str]:
		"""Names of MOSFETs with a source/drain pin on the supply rail."""
		from core.device import DeviceType, PinType
		supply_net = info.parameters.supply_voltage[0]
		names: list[str] = []
		for dev in circuit.devices:
			if dev.device_type != DeviceType.MOSFET:
				continue
			for pin in (PinType.SOURCE, PinType.DRAIN):
				try:
					net = dev.get_net(pin)
				except Exception:
					continue
				if net.name == supply_net:
					names.append(dev.name)
					break
		return names

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

		# The fixed min-value-first decision strategy biases every incumbent
		# toward minimum device sizes and starves the optimisation phase;
		# CP-SAT's default portfolio search climbs the objective far faster.
		# Keep the deterministic ordering only for pure feasibility runs
		# (no objective context).
		if getattr(self.problem, "partition", None) is None:
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
		result.net_voltages = self._extract_net_voltages(solver, adapter)
		result.capacitors = self._extract_capacitors()
		return result

	def _extract_net_voltages(self, solver: Any, adapter: CPSATAdapter) -> dict[str, float]:
		"""Solved DC operating point per net [V], including the fixed rails.

		The solver carries one voltage variable per non-supply net (coupled to
		every device's Vgs/Vds); the rails come from the circuit parameters so
		the emitted ``<Voltages>`` section lists every net, as acst's does
		(issue #49).
		"""
		voltages = {
			name: solver.Value(adapter.var(vv.var)) / 1000.0
			for name, vv in self.problem.variables.voltages.items()
		}
		info = getattr(self.problem, "circuit_info", None)
		if info is not None:
			for net, volts in (info.parameters.supply_voltage,
			                   info.parameters.ground):
				if net:
					voltages[net] = float(volts)
		return voltages

	def _extract_capacitors(self) -> dict[str, float]:
		"""Capacitor values [pF] for the acst ``<Capacitors>`` section.

		pyckt has no capacitor-sizing variables yet: the load capacitors are
		fixed circuit parameters, which is also the value acst reports for
		them (issue #49).
		"""
		info = getattr(self.problem, "circuit_info", None)
		if info is None:
			return {}
		return {name: float(value)
		        for name, value in info.parameters.load_capacities}

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

		if partition is None or circuit is None or info is None:
			power_mw = result.total_current_na / 1e6 * vdd
			return self._coarse_performance(result, power_mw, total_area)

		# supply current counts each branch once (the devices hanging off the
		# supply rail, plus the external bias) — summing every device's Id
		# double-counts stacked branches (acst calculatePowerConsumption)
		power_mw = self._supply_current_na(result, circuit, info) / 1e6 * vdd

		# input-pair transconductance and tail current (first stage)
		gm_in = self._input_gm(result, partition)
		i_tail_na = self._tail_current_na(result, partition)
		# output-node small-signal conductance (cascode-composed) and swing
		gds_out, vov_p_mv, vov_n_mv = self._output_node(result, circuit, info)
		# mirror scaling factor B of the symmetrical OTA: the ratio of the
		# output-branch current to one input-branch current (acst's
		# computeScalingFactorForSymmetricalOTA); 1.0 when unresolvable.
		i_out_na = self._output_branch_current_na(result, circuit, info)
		b_factor = 1.0
		if i_tail_na > 0 and i_out_na > 0:
			b_factor = i_out_na / (i_tail_na / 2.0)

		gain_db = 0.0
		if gm_in > 0 and gds_out > 0:
			gain_db = 20.0 * math.log10(max(b_factor * gm_in / gds_out, 1e-9))

		ft_mhz = 0.0
		if gm_in > 0 and cl_pf > 0:
			ft_mhz = b_factor * gm_in / (2.0 * math.pi * cl_pf) * 1e-3

		# the load cap slews with the *output branch* current (acst's
		# calculateSlewRate uses the currents that reach the output)
		slew_rate = 0.0
		i_slew_na = 2.0 * i_out_na if i_out_na > 0 else i_tail_na
		if i_slew_na > 0 and cl_pf > 0:
			slew_rate = i_slew_na / cl_pf * 1e-3  # V/µs

		phase_margin = self._phase_margin_deg(result, partition, gm_in, cl_pf)

		# output swing: rails minus the output devices' overdrive
		vout_max = vdd - (vov_p_mv / 1000.0 if vov_p_mv else 0.0)
		vout_min = vov_n_mv / 1000.0 if vov_n_mv else 0.0

		perf = ExpectedPerformance(
			gain_db=gain_db,
			transit_freq_mhz=ft_mhz,
			slew_rate=slew_rate,
			power_mw=power_mw,
			total_area_um2=total_area,
			phase_margin_deg=phase_margin,
			vout_min_v=vout_min,
			vout_max_v=vout_max,
		)
		self._ac_metrics(perf, result, circuit, info, partition, gain_db, gm_in)
		return perf

	# ── AC / common-mode metrics (issue #50) ──────────────────────────

	def _ac_metrics(self, perf, result, circuit, info, partition,
	                gain_db, gm_in) -> None:
		"""CMRR, PSRR and common-mode input range (acst's models).

		Ports the post-solve value side of acst's
		``calculateCMRR`` / ``calculateNegPSRR`` / ``calculatePosPSRR`` /
		``calculateCommonModeInputVoltage``
		(CircuitSpecificationsConstraints.cpp), each validated against the
		reference design's reported values (133 dB / 46 / 55 / 4.24 V /
		1.15 V).  The formulas apply to the mirror-OTA shape acst derives
		them for; when a piece cannot be resolved topologically the metric
		stays ``None`` and the writer omits it — the same behaviour as
		acst's ``hasCMRR()``-style guards.
		"""
		pieces = self._first_stage_pieces(result, circuit, info, partition)
		if pieces is None or gain_db <= 0 or gm_in <= 0:
			return
		d_in, tail, load, casc, bias2 = pieces
		vdd = self._supply_voltage(info)
		vss = float(info.parameters.ground[1]) if info.parameters.ground[0] else 0.0

		s_in, s_tail, s_load = (result.devices[d.name] for d in (d_in, tail, load))
		gain_lin = 10.0 ** (gain_db / 20.0)

		# CMRR = opAmpGain · 2·gm(load diode) / gds(tail)     [dB]
		if s_load.gm > 0 and s_tail.gds > 0:
			perf.cmrr_db = 20.0 * math.log10(
				gain_lin * 2.0 * s_load.gm / s_tail.gds)

		# PSRR needs the (opposite-tech) mirrored output branch and its
		# cascode-gate bias diode
		if casc is not None:
			s_casc = result.devices[casc.name]
			a1 = gm_in / s_load.gm if s_load.gm > 0 else 0.0  # diode-loaded A1
			if a1 > 0 and s_casc.gm > 0 and s_casc.gds > 0:
				perf.pos_psrr_deg = 20.0 * math.log10(
					a1 * s_casc.gm / s_casc.gds)
			if (a1 > 0 and bias2 is not None
					and s_load.gm > 0 and s_casc.gm > 0):
				s_b2 = result.devices[bias2.name]
				denom = abs(2.0 * s_load.gm * s_b2.gds
				            - s_casc.gm * s_tail.gds)
				if denom > 0:
					perf.neg_psrr_deg = 20.0 * math.log10(
						2.0 * a1 * s_load.gm * s_casc.gm / denom)

		# common-mode input range: the Vgs stack from the input gate down
		# the bias path (tail) and up the load path (mirror diode)
		from core.device import TechType
		tech = info.technology
		if d_in.tech_type == TechType.N:
			vth_in = abs(tech.nmos.threshold_voltage)
			perf.min_cm_input_v = (vss + s_in.vov / 1e3 + s_tail.vgs / 1e3)
			perf.max_cm_input_v = (vdd + vth_in - s_load.vgs / 1e3)
		else:
			vth_in = abs(tech.pmos.threshold_voltage)
			perf.max_cm_input_v = (vdd - s_in.vov / 1e3 - s_tail.vgs / 1e3)
			perf.min_cm_input_v = (vss - vth_in + s_load.vgs / 1e3)

	def _first_stage_pieces(self, result, circuit, info, partition):
		"""Resolve (input, tail, load diode, output cascode, its bias diode).

		All topological: the tail's drain sits on the pair's common-source
		net; the load mirror diode is gate-and-drain-connected on an
		input-pair drain; the primary output branch is the opposite-tech
		cascode from :func:`output_branches`; its bias diode drives the
		cascode gate.  Returns ``None`` when the shape doesn't match.
		"""
		from core.device import DeviceType, PinType

		from .topology import input_pair_devices, output_branches

		def net(dev, pin):
			try:
				return dev.get_net(pin).name
			except Exception:
				return None

		ins = [d for d in input_pair_devices(partition)
		       if d.name in result.devices]
		if not ins:
			return None
		d_in = ins[0]
		mosfets = [d for d in circuit.devices
		           if d.device_type == DeviceType.MOSFET
		           and d.name in result.devices]

		src_net = net(d_in, PinType.SOURCE)
		tail = next((d for d in mosfets
		             if d is not d_in and net(d, PinType.DRAIN) == src_net),
		            None)

		pair_drains = {net(d, PinType.DRAIN) for d in ins}
		load = next((d for d in mosfets
		             if net(d, PinType.DRAIN) in pair_drains
		             and net(d, PinType.GATE) == net(d, PinType.DRAIN)),
		            None)
		if tail is None or load is None:
			return None

		casc = next((c for c, _bottom in output_branches(
			circuit, info.parameters.output_net, result.devices)
			if c.tech_type != d_in.tech_type), None)
		bias2 = None
		if casc is not None:
			casc_gate = net(casc, PinType.GATE)
			bias2 = next((d for d in mosfets
			              if net(d, PinType.DRAIN) == casc_gate
			              and net(d, PinType.GATE) == casc_gate),
			             None)
		return d_in, tail, load, casc, bias2

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
		"""(effective conductance at output net [nA/V], pmos/nmos Vov [mV]).

		A cascoded output branch contributes gds_casc·gds_bottom/gm_casc
		(acst's composition), a plain branch its raw gds.
		"""
		from core.device import TechType

		from .topology import output_branches
		out_net = info.parameters.output_net
		gds_sum = 0.0
		vov_p = vov_n = 0
		for casc, bottom in output_branches(circuit, out_net, result.devices):
			sized = result.devices[casc.name]
			if bottom is not None and sized.gm > 0:
				bot = result.devices[bottom.name]
				gds_sum += sized.gds * bot.gds / sized.gm
			else:
				gds_sum += sized.gds
			# the branch limits the swing with its *stacked* overdrives
			# (Vov_casc + Vov_bottom), acst's Min/MaximumOutputVoltage
			stack_vov = sized.vov + (
				result.devices[bottom.name].vov if bottom is not None else 0
			)
			if casc.tech_type == TechType.P:
				vov_p = max(vov_p, stack_vov)
			elif casc.tech_type == TechType.N:
				vov_n = max(vov_n, stack_vov)
		return gds_sum, vov_p, vov_n

	def _output_branch_current_na(self, result, circuit, info) -> float:
		"""One output branch's drain current [nA] (max over output devices)."""
		from .topology import output_node_devices
		out_net = info.parameters.output_net
		currents = [result.devices[d.name].current
		            for d in output_node_devices(circuit, out_net, result.devices)]
		return float(max(currents)) if currents else 0.0

	def _supply_current_na(self, result, circuit, info) -> float:
		"""Current drawn from the supply rail [nA]: branch currents of devices
		with a source/drain pin on the supply net, plus the external bias."""
		from core.device import DeviceType, PinType
		supply_net = info.parameters.supply_voltage[0]
		total = 0.0
		seen = False
		for dev in circuit.devices:
			if dev.device_type != DeviceType.MOSFET or dev.name not in result.devices:
				continue
			for pin in (PinType.SOURCE, PinType.DRAIN):
				try:
					net = dev.get_net(pin)
				except Exception:
					continue
				if net.name == supply_net:
					total += result.devices[dev.name].current
					seen = True
					break
		if not seen:
			return float(result.total_current_na)
		bias_ua = info.parameters.bias_current[1] if info.parameters.bias_current else 0.0
		return total + bias_ua * 1e3

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
