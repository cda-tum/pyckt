"""Recognition analysis pipelines.

Provides the two `AbstractAnalysis` orchestrators dispatched by the CLI:

* :class:`StructRecAnalysis` (``--analysis structrec``) — parses a netlist
  and runs the structure-recognition engine, producing an XML overlay.
* :class:`RuleGenAnalysis` (``--analysis rulegen``) — same parse + recognise
  pipeline, then derives sizing rules from the structure overlay and writes
  them as a sizing-rules XML file.

Both wire to the existing engines in
:mod:`recognition.recognizer` / :mod:`recognition.rulegen` /
:mod:`recognition.writer` (Week 4).
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.common import AbstractAnalysis

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Common parse + recognise helper
# ---------------------------------------------------------------------------

def _parse_and_recognise(args):
    """Shared `initialize`-time work for both recognition analyses.

    Returns ``(circuit, structure_circuits)`` ready for the subclass-specific
    `compute()` to consume.
    """
    from ckt_io.device_types_parser import load_device_types
    from ckt_io.hspice_mapping import HSpiceMapping
    from ckt_io.hspice_parser import HSpiceParser
    from ckt_io.supply_nets_parser import SupplyNetConfig
    from recognition.library import Library
    from recognition.recognizer import StructureRecognizer

    circuit_netlist = _require_arg(args, "circuit_netlist")
    device_types = load_device_types(_require_arg(args, "device_types_file"))
    mapping = HSpiceMapping.from_file(_require_arg(args, "hspice_mapping_file"))
    supply_nets = SupplyNetConfig.from_file(_require_arg(args, "hspice_supplynet_file"))

    parser = HSpiceParser(mapping, supply_nets, device_types)
    circuit = parser.parse(circuit_netlist)
    _log.debug("Parsed %s: %d MOSFETs", circuit_netlist, len(circuit.mosfets))

    library_path = getattr(args, "xml_structrec_library_file", None)
    library = Library.from_directory(_resolve_lib_dir(library_path))

    structure_circuits = StructureRecognizer(library).recognize(circuit)
    _log.info(
        "Recognised %d structures across %d levels",
        structure_circuits.total_structures,
        len(structure_circuits.hierarchy_levels),
    )
    return circuit, structure_circuits


def _require_arg(args, name: str) -> str:
    value = getattr(args, name, None)
    if not value:
        raise ValueError(
            f"Missing required argument --{name.replace('_', '-')}"
        )
    return value


def _resolve_lib_dir(path_str: str | None) -> Path | None:
    """Pass the ``--library`` argument through to ``Library.from_directory``.

    The loader itself accepts a directory *or* a wrapper-file path (issue
    #47 — acst's ``Library.xml`` form), and ``None`` falls back to the
    bundled XMLs, so no resolution is needed here.
    """
    return Path(path_str) if path_str is not None else None


# ---------------------------------------------------------------------------
# StructRecAnalysis
# ---------------------------------------------------------------------------

class StructRecAnalysis(AbstractAnalysis):
    """Structure recognition — dispatched by ``--analysis structrec``.

    Lifecycle
    ---------
    * ``initialize()`` — load IO config, parse the circuit, run the
      `StructureRecognizer` and store the resulting `StructureCircuits`.
    * ``compute()`` — no-op (recognition is done in `initialize`; kept for
      `AbstractAnalysis` contract symmetry).
    * ``write()`` — serialise the structure overlay via `StructRecXMLWriter`.

    Required args (snake_case attributes on the namespace):
        * ``circuit_netlist`` — path to the input ``.hspice`` file
        * ``device_types_file`` — ``deviceTypes.xcat``
        * ``hspice_mapping_file`` — ``HSpiceMapping.xcat``
        * ``hspice_supplynet_file`` — ``supplyNets.xcat``
        * ``output_file`` — path for the output XML

    Optional args:
        * ``xml_structrec_library_file`` — directory or
          ``AnalogLibrary.xml`` file. Defaults to the bundled XMLs.
    """

    def __init__(self, args) -> None:
        super().__init__(args)
        self.circuit = None
        self.structure_circuits = None

    def initialize(self) -> None:
        self.circuit, self.structure_circuits = _parse_and_recognise(self.args)

    def compute(self) -> None:
        if self.structure_circuits is None:
            raise RuntimeError(
                "StructRecAnalysis: 'structure_circuits' is not initialised — "
                "call initialize() before compute()."
            )
        # Recognition itself runs in initialize(); compute() is a no-op so the
        # standard initialize→compute→write contract still holds.

    def write(self) -> None:
        if self.structure_circuits is None:
            raise RuntimeError(
                "StructRecAnalysis: 'structure_circuits' is not initialised — "
                "call initialize() before write()."
            )
        from recognition.writer import (
            AcstStructRecXMLWriter,
            StructRecXMLWriter,
        )

        output_file = _require_arg(self.args, "output_file")
        fmt = getattr(self.args, "output_format", "native")
        writer = (
            AcstStructRecXMLWriter() if fmt == "acst" else StructRecXMLWriter()
        )
        writer.write(self.structure_circuits, output_file)
        _log.info("Wrote recognition XML (%s format) → %s", fmt, output_file)


# ---------------------------------------------------------------------------
# RuleGenAnalysis
# ---------------------------------------------------------------------------

class RuleGenAnalysis(AbstractAnalysis):
    """Rule generation — dispatched by ``--analysis rulegen``.

    Lifecycle
    ---------
    * ``initialize()`` — same parse + recognise as `StructRecAnalysis`.
    * ``compute()`` — runs `RuleGenerator.generate()` over the structure
      overlay; stores the resulting list of `SizingRule`.
    * ``write()`` — serialise rules via `RuleXMLWriter`.

    Args: same as `StructRecAnalysis`. The output XML schema is different
    (rules, not structures).
    """

    def __init__(self, args) -> None:
        super().__init__(args)
        self.circuit = None
        self.structure_circuits = None
        self.rules: list = []

    def initialize(self) -> None:
        self.circuit, self.structure_circuits = _parse_and_recognise(self.args)

    def compute(self) -> None:
        if self.structure_circuits is None:
            raise RuntimeError(
                "RuleGenAnalysis: 'structure_circuits' is not initialised — "
                "call initialize() before compute()."
            )
        from recognition.rulegen import RuleGenerator

        self.rules = RuleGenerator().generate(self.structure_circuits)
        _log.info("Generated %d sizing rules", len(self.rules))

    def write(self) -> None:
        if not self.rules and self.structure_circuits is None:
            raise RuntimeError(
                "RuleGenAnalysis: nothing to write — call compute() first."
            )
        output_file = _require_arg(self.args, "output_file")
        fmt = getattr(self.args, "output_format", "native")

        if fmt == "acst":
            # acst's rulegen learns a recognition library (pairLibrary of new
            # composite structures), not sizing rules.
            from recognition.rule_learning import RuleLearner
            from recognition.writer import AcstPairLibraryWriter

            base = getattr(self.args, "structure_name", None) or "LearnedStructure"
            library = RuleLearner(base).learn(self.structure_circuits)
            AcstPairLibraryWriter().write(library, output_file)
            _log.info("Wrote learned pairLibrary (%d items) → %s",
                      len(library.items), output_file)
        else:
            from recognition.writer import RuleXMLWriter

            RuleXMLWriter().write(self.rules, output_file)
            _log.info("Wrote %d rules → %s", len(self.rules), output_file)
