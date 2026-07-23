"""Tests for `partitioning.net_inference` (issue #6).

Verifies the structural net-role inference on the bundled ``Partitioning``
fixture — the bundle that ships *no*
``CircuitParameterAndSpecifications.xml``, which previously forced
``scripts/run_partitioning.sh`` to borrow one from another fixture.
"""
from __future__ import annotations

import pytest

from partitioning.net_inference import infer_circuit_parameters


@pytest.fixture(scope="module")
def partitioning_circuit(inputs_dir):
    from ckt_io.device_types_parser import load_device_types
    from ckt_io.hspice_mapping import HSpiceMapping
    from ckt_io.hspice_parser import HSpiceParser
    from ckt_io.supply_nets_parser import SupplyNetConfig

    src = inputs_dir / "Partitioning"
    parser = HSpiceParser(
        HSpiceMapping.from_file(str(src / "HSpiceMapping.xcat")),
        SupplyNetConfig.from_file(str(src / "supplyNets.xcat")),
        load_device_types(str(src / "deviceTypes.xcat")),
    )
    return parser.parse(str(src / "cascodedSymmetricalCMOSOTA.hspice"))


class TestNetInference:
    def test_inputs_are_the_undriven_diff_pair_gates(self, partitioning_circuit):
        params = infer_circuit_parameters(partitioning_circuit)
        assert {params.input_plus[0], params.input_minus[0]} == {"inp", "inn"}

    def test_output_is_the_all_drain_net(self, partitioning_circuit):
        params = infer_circuit_parameters(partitioning_circuit)
        assert params.output_net == "out"

    def test_bias_is_the_externally_fed_diode_net(self, partitioning_circuit):
        params = infer_circuit_parameters(partitioning_circuit)
        assert params.bias_current[0] == "ibias"

    def test_rails_come_from_supply_flags(self, partitioning_circuit):
        params = infer_circuit_parameters(partitioning_circuit)
        assert params.supply_voltage[0] == "vdd!"
        assert params.ground[0] == "gnd!"

    def test_partitioners_accept_inferred_params(self, partitioning_circuit):
        """Both partitioners run to completion on inferred roles."""
        from partitioning.acst_partitioner import AcstPartitioner
        from partitioning.partitioner import Partitioner
        from recognition.library import Library
        from recognition.recognizer import StructureRecognizer

        sc = StructureRecognizer(Library.from_directory(None)).recognize(
            partitioning_circuit
        )
        params = infer_circuit_parameters(partitioning_circuit)

        native = Partitioner(params).partition(sc)
        assert native.total > 0

        acst = AcstPartitioner(params).partition(sc)
        assert acst is not None
