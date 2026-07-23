"""Synthesis engine — filter, size, and rank op-amp topology candidates.

The :class:`SynthesisEngine` is the core of the Week 8 synthesis pipeline.
Given a populated :class:`~synthesis.library.TopologyLibrary`, a
:class:`~ckt_io.circuit_info_parser.Specifications` object, and optional
:class:`~ckt_io.technology_parser.TechnologyParams`, it:

1. **Filters** the library to the structurally compatible topologies.
2. **Sizes** each candidate (Phase 3: stub estimate; Phase 4+: full CP-SAT solver).
3. **Scores** each sized result using an equal-weight min-max normalized sum.
4. **Returns** the ranked list, best (lowest score) first.

Scoring formula (lower is better) — matches C++ ``SearchSpace::cost_``:

.. math::

   \\text{score} = \\hat{G} + \\hat{P} + \\hat{A} + \\hat{f}_T + \\hat{r}_s

where each hat-term is the min-max normalized value of the metric across all
candidates in the current population.  Gain and transit frequency are inverted
before normalization (higher is better); power, area, and slew-rate are
normalized directly (lower is better).  When all candidates share the same
value for a metric, that contribution is 0.5 for every candidate.

C++ ref: ``AutomaticSizing/src/ConstraintProgram/SearchSpace.cpp`` line 957
"""

from __future__ import annotations

import logging
from typing import Any

from sizing.result import ExpectedPerformance, SizingResult
from synthesis.library import TopologyLibrary, TopologySpec

_log = logging.getLogger(__name__)


class SynthesisEngine:
    """Filter, size, and rank topology candidates.

    Parameters
    ----------
    library:
        Populated topology library to search.
    specifications:
        Performance specifications (a
        :class:`~ckt_io.circuit_info_parser.Specifications` instance or any
        object with ``complementary`` and ``fully_differential`` attributes).
        Attributes that are ``None`` are treated as *unconstrained*.
    technology:
        Optional technology parameters
        (:class:`~ckt_io.technology_parser.TechnologyParams`).
        Reserved for the Phase 4 solver integration; not used in the Phase 3
        stub sizing path.

    Examples
    --------
    >>> from synthesis.library import TopologyLibrary, TopologySpec
    >>> from core.device import TechType
    >>> from ckt_io.circuit_info_parser import Specifications
    >>> lib = TopologyLibrary()
    >>> lib.add(TopologySpec(1, "ota", 1, False, False, TechType.N))
    >>> specs = Specifications(min_gain=60.0, complementary=False)
    >>> engine = SynthesisEngine(lib, specs)
    >>> results = engine.synthesize()
    >>> len(results)
    1
    """

    def __init__(
        self,
        library: TopologyLibrary,
        specifications: Any,
        technology: Any = None,
        circuit_parameter: Any = None,
        sizing_timeout: float = 2.0,
        max_candidates: int | None = None,
    ) -> None:
        self.library = library
        self.specifications = specifications
        self.technology = technology
        #: Operating conditions for the *generated* topologies (rails, input
        #: DC, bias current, load cap) — required for real sizing (#51).
        self.circuit_parameter = circuit_parameter
        #: Per-candidate CP-SAT budget [s] for the real sizing path.
        self.sizing_timeout = sizing_timeout
        #: Cap on how many filtered candidates are sized (None = all) — the
        #: full single-output set is ~3.3k candidates, ~2 s each.
        self.max_candidates = max_candidates
        self._recognition_library = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def synthesize(
        self, mode: str = "small"
    ) -> list[tuple[TopologySpec, SizingResult]]:
        """Filter → size → rank the library.

        Parameters
        ----------
        mode:
            Sizing mode hint.  ``"small"`` (default) picks the fastest path;
            ``"exhaustive"`` is reserved for future use.

        Returns
        -------
        list[tuple[TopologySpec, SizingResult]]
            Pairs of (topology spec, sizing result), sorted ascending by
            score (best candidate first).  Returns ``[]`` when no topology
            passes the filter or every sizing attempt returns ``None``.
        """
        candidates = self._filter_candidates()
        if self.max_candidates is not None:
            candidates = candidates[: self.max_candidates]
        if not candidates:
            _log.warning(
                "SynthesisEngine.synthesize(): no candidates after filtering — "
                "check complementary/fully_differential spec fields."
            )
            return []

        results: list[tuple[TopologySpec, SizingResult]] = []
        for topo in candidates:
            sizing = self._size_topology(topo)
            if sizing is not None:
                results.append((topo, sizing))

        _log.debug(
            "SynthesisEngine: %d candidates, %d sized successfully",
            len(candidates),
            len(results),
        )

        scores = self._compute_scores(results)
        results = [pair for _, pair in sorted(zip(scores, results), key=lambda x: x[0])]
        return results

    # ------------------------------------------------------------------
    # Protected helpers (overridable for testing / subclassing)
    # ------------------------------------------------------------------

    def _filter_candidates(self) -> list[TopologySpec]:
        """Return all library entries that satisfy the structural spec.

        Only ``complementary`` and ``fully_differential`` are used as hard
        filters; other performance specs are handled by the sizing step.
        ``None`` values are treated as unconstrained (no filter applied).

        Returns
        -------
        list[TopologySpec]
            Sorted ascending by id.
        """
        criteria: dict[str, bool] = {}
        specs = self.specifications

        complementary = getattr(specs, "complementary", None)
        if complementary is not None:
            criteria["is_complementary"] = complementary

        fully_differential = getattr(specs, "fully_differential", None)
        if fully_differential is not None:
            criteria["is_fully_differential"] = fully_differential

        return self.library.filter(**criteria)

    def _size_topology(self, topo: TopologySpec) -> SizingResult | None:
        """Size one topology candidate and return a :class:`SizingResult`.

        When the engine has the full context — the candidate's structural
        circuit, technology parameters and operating conditions
        (``circuit_parameter``) — this runs the **real sizing pipeline**
        (recognise → partition → rules → CP-SAT, issue #51) with a
        per-candidate budget of :attr:`sizing_timeout` seconds and ranks on
        the solved performance.  Candidates whose solve finds no feasible
        point within the budget return ``None`` and are excluded, exactly
        as acst drops unsizable candidates (its reference run sized
        868/2260).

        Without that context (bare engines in unit tests, metadata-only
        libraries loaded from a pre-built directory) it falls back to the
        Phase-3 stub estimate so the ranking machinery stays exercisable.

        Parameters
        ----------
        topo:
            Topology metadata.

        Returns
        -------
        SizingResult | None
            A sizing result, or ``None`` if sizing is infeasible (the
            topology will be excluded from the ranked output).
        """
        circuit = self.library.get_circuit(topo.id)
        if (circuit is None or self.technology is None
                or self.circuit_parameter is None):
            return self._stub_sizing(topo)
        return self._solve_topology(topo, circuit)

    @staticmethod
    def _stub_sizing(topo: TopologySpec) -> SizingResult:
        """Phase-3 metadata-derived estimate (fallback path)."""
        num_cascoded = sum(1 for v in topo.has_cascode.values() if v)
        perf = ExpectedPerformance(
            gain_db=60.0 + 10.0 * topo.num_stages,
            transit_freq_mhz=1.0,
            power_mw=0.5 * topo.num_stages,
            total_area_um2=800.0 * topo.num_stages + 200.0 * num_cascoded,
        )
        return SizingResult(solver_status="stub", performance=perf)

    def _params_for(self, topo: TopologySpec):
        """Operating conditions adjusted to the candidate's port shape."""
        from dataclasses import replace

        params = self.circuit_parameter
        if topo.is_fully_differential:
            params = replace(params, output_net="out1")
        return params

    def _solve_topology(
        self, topo: TopologySpec, circuit: Any
    ) -> SizingResult | None:
        """Run recognise → partition → rules → CP-SAT on one candidate."""
        from ckt_io.circuit_info_parser import CircuitInformation
        from core.net import Supply
        from partitioning.partitioner import Partitioner
        from recognition.recognizer import StructureRecognizer
        from recognition.rulegen import RuleGenerator
        from sizing.problem import SizingProblem
        from sizing.solver import SizingSolver

        params = self._params_for(topo)
        # generated circuits carry no supply flags — mark the rails so
        # recognition and the device↔net voltage coupling see them
        for net in circuit.nets:
            if net.name == params.supply_voltage[0]:
                net.supply = Supply.vdd()
            elif net.name == params.ground[0]:
                net.supply = Supply.gnd()

        if self._recognition_library is None:
            from recognition.library import Library
            self._recognition_library = Library.from_directory(None)

        try:
            sc = StructureRecognizer(self._recognition_library).recognize(circuit)
            partition = Partitioner(params).partition(sc)
            rules = RuleGenerator().generate(sc)
            info = CircuitInformation(
                parameters=params,
                specifications=self.specifications,
                technology=self.technology,
            )
            problem = SizingProblem.build(circuit, partition, rules, info)
            solver = SizingSolver(problem)
            solver.timeout_seconds = self.sizing_timeout
            result = solver.solve()
        except Exception as exc:  # unsizable shape — drop the candidate
            _log.debug("topology %d: sizing failed (%s)", topo.id, exc)
            return None
        if not result.devices:
            _log.debug("topology %d: no feasible point within %.1f s",
                       topo.id, self.sizing_timeout)
            return None
        return result

    def _compute_scores(
        self, pairs: list[tuple["TopologySpec", SizingResult]]
    ) -> list[float]:
        """Compute equal-weight min-max normalized scores for all candidates.

        Faithful translation of the C++ ``SearchSpace::cost_`` variable
        (``AutomaticSizing/src/ConstraintProgram/SearchSpace.cpp`` line 957)::

            cost_ = normedGain + normedPower + normedArea
                    + normedTransitFrequency + normedSlewRate

        Each metric is normalized to [0, 1] across the candidate population.
        For metrics where **higher is better** (gain, transit frequency) the
        normalization is inverted so that a higher raw value still produces a
        *lower* (better) score contribution.  When the population range for a
        metric is zero (all values identical) every candidate receives 0.5 for
        that term.

        Slew-rate is not produced by the Phase 3 stub, so its contribution is
        fixed at 0.5 per candidate until the real solver is integrated.

        Parameters
        ----------
        pairs:
            List of ``(TopologySpec, SizingResult)`` pairs as returned by the
            sizing step.  Must be non-empty.

        Returns
        -------
        list[float]
            Scalar score for each pair, in the same order.  Lower is better.
        """
        if not pairs:
            return []

        perfs = [p.performance for _, p in pairs]

        def _norm(vals: list[float], invert: bool = False) -> list[float]:
            """Min-max normalise; invert when higher raw value is better."""
            lo, hi = min(vals), max(vals)
            rng = hi - lo
            if rng == 0.0:
                return [0.5] * len(vals)
            normed = [(v - lo) / rng for v in vals]
            if invert:
                normed = [1.0 - n for n in normed]
            return normed

        gains  = _norm([p.gain_db for p in perfs],           invert=True)
        powers = _norm([p.power_mw for p in perfs],          invert=False)
        areas  = _norm([p.total_area_um2 for p in perfs],    invert=False)
        freqs  = _norm([p.transit_freq_mhz for p in perfs],  invert=True)
        # real solved slew rates when the sizing pipeline produced them;
        # the stub path leaves them at 0.0 → constant 0.5 contribution
        slews  = _norm([p.slew_rate for p in perfs],         invert=True)

        return [
            gains[i] + powers[i] + areas[i] + freqs[i] + slews[i]
            for i in range(len(pairs))
        ]
