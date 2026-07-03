"""pyckt CLI — subcommand-style dispatcher (Week 9 Phase 4).

Each subcommand corresponds to one analysis mode and maps to a class in
:data:`ANALYSIS_REGISTRY`.  `cli.run(argv)` is the in-process entry
point used by integration tests; `main()` wraps it for the
``pyckt`` console script.

Usage
-----

::

    pyckt structrec --circuit circuit.hspice \\
                    --device-types deviceTypes.xcat \\
                    --mapping HSpiceMapping.xcat \\
                    --supply-nets supplyNets.xcat \\
                    --output result.xml

    pyckt automaticsizing --circuit circuit.hspice ... --output-dir results/

In-process call (used by Phase 5 integration tests)::

    from cli import run
    result = run(["structrec", "--circuit", "...", ...])
    assert result.returncode == 0
    sc = result.data.structure_circuits   # the StructureCircuits overlay
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import namedtuple

from utils.loguru_loader import setup_logger

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ANALYSIS_REGISTRY: dict[str, tuple[str, str]] = {
    "structrec":       ("recognition.analysis",     "StructRecAnalysis"),
    "rulegen":         ("recognition.analysis",     "RuleGenAnalysis"),
    "partitioning":    ("partitioning.analysis",    "PartitioningAnalysis"),
    "automaticsizing": ("sizing.analysis",    "AutomaticSizingAnalysis"),
    "synthesis":       ("synthesis.analysis", "SynthesisAnalysis"),
    "toplibgen":       ("topogen.analysis",         "TopLibGenAnalysis"),
}
"""Maps subcommand name → (module, class).  Single source of truth for
both the parser and dispatcher."""


# ---------------------------------------------------------------------------
# Result wrapper
# ---------------------------------------------------------------------------

Result = namedtuple("Result", ["returncode", "data"])
"""In-process return value of `cli.run(argv)`.

* ``returncode`` — 0 on success, non-zero on failure (mirrors process exit code).
* ``data`` — the executed `AbstractAnalysis` instance on success (so callers
  can read mode-specific result attributes like ``.structure_circuits``,
  ``.rules``, ``.partition``, ``.result``, ``.results``, ``.library``).
  ``None`` on failure.
"""


# ---------------------------------------------------------------------------
# Parser construction
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with one subparser per analysis mode."""
    p = argparse.ArgumentParser(
        prog="pyckt",
        description="pyckt — Analog Circuit Synthesis Tool (Python)",
    )
    p.add_argument(
        "--log-level-console",
        choices=["DEBUG", "TRACE", "OFF"],
        default="DEBUG",
        help="Logger verbosity (default: DEBUG).",
    )

    sub = p.add_subparsers(
        dest="command",
        required=True,
        metavar="MODE",
        help="Analysis mode (one of: %s)" % ", ".join(ANALYSIS_REGISTRY),
    )

    _build_structrec(sub)
    _build_rulegen(sub)
    _build_partitioning(sub)
    _build_automaticsizing(sub)
    _build_synthesis(sub)
    _build_toplibgen(sub)
    return p


# ---------------------------------------------------------------------------
# Per-mode subparser builders
# ---------------------------------------------------------------------------

def _add_io_args(sp: argparse.ArgumentParser) -> None:
    """Required IO args shared by every recognition-derived subcommand."""
    sp.add_argument("--circuit", dest="circuit_netlist", required=True,
                    help="Path to the input HSpice netlist (.hspice)")
    sp.add_argument("--device-types", dest="device_types_file", required=True,
                    help="Path to deviceTypes.xcat")
    sp.add_argument("--mapping", dest="hspice_mapping_file", required=True,
                    help="Path to HSpiceMapping.xcat")
    sp.add_argument("--supply-nets", dest="hspice_supplynet_file", required=True,
                    help="Path to supplyNets.xcat")


def _add_library_arg(sp: argparse.ArgumentParser) -> None:
    """Optional structrec library directory (defaults to bundled XMLs)."""
    sp.add_argument("--library", dest="xml_structrec_library_file", default=None,
                    help="Structrec library directory or AnalogLibrary.xml "
                         "(default: bundled XMLs)")


def _add_output_format_arg(sp: argparse.ArgumentParser) -> None:
    """Output-schema selector shared by modes with an acst-compatible writer."""
    sp.add_argument("--output-format", dest="output_format",
                    choices=["native", "acst"], default="native",
                    help="Output XML schema: pyckt 'native' (default) or "
                         "C++-compatible 'acst'")


def _build_structrec(sub) -> None:
    sp = sub.add_parser("structrec", help="Structure recognition")
    _add_io_args(sp)
    _add_library_arg(sp)
    sp.add_argument("--output", dest="output_file", required=True,
                    help="Output XML path for the recognised structure overlay")
    _add_output_format_arg(sp)


def _build_rulegen(sub) -> None:
    sp = sub.add_parser("rulegen", help="Sizing rule generation")
    _add_io_args(sp)
    _add_library_arg(sp)
    sp.add_argument("--output", dest="output_file", required=True,
                    help="Output XML path for the generated sizing rules")
    sp.add_argument("--structure-name", dest="structure_name",
                    default="LearnedStructure",
                    help="Base name for learned composite structures "
                         "(acst output format only)")
    _add_output_format_arg(sp)


def _build_partitioning(sub) -> None:
    sp = sub.add_parser("partitioning", help="Circuit partitioning")
    _add_io_args(sp)
    _add_library_arg(sp)
    sp.add_argument("--circuit-params", dest="xml_circuit_information_file",
                    required=False, default=None,
                    help="Path to CircuitParameterAndSpecifications.xml "
                         "(optional override; when omitted, the input/output/"
                         "bias net roles are inferred from the circuit "
                         "structure, as acst does)")
    sp.add_argument("--output", dest="output_file", required=True,
                    help="Output XML path for the partition")
    _add_output_format_arg(sp)


def _build_automaticsizing(sub) -> None:
    sp = sub.add_parser("automaticsizing", help="Automatic transistor sizing")
    _add_io_args(sp)
    _add_library_arg(sp)
    sp.add_argument("--tech-file", dest="xml_technologie_file", required=True,
                    help="Path to TechnologyFile.xml")
    sp.add_argument("--circuit-params", dest="xml_circuit_information_file",
                    required=True,
                    help="Path to CircuitParameterAndSpecifications.xml")
    sp.add_argument("--output", dest="output_file", required=True,
                    help="Output XML path for the sizing result")
    sp.add_argument("--timeout", dest="runtime", type=float, default=30.0,
                    help="Solver timeout in seconds (default: 30). The balanced "
                         "multi-objective converges in a few seconds; the solver "
                         "uses the remaining budget to refine the trade-off.")
    sp.add_argument("--transistor-model", choices=["SHM", "EKV"], default="SHM",
                    help="Transistor model (default: SHM)")
    sp.add_argument("--scaling", choices=["0.1mum", "1mum"], default="1mum",
                    help="Geometric scaling unit (default: 1mum)")
    _add_output_format_arg(sp)


def _build_synthesis(sub) -> None:
    sp = sub.add_parser("synthesis", help="Topology synthesis")
    sp.add_argument("--device-types", dest="device_types_file", required=True,
                    help="Path to deviceTypes.xcat")
    sp.add_argument("--mapping", dest="hspice_mapping_file", default=None,
                    help="Path to HSpiceMapping.xcat (optional)")
    sp.add_argument("--supply-nets", dest="hspice_supplynet_file", default=None,
                    help="Path to supplyNets.xcat (optional)")
    sp.add_argument("--tech-file", dest="xml_tech_file", required=True,
                    help="Path to TechnologieFile.xml")
    sp.add_argument("--spec", dest="xml_spec_file", required=True,
                    help="Path to CircuitSpecifications.xml")
    sp.add_argument("--library-dir", dest="library_dir", default=None,
                    help="Pre-built topology library directory; if absent, "
                         "a fresh library is generated in memory")
    sp.add_argument("--output-dir", dest="output_dir", required=True,
                    help="Directory for ranked synthesis output")


def _build_toplibgen(sub) -> None:
    sp = sub.add_parser("toplibgen", help="Topology library generation")
    sp.add_argument("--output-dir", dest="output_dir", required=True,
                    help="Directory where the generated topology library "
                         "will be written (native: one .ckt+.json per "
                         "topology; acst: one .ckt per topology under "
                         "SingleOutputOpAmps/FullyDifferentialOpAmps/"
                         "ComplementaryOpAmps)")
    _add_output_format_arg(sp)
    # toplibgen also accepts the shared IO args for parser-fixture parity but
    # they are not required because the Python generator works from scratch.
    sp.add_argument("--device-types", dest="device_types_file", default=None,
                    help="Path to deviceTypes.xcat (unused; accepted for "
                         "compatibility with the C++ ACST flag set)")


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def run(argv: list[str] | None = None) -> Result:
    """In-process CLI entry point — the unit-testable counterpart to ``main``.

    Parses *argv* (or `sys.argv[1:]` when `None`), constructs the
    appropriate `AbstractAnalysis`, drives its three-phase lifecycle,
    and returns a :class:`Result`.

    On any exception during initialize/compute/write the analysis logs
    the error and returns ``Result(returncode=1, data=None)`` instead
    of propagating — this matches the spec's `result.returncode` /
    `result.data` shape that integration tests rely on.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logger(args.log_level_console)

    log = logging.getLogger(__name__)
    module_path, class_name = ANALYSIS_REGISTRY[args.command]
    module = __import__(module_path, fromlist=[class_name])
    analysis_class = getattr(module, class_name)
    analysis = analysis_class(args)

    start = time.time()
    try:
        analysis.initialize()
        analysis.compute()
        analysis.write()
    except Exception as exc:  # noqa: BLE001 — catch-all is intentional at the
        # CLI boundary so callers get a Result instead of a traceback.
        log.error("pyckt %s failed: %s", args.command, exc, exc_info=True)
        return Result(returncode=1, data=None)

    elapsed = time.time() - start
    h, rem = divmod(int(elapsed), 3600)
    m, s = divmod(rem, 60)
    print(f"Program runtime: {h}h {m}min {s}s")
    return Result(returncode=0, data=analysis)


def main() -> None:
    """Console-script entry point (``pyckt …``).  Wraps :func:`run`."""
    sys.exit(run().returncode)


if __name__ == "__main__":
    main()
