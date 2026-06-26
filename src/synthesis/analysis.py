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
   summary file plus one ``.ckt`` HSpice netlist stub per topology.

C++ ref: ``Synthesis::Synthesis::initialize / compute / write``
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

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
        self.library: TopologyLibrary | None = None
        self.engine: SynthesisEngine | None = None
        self.results: list[tuple[TopologySpec, object]] = []

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
                ├── rank_001_topology_0001.ckt  # HSpice netlist stub
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
                    "gain_db": p.gain_db,
                    "power_mw": p.power_mw,
                    "area_um2": p.total_area_um2,
                    "transit_freq_mhz": p.transit_freq_mhz,
                }
            )

        json_path = root / "synthesis_results.json"
        json_path.write_text(json.dumps(summary, indent=2))
        _log.info("Wrote synthesis summary → %s", json_path)

        # -- Per-topology CKT stubs -----------------------------------------
        for rank, ((spec, sizing), score) in enumerate(
            zip(results, scores), start=1
        ):
            ckt_name = f"rank_{rank:03d}_topology_{spec.id:04d}.ckt"
            ckt_path = cand_dir / ckt_name
            ckt_path.write_text(
                f"** Rank {rank}: {spec.name}  (id={spec.id})\n"
                f"** Score: {score:.6f}\n"
                f".MACRO {spec.name} ibias in1 in2 out sourceNmos sourcePmos\n"
                f"** (stub — Phase 3)\n"
                f".EOM {spec.name}\n"
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
