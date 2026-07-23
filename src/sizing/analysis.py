"""Automatic sizing analysis pipeline.

Wires the full automatic sizing flow end-to-end:
input parsing, structure recognition, partitioning, rule generation,
problem assembly, CP-SAT solving, and result-output serialisation.
"""

from __future__ import annotations

import logging
from pathlib import Path

_log = logging.getLogger(__name__)

from core.common import AbstractAnalysis

from .problem import SizingProblem
from .solver import SizingSolver
from .writer import AcstSizingXMLWriter, SizedCircuitWriter, SizingXMLWriter


class AutomaticSizingAnalysis(AbstractAnalysis):
    """Automatic sizing — dispatched by ``--analysis automaticsizing``."""

    def __init__(self, args) -> None:
        super().__init__(args)
        self.circuit = None
        self.circuit_info = None
        self.library = None
        self.structure_circuits = None
        self.partition = None
        self.rules = []
        self.problem = None
        self.solver = None
        self.result = None

    def initialize(self) -> None:
        from ckt_io import (
            HSpiceMapping,
            HSpiceParser,
            SupplyNetConfig,
            load_circuit_information,
            load_device_types,
        )
        from partitioning.partitioner import Partitioner
        from recognition.library import Library
        from recognition.recognizer import RuleGenerator, StructureRecognizer

        mapping = HSpiceMapping.from_file(self._require_arg("hspice_mapping_file"))
        supply_nets = SupplyNetConfig.from_file(
            self._require_arg("hspice_supplynet_file")
        )
        device_types = load_device_types(self._require_arg("device_types_file"))

        parser = HSpiceParser(mapping, supply_nets, device_types)
        self.circuit = parser.parse(self._require_arg("circuit_netlist"))

        self.circuit_info = load_circuit_information(
            self._require_arg("xml_circuit_information_file"),
            self._require_arg("xml_technologie_file"),
        )

        # Optional: --library may be omitted to fall back to the bundled
        # data/structrec/ XMLs.  Aligns with structrec / rulegen /
        # partitioning analyses (Phase 4) which all default to None.
        library_path = getattr(self.args, "xml_structrec_library_file", None)
        self.library = Library.from_directory(
            self._resolve_structrec_library_dir(library_path)
            if library_path
            else None
        )
        self.structure_circuits = StructureRecognizer(self.library).recognize(
            self.circuit
        )
        self.partition = Partitioner(self.circuit_info.parameters).partition(
            self.structure_circuits
        )
        self.rules = RuleGenerator().generate(self.structure_circuits)

    def compute(self) -> None:
        self.problem = SizingProblem.build(
            self._require_initialized(self.circuit, "circuit"),
            self._require_initialized(self.partition, "partition"),
            self.rules,
            self._require_initialized(self.circuit_info, "circuit_info"),
        )
        self.solver = SizingSolver(self.problem)
        # Wire the --timeout (runtime) through to the CP-SAT solver so the
        # balanced multi-objective search is time-bounded (it returns the best
        # feasible design found within the budget).
        runtime = getattr(self.args, "runtime", None)
        if runtime:
            self.solver.timeout_seconds = float(runtime)
        self.result = self.solver.solve()

        if not self.result.devices:
            _log.warning(
                "Sizing solver returned no solution (status=%s). "
                "Check constraints and bounds — the problem may be infeasible "
                "or the timeout was reached before a feasible point was found.",
                self.result.solver_status,
            )

    def write(self) -> None:
        result = self._require_initialized(self.result, "result")
        output_path = Path(self._require_arg("output_file"))
        fmt = getattr(self.args, "output_format", "native")
        writer = (
            AcstSizingXMLWriter(result) if fmt == "acst"
            else SizingXMLWriter(result)
        )
        writer.write(output_path)

        sized_netlist = output_path.with_suffix(".sized.hspice")
        SizedCircuitWriter(result).write(
            self._require_arg("circuit_netlist"),
            sized_netlist,
        )

    def _require_arg(self, name: str) -> str:
        value = getattr(self.args, name, None)
        if not value:
            raise ValueError(f"Missing required argument --{name.replace('_', '-')}")
        return value

    @staticmethod
    def _require_initialized(value, name: str):
        if value is None:
            raise RuntimeError(
                f"AutomaticSizingAnalysis expected initialized {name}"
            )
        return value

    @staticmethod
    def _resolve_structrec_library_dir(path_str: str) -> Path:
        # Library.from_directory accepts a directory or a wrapper-file path
        # (issue #47), so pass the argument through unchanged.
        return Path(path_str)
