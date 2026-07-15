"""Partitioning analysis pipeline.

Provides :class:`PartitioningAnalysis`, the `AbstractAnalysis` orchestrator
dispatched by ``--analysis partitioning``.

Pipeline
--------
1. **initialize()** — load IO config (mapping / supply / device-types),
   parse the input HSpice netlist, run structure recognition, and parse
   the circuit-information XML for partitioner pin assignments.
2. **compute()** — run :class:`~partitioning.partitioner.Partitioner` on
   the structure overlay; store the resulting :class:`PartitionResult`.
3. **write()** — serialise the partition via
   :class:`~partitioning.writer.PartitionXMLWriter`.

C++ ref: ``Partitioning::Partitioning::initialize / compute / write``
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.common import AbstractAnalysis

_log = logging.getLogger(__name__)


class PartitioningAnalysis(AbstractAnalysis):
    """Partitioning — dispatched by ``--analysis partitioning``.

    Required args (snake_case attributes on the namespace):
        * ``circuit_netlist`` — input ``.hspice`` file
        * ``device_types_file`` — ``deviceTypes.xcat``
        * ``hspice_mapping_file`` — ``HSpiceMapping.xcat``
        * ``hspice_supplynet_file`` — ``supplyNets.xcat``
        * ``output_file`` — output partition XML path

    Optional args:
        * ``xml_circuit_information_file`` —
          ``CircuitParameterAndSpecifications.xml``; when omitted the
          input/output/bias net roles are inferred from the circuit
          structure (:mod:`partitioning.net_inference`), as acst does.
        * ``xml_structrec_library_file`` — directory or
          ``AnalogLibrary.xml`` file. Defaults to the bundled XMLs.
    """

    def __init__(self, args) -> None:
        super().__init__(args)
        self.circuit = None
        self.structure_circuits = None
        self.circuit_params = None
        self.partition = None

    # ------------------------------------------------------------------
    # Phase 1 — initialize
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        from ckt_io.circuit_info_parser import parse_circuit_parameters
        from ckt_io.device_types_parser import load_device_types
        from ckt_io.hspice_mapping import HSpiceMapping
        from ckt_io.hspice_parser import HSpiceParser
        from ckt_io.supply_nets_parser import SupplyNetConfig
        from recognition.library import Library
        from recognition.recognizer import StructureRecognizer

        circuit_netlist = self._require_arg("circuit_netlist")
        device_types = load_device_types(self._require_arg("device_types_file"))
        mapping = HSpiceMapping.from_file(self._require_arg("hspice_mapping_file"))
        supply_nets = SupplyNetConfig.from_file(
            self._require_arg("hspice_supplynet_file")
        )

        parser = HSpiceParser(mapping, supply_nets, device_types)
        self.circuit = parser.parse(circuit_netlist)
        _log.debug("Parsed %s: %d MOSFETs", circuit_netlist, len(self.circuit.mosfets))

        library_path = getattr(self.args, "xml_structrec_library_file", None)
        library = Library.from_directory(self._resolve_lib_dir(library_path))
        self.structure_circuits = StructureRecognizer(library).recognize(self.circuit)
        _log.debug(
            "Recognised %d structures", self.structure_circuits.total_structures
        )

        # Optional override: with no --circuit-params, infer the net roles
        # from the circuit structure, as acst's partitioner does (its
        # ``Partitioning::compute`` takes only the recognition result).
        params_file = getattr(self.args, "xml_circuit_information_file", None)
        if params_file:
            self.circuit_params = parse_circuit_parameters(params_file)
        else:
            from partitioning.net_inference import infer_circuit_parameters

            self.circuit_params = infer_circuit_parameters(self.circuit)

    # ------------------------------------------------------------------
    # Phase 2 — compute
    # ------------------------------------------------------------------

    def compute(self) -> None:
        from partitioning.partitioner import Partitioner

        sc = self._require_initialised(self.structure_circuits, "structure_circuits")
        params = self._require_initialised(self.circuit_params, "circuit_params")

        self.partition = Partitioner(params).partition(sc)
        _log.info("Partitioning done: %s", self.partition.summary())

    # ------------------------------------------------------------------
    # Phase 3 — write
    # ------------------------------------------------------------------

    def write(self) -> None:
        output_file = self._require_arg("output_file")
        fmt = getattr(self.args, "output_format", "native")

        if fmt == "acst":
            # acst format uses the acst-faithful gm-path/Part partitioner
            # (built on the recognition hierarchy), not pyckt's native result.
            from partitioning.acst_partitioner import AcstPartitioner
            from partitioning.writer import AcstPartitionXMLWriter

            sc = self._require_initialised(
                self.structure_circuits, "structure_circuits")
            params = self._require_initialised(self.circuit_params, "circuit_params")
            acst_result = AcstPartitioner(params).partition(sc)
            AcstPartitionXMLWriter(acst_result).write(output_file)
        else:
            from partitioning.writer import PartitionXMLWriter

            partition = self._require_initialised(self.partition, "partition")
            PartitionXMLWriter(partition).write(output_file)
        _log.info("Wrote partition XML (%s format) → %s", fmt, output_file)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require_arg(self, name: str) -> str:
        value = getattr(self.args, name, None)
        if not value:
            raise ValueError(
                f"Missing required argument --{name.replace('_', '-')}"
            )
        return value

    @staticmethod
    def _require_initialised(value, name: str):
        if value is None:
            raise RuntimeError(
                f"PartitioningAnalysis: '{name}' is not initialised — "
                f"call initialize() before compute(), and compute() before write()."
            )
        return value

    @staticmethod
    def _resolve_lib_dir(path_str: str | None) -> Path | None:
        # Library.from_directory accepts a directory or a wrapper-file path
        # (issue #47), so pass the argument through unchanged.
        return Path(path_str) if path_str is not None else None
