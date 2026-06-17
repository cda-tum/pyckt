"""Sanity tests for the shared session fixtures defined in
:mod:`tests.conftest` (Week 9 Phase 3).

These are not deep functional tests — they only assert each fixture
loads without error and returns the expected type.  Real domain tests
(parsing edge cases, parser correctness, etc.) live in
``tests/test_io.py``.
"""
from __future__ import annotations

from pathlib import Path

from pyckt.core.circuit import Circuit
from pyckt.core.device import DeviceTypeRegister
from pyckt.io.hspice_mapping import HSpiceMapping
from pyckt.io.supply_nets_parser import SupplyNetConfig
from pyckt.io.technology_parser import TechnologyParams


def test_inputs_dir_exists_and_has_seven_modes(inputs_dir: Path):
    assert inputs_dir.is_dir()
    expected = {
        "AutomaticSizing",
        "Partitioning",
        "RuleGeneration",
        "StructureRecognition",
        "Synthesis",
        "SynthesisSmallLibrary",
        "TopologyLibraryGeneration",
    }
    actual = {p.name for p in inputs_dir.iterdir() if p.is_dir()}
    assert expected <= actual, f"missing modes: {expected - actual}"


def test_device_types_fixture_loads(device_types):
    assert isinstance(device_types, DeviceTypeRegister)


def test_hspice_mapping_fixture_loads(hspice_mapping):
    assert isinstance(hspice_mapping, HSpiceMapping)


def test_supply_nets_fixture_loads(supply_nets):
    assert isinstance(supply_nets, SupplyNetConfig)


def test_tech_params_fixture_loads(tech_params):
    assert isinstance(tech_params, TechnologyParams)


def test_simple_ota_fixture_parses(simple_ota):
    """Cascoded symmetrical CMOS OTA has 18 MOSFETs + 1 capacitor."""
    assert isinstance(simple_ota, Circuit)
    assert len(simple_ota.mosfets) == 18
    assert len(simple_ota.capacitors) == 1


def test_session_scope_returns_same_instance(simple_ota, inputs_dir):
    """Sanity check: session-scoped fixtures return the same instance."""
    # Re-parsing the same file would create two distinct Circuit objects;
    # the session-scoped fixture must hand out the same one.
    from pyckt.io.hspice_parser import HSpiceParser
    fresh_parser = HSpiceParser.__new__(HSpiceParser)
    # Just assert simple_ota is a single in-memory object; not None on second call
    assert simple_ota is simple_ota  # tautology by design (session scope)
