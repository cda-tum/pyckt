"""Public Python API for pyckt.

Every analysis mode that the :mod:`cli` command-line interface exposes is
also available here as a plain, typed function — no ``argv`` list, no subprocess,
no generic ``Result`` wrapper.  Each function takes file paths (``str`` or
:class:`~pathlib.Path`) plus keyword options, drives the underlying
``AbstractAnalysis`` lifecycle (``initialize → compute → write``), and returns
the mode's typed result object directly:

==============================  ==================================  ===========================================
Function                        Wraps                               Returns
==============================  ==================================  ===========================================
:func:`recognize`               ``StructRecAnalysis``               :class:`~recognition.model.StructureCircuits`
:func:`generate_rules`          ``RuleGenAnalysis``                 ``list`` of ``SizingRule``
:func:`partition`               ``PartitioningAnalysis``            :class:`~partitioning.result.PartitionResult`
:func:`size`                    ``AutomaticSizingAnalysis``         :class:`~sizing.result.SizingResult`
:func:`synthesize`              ``SynthesisAnalysis``               ``list`` of ``(TopologySpec, SizingResult)``
:func:`generate_topology_library`  ``TopLibGenAnalysis``            :class:`~synthesis.library.TopologyLibrary`
==============================  ==================================  ===========================================

Writing output to disk is **optional**: pass ``output=...`` (or ``output_dir=...``)
to also serialise the result, or omit it to get the in-memory object only.

Examples
--------
Recognise structures and inspect them in memory::

    from pyckt import recognize

    structures = recognize(
        circuit="circuit.hspice",
        device_types="deviceTypes.xcat",
        mapping="HSpiceMapping.xcat",
        supply_nets="supplyNets.xcat",
    )
    print(structures.total_structures)

Size a circuit and write both the XML and sized netlist::

    from pyckt import size

    result = size(
        circuit="circuit.hspice",
        device_types="deviceTypes.xcat",
        mapping="HSpiceMapping.xcat",
        supply_nets="supplyNets.xcat",
        tech_file="TechnologyFile.xml",
        circuit_params="CircuitParameterAndSpecifications.xml",
        timeout=60,
        output="sized.xml",          # also writes sized.sized.hspice
    )
    print(result.performance.gain_db)

Generate the whole topology library in memory::

    from pyckt import generate_topology_library

    library = generate_topology_library()
    print(library.size())
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # import only for type checkers — avoids heavy runtime imports
    from partitioning.result import PartitionResult
    from recognition.model import StructureCircuits
    from sizing.result import SizingResult
    from synthesis.library import TopologyLibrary, TopologySpec

__all__ = [
    "recognize",
    "generate_rules",
    "partition",
    "size",
    "synthesize",
    "generate_topology_library",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _path(value: str | Path | None) -> str | None:
    """Normalise an optional path argument to ``str`` (or ``None``)."""
    return None if value is None else str(value)


def _run(analysis_cls: type, namespace: argparse.Namespace, *, write: bool) -> Any:
    """Drive one analysis through ``initialize → compute → [write]``.

    Returns the executed analysis instance so each public function can read
    the mode-specific result attribute off it.
    """
    analysis = analysis_cls(namespace)
    analysis.initialize()
    analysis.compute()
    if write:
        analysis.write()
    return analysis


# ---------------------------------------------------------------------------
# Recognition modes
# ---------------------------------------------------------------------------

def recognize(
    circuit: str | Path,
    device_types: str | Path,
    mapping: str | Path,
    supply_nets: str | Path,
    *,
    library: str | Path | None = None,
    output: str | Path | None = None,
    output_format: str = "native",
) -> StructureCircuits:
    """Recognise the analog structures in a flat transistor netlist.

    Parses *circuit* and runs the structure-recognition engine, returning the
    hierarchical :class:`~recognition.model.StructureCircuits` overlay
    (current mirrors, differential pairs, cascodes, …).

    Parameters
    ----------
    circuit, device_types, mapping, supply_nets:
        Paths to the input netlist and its three parsing-config files
        (``deviceTypes.xcat`` / ``HSpiceMapping.xcat`` / ``supplyNets.xcat``).
    library:
        Recognition-library directory or ``AnalogLibrary.xml`` file.  Defaults
        to pyckt's bundled pattern library.
    output:
        Optional XML output path.  When given, the overlay is also written;
        omit it to get the in-memory object only.
    output_format:
        ``"native"`` (pyckt schema) or ``"acst"`` (C++-compatible schema).
        Only affects the written file, not the returned object.

    Returns
    -------
    StructureCircuits
        The recognised structure overlay.
    """
    from recognition.analysis import StructRecAnalysis

    ns = argparse.Namespace(
        circuit_netlist=_path(circuit),
        device_types_file=_path(device_types),
        hspice_mapping_file=_path(mapping),
        hspice_supplynet_file=_path(supply_nets),
        xml_structrec_library_file=_path(library),
        output_file=_path(output),
        output_format=output_format,
    )
    return _run(StructRecAnalysis, ns, write=output is not None).structure_circuits


def generate_rules(
    circuit: str | Path,
    device_types: str | Path,
    mapping: str | Path,
    supply_nets: str | Path,
    *,
    library: str | Path | None = None,
    structure_name: str = "LearnedStructure",
    output: str | Path | None = None,
    output_format: str = "native",
) -> list:
    """Generate sizing rules from the recognised structure overlay.

    Runs the same parse + recognise pipeline as :func:`recognize`, then derives
    the native sizing-rule list (matched pairs, equal-W/L, equal-length).

    Parameters
    ----------
    circuit, device_types, mapping, supply_nets, library:
        As for :func:`recognize`.
    structure_name:
        Base name for the learned composite structures — used only when
        ``output_format="acst"`` (which writes a learned ``pairLibrary`` instead
        of the native rules).
    output:
        Optional XML output path.
    output_format:
        ``"native"`` writes the sizing-rule list; ``"acst"`` writes a learned
        recognition ``pairLibrary``.  The **returned** value is always the
        native sizing-rule list regardless of format.

    Returns
    -------
    list
        The generated ``SizingRule`` objects.
    """
    from recognition.analysis import RuleGenAnalysis

    ns = argparse.Namespace(
        circuit_netlist=_path(circuit),
        device_types_file=_path(device_types),
        hspice_mapping_file=_path(mapping),
        hspice_supplynet_file=_path(supply_nets),
        xml_structrec_library_file=_path(library),
        structure_name=structure_name,
        output_file=_path(output),
        output_format=output_format,
    )
    return _run(RuleGenAnalysis, ns, write=output is not None).rules


# ---------------------------------------------------------------------------
# Partitioning
# ---------------------------------------------------------------------------

def partition(
    circuit: str | Path,
    device_types: str | Path,
    mapping: str | Path,
    supply_nets: str | Path,
    circuit_params: str | Path,
    *,
    library: str | Path | None = None,
    output: str | Path | None = None,
    output_format: str = "native",
) -> PartitionResult:
    """Classify recognised structures into op-amp functional sections.

    Parses *circuit*, recognises its structures, then assigns each to a
    functional role (transconductance / load / bias / capacitance) using the
    input/output/bias/supply pins from *circuit_params*.

    Parameters
    ----------
    circuit, device_types, mapping, supply_nets, library:
        As for :func:`recognize`.
    circuit_params:
        Path to ``CircuitParameterAndSpecifications.xml`` (provides the
        input/output/bias/supply net assignments the partitioner needs).
    output:
        Optional XML output path.
    output_format:
        ``"native"`` or ``"acst"``.  The returned object is the native
        :class:`~partitioning.result.PartitionResult` regardless of format.

    Returns
    -------
    PartitionResult
        The structure → (role, stage) assignment.
    """
    from partitioning.analysis import PartitioningAnalysis

    ns = argparse.Namespace(
        circuit_netlist=_path(circuit),
        device_types_file=_path(device_types),
        hspice_mapping_file=_path(mapping),
        hspice_supplynet_file=_path(supply_nets),
        xml_circuit_information_file=_path(circuit_params),
        xml_structrec_library_file=_path(library),
        output_file=_path(output),
        output_format=output_format,
    )
    return _run(PartitioningAnalysis, ns, write=output is not None).partition


# ---------------------------------------------------------------------------
# Automatic sizing
# ---------------------------------------------------------------------------

def size(
    circuit: str | Path,
    device_types: str | Path,
    mapping: str | Path,
    supply_nets: str | Path,
    tech_file: str | Path,
    circuit_params: str | Path,
    *,
    library: str | Path | None = None,
    timeout: float = 30.0,
    output: str | Path | None = None,
    output_format: str = "native",
) -> SizingResult:
    """Size every transistor in the circuit with the CP-SAT solver.

    Runs the full pipeline (parse → recognise → partition → rulegen → assemble →
    solve) and returns the solved :class:`~sizing.result.SizingResult`
    (per-device W/L/current/operating-point plus an estimated performance
    summary).

    Parameters
    ----------
    circuit, device_types, mapping, supply_nets, library:
        As for :func:`recognize`.
    tech_file:
        Path to ``TechnologyFile.xml``.
    circuit_params:
        Path to ``CircuitParameterAndSpecifications.xml`` (specs + pins).
    timeout:
        Solver budget in seconds (default 30).  The solver returns the best
        feasible design found within the budget.
    output:
        Optional XML output path.  When given, a sized HSpice netlist is also
        written alongside it as ``<output>.sized.hspice``.
    output_format:
        ``"native"`` or ``"acst"`` for the written XML schema.

    Returns
    -------
    SizingResult
        The solved sizing plus expected-performance summary.
    """
    from sizing.analysis import AutomaticSizingAnalysis

    ns = argparse.Namespace(
        circuit_netlist=_path(circuit),
        device_types_file=_path(device_types),
        hspice_mapping_file=_path(mapping),
        hspice_supplynet_file=_path(supply_nets),
        xml_technologie_file=_path(tech_file),
        xml_circuit_information_file=_path(circuit_params),
        xml_structrec_library_file=_path(library),
        runtime=timeout,
        output_file=_path(output),
        output_format=output_format,
    )
    return _run(AutomaticSizingAnalysis, ns, write=output is not None).result


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def synthesize(
    spec: str | Path,
    tech_file: str | Path,
    *,
    device_types: str | Path | None = None,
    mapping: str | Path | None = None,
    supply_nets: str | Path | None = None,
    library_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> list[tuple[TopologySpec, Any]]:
    """Synthesise and rank op-amp topologies against a specification.

    Loads (or generates) a topology library, structurally filters it by the
    specification's complementary / fully-differential flags, sizes each
    surviving candidate, and returns them ranked best-first.

    Parameters
    ----------
    spec:
        Path to ``CircuitSpecifications.xml`` (target gain / power / area / …).
    tech_file:
        Path to ``TechnologieFile.xml``.
    device_types, mapping, supply_nets:
        Optional parsing-config paths (accepted for CLI parity).
    library_dir:
        Pre-built topology-library directory.  When omitted, a fresh library is
        generated in memory.
    output_dir:
        Optional directory for the ranked output (JSON summary + per-candidate
        ``.ckt`` stubs).  Omit to get the in-memory ranking only.

    Returns
    -------
    list[tuple[TopologySpec, SizingResult]]
        Ranked ``(topology, sizing)`` pairs, best first.
    """
    from synthesis.analysis import SynthesisAnalysis

    ns = argparse.Namespace(
        xml_spec_file=_path(spec),
        xml_tech_file=_path(tech_file),
        device_types_file=_path(device_types),
        hspice_mapping_file=_path(mapping),
        hspice_supplynet_file=_path(supply_nets),
        library_dir=_path(library_dir),
        output_dir=_path(output_dir),
    )
    return _run(SynthesisAnalysis, ns, write=output_dir is not None).results


# ---------------------------------------------------------------------------
# Topology library generation
# ---------------------------------------------------------------------------

def generate_topology_library(
    output_dir: str | Path | None = None,
    *,
    output_format: str = "native",
) -> TopologyLibrary:
    """Enumerate every valid op-amp topology.

    Runs the full HL2–HL5 factory sweep and returns the populated
    :class:`~synthesis.library.TopologyLibrary`.

    Parameters
    ----------
    output_dir:
        Optional directory to write the library to.  When omitted, the library
        is generated in memory only (nothing is written to disk).
    output_format:
        ``"native"`` writes one ``.ckt`` stub + ``.json`` per topology;
        ``"acst"`` writes one ACST-format ``.ckt`` netlist per topology under
        ``SingleOutputOpAmps`` / ``FullyDifferentialOpAmps`` /
        ``ComplementaryOpAmps``.  Ignored when *output_dir* is ``None``.

    Returns
    -------
    TopologyLibrary
        The fully-populated topology library.
    """
    # In-memory only: call the generator directly (the analysis wrapper requires
    # an --output-dir for its initialize() step).
    if output_dir is None:
        from synthesis.generator import TopologyLibraryGenerator

        return TopologyLibraryGenerator(output_dir=None).generate()

    from topogen.analysis import TopLibGenAnalysis

    ns = argparse.Namespace(
        output_dir=_path(output_dir),
        output_format=output_format,
        device_types_file=None,
    )
    return _run(TopLibGenAnalysis, ns, write=True).library
