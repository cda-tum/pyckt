"""Synthesis analysis pipeline — initialize → compute → write.

:class:`SynthesisAnalysis` is the top-level orchestrator for the synthesis
flow.  It is dispatched by ``--analysis synthesis`` and follows the
three-phase ``AbstractAnalysis`` contract.

Pipeline
--------
1. **initialize()** — parse the circuit-specification XML to obtain a
   :class:`~ckt_io.circuit_info_parser.Specifications` object and
   (optionally) load a pre-built topology library from disk or generate
   a fresh one via :class:`~synthesis.generator.TopologyLibraryGenerator`.
2. **compute()** — instantiate a :class:`~synthesis.engine.SynthesisEngine`
   and run :meth:`~synthesis.engine.SynthesisEngine.synthesize`.
   Logs a warning if no candidates survive the filter step.
3. **write()** — serialise ranked results to *output_dir* as one JSON
   summary file plus one ``.ckt`` HSpice netlist per topology, rendered via
   :class:`~ckt_io.hspice_writer.AcstNetlistWriter` from each candidate's
   flat circuit (when the library retains one — see :meth:`write`).

C++ ref: ``Synthesis::Synthesis::initialize / compute / write``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ckt_io.hspice_writer import AcstNetlistWriter
from core.common import AbstractAnalysis
from synthesis.engine import SynthesisEngine
from synthesis.library import TopologyLibrary, TopologySpec

_log = logging.getLogger(__name__)


class SynthesisAnalysis(AbstractAnalysis):
    """Synthesis — dispatched by ``--analysis synthesis``.

    Parameters
    ----------
    args:
        Parsed CLI namespace.  Expected attributes (all optional; missing
        ones cause graceful errors at the appropriate phase):

        * ``xml_spec_file``  — path to ``CircuitParameterAndSpecifications.xml``
        * ``xml_tech_file``  — path to ``TechnologieFile.xml``
        * ``library_dir``    — path to a pre-built topology library directory;
          when absent or empty the library is generated from scratch.
        * ``output_dir``     — directory for ranked output files.
    """

    def __init__(self, args) -> None:
        super().__init__(args)
        self.specifications = None
        self.technology = None
        self.circuit_parameter = None
        self.library: TopologyLibrary | None = None
        self.engine: SynthesisEngine | None = None
        self.results: list[tuple[TopologySpec, object]] = []

    @staticmethod
    def _parse_operating_parameters(spec_path):
        """Build a :class:`CircuitParameter` for the *generated* topologies.

        The synthesis ``CircuitSpecifications.xml`` carries the operating
        conditions inline (``SupplyVoltage``/``GroundVoltage``/
        ``InputVoltage``/``LoadCapacity``/``BiasCurrent``); the generated
        circuits use the canonical port names (``ibias in1 in2 out
        source_nmos source_pmos`` and ``Cap_load_1``).  Returns ``None``
        when the tags are absent (non-synthesis spec files) — the engine
        then falls back to stub sizing.
        """
        from ckt_io.circuit_info_parser import CircuitParameter, _read_xml

        root = _read_xml(spec_path)
        spec = root.find("Specifications")
        if spec is None:
            return None

        def attr(tag, name):
            el = spec.find(tag)
            return float(el.get(name)) if el is not None and el.get(name) else None

        vdd = attr("SupplyVoltage", "Vdd")
        gnd = attr("GroundVoltage", "Gnd")
        vin = attr("InputVoltage", "Vin")
        cl = attr("LoadCapacity", "Cl")
        ibias = attr("BiasCurrent", "Ibias")
        if vdd is None or vin is None or cl is None:
            return None
        return CircuitParameter(
            load_capacities=[("Cap_load_1", cl)],
            supply_voltage=("source_pmos", vdd),
            ground=("source_nmos", gnd if gnd is not None else 0.0),
            bias_current=("ibias", ibias if ibias is not None else 0.0),
            input_plus=("in1", vin),
            input_minus=("in2", vin),
            output_net="out",
        )

    # ------------------------------------------------------------------
    # Phase 1 — initialize
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Parse specifications XML and load (or generate) the topology library.

        Steps
        -----
        1. Parse ``args.xml_spec_file`` for a
           :class:`~ckt_io.circuit_info_parser.Specifications` object.
           If ``args.xml_tech_file`` is also provided, load
           :class:`~ckt_io.technology_parser.TechnologyParams` as well.
        2. If ``args.library_dir`` is set and the directory exists, load the
           library via :meth:`~synthesis.library.TopologyLibrary.from_directory`.
           Otherwise generate a fresh library with
           :class:`~synthesis.generator.TopologyLibraryGenerator` and
           cache it to ``args.library_dir`` (if specified).

        Raises
        ------
        ValueError
            If ``args.xml_spec_file`` is missing or the path does not exist.
        """
        # -- Specifications -------------------------------------------------
        spec_path = getattr(self.args, "xml_spec_file", None)
        if not spec_path:
            raise ValueError(
                "SynthesisAnalysis.initialize(): --xml-spec-file is required"
            )
        if not Path(spec_path).exists():
            raise FileNotFoundError(
                f"SynthesisAnalysis: spec file not found: {spec_path}"
            )

        from ckt_io.circuit_info_parser import parse_specifications

        self.specifications = parse_specifications(spec_path)
        self.circuit_parameter = self._parse_operating_parameters(spec_path)
        _log.debug("Loaded specifications from %s", spec_path)

        # -- Technology (optional) ------------------------------------------
        tech_path = getattr(self.args, "xml_tech_file", None)
        if tech_path and Path(tech_path).exists():
            from ckt_io.technology_parser import TechnologyParams

            self.technology = TechnologyParams.from_file(tech_path)
            _log.debug("Loaded technology params from %s", tech_path)

        # -- Topology library -----------------------------------------------
        library_dir = getattr(self.args, "library_dir", None)
        if library_dir and Path(library_dir).exists():
            _log.info("Loading topology library from %s", library_dir)
            self.library = TopologyLibrary.from_directory(library_dir)
        else:
            _log.info(
                "Generating topology library%s",
                f" → {library_dir}" if library_dir else " (in-memory only)",
            )
            from synthesis.generator import TopologyLibraryGenerator

            gen = TopologyLibraryGenerator(output_dir=library_dir or None)
            self.library = gen.generate()

        _log.info("Topology library ready: %d topologies", self.library.size())

    # ------------------------------------------------------------------
    # Phase 2 — compute
    # ------------------------------------------------------------------

    def compute(self) -> None:
        """Run the synthesis engine to filter, size, and rank candidates.

        Requires :meth:`initialize` to have completed successfully.

        Logs a warning when no candidates survive the structural filter so
        that the user knows their specification constraints may be too tight.

        Raises
        ------
        RuntimeError
            If ``initialize()`` has not been called (library is ``None``).
        """
        library = self._require_initialized(self.library, "library")
        specs = self._require_initialized(self.specifications, "specifications")

        self.engine = SynthesisEngine(
            library=library,
            specifications=specs,
            technology=self.technology,
            circuit_parameter=self.circuit_parameter,
            sizing_timeout=float(getattr(self.args, "sizing_timeout", 2.0)),
            max_candidates=getattr(self.args, "max_candidates", None),
        )
        self.results = self.engine.synthesize()

        if not self.results:
            _log.warning(
                "SynthesisAnalysis.compute(): synthesize() returned no results — "
                "no topologies matched the filter criteria. "
                "Consider relaxing complementary/fully_differential constraints."
            )
        else:
            _log.info(
                "SynthesisAnalysis.compute(): %d ranked candidate(s)", len(self.results)
            )

    # ------------------------------------------------------------------
    # Phase 3 — write
    # ------------------------------------------------------------------

    def write(self) -> None:
        """Write ranked synthesis results to *output_dir*.

        Output layout::

            output_dir/
            ├── synthesis_results.json          # ranked summary (JSON array)
            └── candidates/
                ├── rank_001_topology_0001.ckt  # HSpice netlist
                ├── rank_002_topology_0003.ckt
                └── ...

        ``synthesis_results.json`` contains a JSON array of objects, each with:

        * ``rank``          — 1-based ranking (1 = best)
        * ``id``            — topology id
        * ``name``          — topology name
        * ``score``         — engine score (lower is better)
        * ``gain_db``       — estimated gain [dB]
        * ``power_mw``      — estimated power [mW]
        * ``area_um2``      — estimated area [μm²]
        * ``transit_freq_mhz`` — estimated transit frequency [MHz]

        Each candidate's ``.ckt`` is rendered from its flat topology circuit
        via :class:`~ckt_io.hspice_writer.AcstNetlistWriter` (the same writer
        ``toplibgen`` uses) — a real, parseable netlist reflecting the
        candidate's structure, *not* a placeholder.

        .. note::
           The netlist is unsized (no ``W=``/``L=`` parameters): the
           candidate's flat circuit only carries device/net structure, and
           :meth:`~synthesis.engine.SynthesisEngine._size_topology` does not
           yet populate per-device sizing (it is a stub pending the real
           CP-SAT integration — a separate, larger item). Once that lands,
           this writer should switch to embedding the solved W/L values.

           If the topology library was loaded from a pre-built directory
           (:meth:`~synthesis.library.TopologyLibrary.from_directory` does
           not retain circuit objects, only metadata), no structural circuit
           is available for that candidate; its ``.ckt`` falls back to a
           comment-only placeholder noting why.

        Raises
        ------
        ValueError
            If ``args.output_dir`` is not set.
        RuntimeError
            If ``compute()`` has not been called.
        """
        output_dir = getattr(self.args, "output_dir", None)
        if not output_dir:
            raise ValueError(
                "SynthesisAnalysis.write(): --output-dir is required"
            )

        results = self._require_initialized(self.results, "results")
        engine = self._require_initialized(self.engine, "engine")
        library = self._require_initialized(self.library, "library")

        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        cand_dir = root / "candidates"
        cand_dir.mkdir(exist_ok=True)

        # -- JSON summary ---------------------------------------------------
        scores = engine._compute_scores(results)
        summary = []
        for rank, ((spec, sizing), score) in enumerate(
            zip(results, scores), start=1
        ):
            p = sizing.performance
            summary.append(
                {
                    "rank": rank,
                    "id": spec.id,
                    "name": spec.name,
                    "score": round(score, 6),
                    "solver_status": sizing.solver_status,
                    "gain_db": round(p.gain_db, 3),
                    "power_mw": round(p.power_mw, 4),
                    "area_um2": round(p.total_area_um2, 1),
                    "transit_freq_mhz": round(p.transit_freq_mhz, 3),
                    "slew_rate_v_us": round(p.slew_rate, 3),
                    "phase_margin_deg": round(p.phase_margin_deg, 2),
                }
            )

        json_path = root / "synthesis_results.json"
        json_path.write_text(json.dumps(summary, indent=2))
        _log.info("Wrote synthesis summary → %s", json_path)

        # -- Per-topology CKT netlists ---------------------------------------
        from sizing.writer import SizedCircuitWriter

        writer = AcstNetlistWriter()
        missing_circuits = 0
        for rank, (spec, sizing) in enumerate(results, start=1):
            ckt_name = f"rank_{rank:03d}_topology_{spec.id:04d}.ckt"
            ckt_path = cand_dir / ckt_name
            circuit = library.get_circuit(spec.id)
            if circuit is not None:
                writer.write(circuit, ckt_path, name=spec.name)
                if getattr(sizing, "devices", None):
                    # embed the solved W/L (acst's synthesis output is sized)
                    SizedCircuitWriter(sizing).write(ckt_path, ckt_path)
            else:
                missing_circuits += 1
                ckt_path.write_text(
                    f"** Rank {rank}: {spec.name}  (id={spec.id})\n"
                    f"** Structural circuit unavailable — the topology "
                    f"library was loaded from a pre-built directory, which\n"
                    f"** does not retain circuit objects (metadata only). "
                    f"Regenerate the library in-memory to get real netlists.\n"
                )

        if missing_circuits:
            _log.warning(
                "SynthesisAnalysis.write(): %d/%d candidate(s) had no "
                "structural circuit available (library loaded from a "
                "pre-built directory) — wrote placeholder netlists for them.",
                missing_circuits, len(results),
            )
        _log.info("Wrote %d candidate netlist(s) → %s", len(results), cand_dir)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_initialized(value, name: str):
        """Raise ``RuntimeError`` if *value* is ``None``."""
        if value is None:
            raise RuntimeError(
                f"SynthesisAnalysis: '{name}' is not initialized — "
                f"call initialize() before compute(), and compute() before write()."
            )
        return value
