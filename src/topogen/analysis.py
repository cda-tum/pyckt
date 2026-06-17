"""Topology library generation analysis pipeline.

:class:`TopLibGenAnalysis` is the top-level orchestrator dispatched by
``--analysis toplibgen``.  It wraps
:class:`~pyckt.synthesis.generator.TopologyLibraryGenerator` in the
standard ``initialize → compute → write`` lifecycle of
:class:`~pyckt.core.common.AbstractAnalysis`.

Pipeline
--------
1. **initialize()** — validate ``--output-dir`` and instantiate the
   generator with on-disk writes deferred (the generator runs in
   in-memory mode and disk persistence happens in ``write()``).
2. **compute()** — call
   :meth:`~pyckt.synthesis.generator.TopologyLibraryGenerator.generate`
   to enumerate every valid op-amp topology.  Populates ``self.library``.
3. **write()** — flush ``self.library`` to ``args.output_dir`` via
   :meth:`~pyckt.synthesis.library.TopologyLibrary.to_directory`.

C++ ref: ``Synthesis::TopologyLibraryGeneration::initialize / compute / write``
"""

from __future__ import annotations

import logging
from pathlib import Path

from pyckt.core.common import AbstractAnalysis
from pyckt.synthesis.library import TopologyLibrary

_log = logging.getLogger(__name__)


class TopLibGenAnalysis(AbstractAnalysis):
    """Topology library generation — dispatched by ``--analysis toplibgen``.

    Parameters
    ----------
    args:
        Parsed CLI namespace.  Required attribute:

        * ``output_dir`` — directory where the generated ``.ckt``/``.json``
          pairs are written (one per topology, grouped into
          ``one_stage_*`` / ``two_stage_*`` sub-directories).
    """

    def __init__(self, args) -> None:
        super().__init__(args)
        self.output_dir: str | None = None
        self.generator = None
        self.library: TopologyLibrary | None = None

    # ------------------------------------------------------------------
    # Phase 1 — initialize
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Validate ``--output-dir`` and prepare the generator.

        Raises
        ------
        ValueError
            If ``args.output_dir`` is missing or empty.
        """
        output_dir = getattr(self.args, "output_dir", None)
        if not output_dir:
            raise ValueError(
                "TopLibGenAnalysis.initialize(): --output-dir is required"
            )
        self.output_dir = output_dir

        # Build the generator with output_dir=None so on-disk writes happen
        # during write(), not compute() — preserving the standard
        # initialize/compute/write separation that AbstractAnalysis expects.
        from pyckt.synthesis.generator import TopologyLibraryGenerator
        self.generator = TopologyLibraryGenerator(output_dir=None)
        _log.debug("TopLibGenAnalysis initialized: output_dir=%s", output_dir)

    # ------------------------------------------------------------------
    # Phase 2 — compute
    # ------------------------------------------------------------------

    def compute(self) -> None:
        """Enumerate every valid op-amp topology in memory.

        Raises
        ------
        RuntimeError
            If ``initialize()`` has not been called.
        """
        generator = self._require_initialized(self.generator, "generator")
        self.library = generator.generate()
        _log.info(
            "TopLibGenAnalysis.compute(): generated %d topologies",
            self.library.size(),
        )

    # ------------------------------------------------------------------
    # Phase 3 — write
    # ------------------------------------------------------------------

    def write(self) -> None:
        """Write the library to ``args.output_dir``.

        The layout depends on ``args.output_format`` (default ``"native"``).

        ``native`` — pyckt's ``.ckt`` stub + ``.json`` metadata per topology::

            output_dir/
            ├── one_stage_single_output/
            │   ├── topology_0001.ckt
            │   ├── topology_0001.json
            │   └── ...
            ├── one_stage_fully_differential/
            ├── two_stage_single_output/
            └── two_stage_fully_differential/

        ``acst`` — one ACST-format ``.ckt`` netlist per topology, grouped into
        ACST's three category directories (no ``.json`` sidecars)::

            output_dir/
            ├── SingleOutputOpAmps/
            ├── FullyDifferentialOpAmps/
            └── ComplementaryOpAmps/

        Raises
        ------
        RuntimeError
            If ``compute()`` has not been called.
        """
        library = self._require_initialized(self.library, "library")
        output_dir = self._require_initialized(self.output_dir, "output_dir")

        output_format = getattr(self.args, "output_format", "native")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        if output_format == "acst":
            counts = library.to_acst_directory(output_dir)
            _log.info(
                "Wrote %d topologies (acst format) → %s  %s",
                library.size(), output_dir, counts,
            )
        else:
            library.to_directory(output_dir)
            _log.info("Wrote %d topologies → %s", library.size(), output_dir)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_initialized(value, name: str):
        """Raise ``RuntimeError`` if *value* is ``None``."""
        if value is None:
            raise RuntimeError(
                f"TopLibGenAnalysis: '{name}' is not initialized — "
                f"call initialize() before compute(), and compute() before write()."
            )
        return value
