"""Shared pytest fixtures for the pyckt test suite (Week 9 Phase 3).

This conftest exposes session-scoped fixtures so individual tests don't
have to re-parse the same XCAT/XML files.  All fixtures source their
input from the bundled ``tests/data/inputs/`` tree (Phase 3 copied a
minimum subset of ``acst/InputFileExamples/`` into the repo so the suite
is self-contained — no hard-coded host paths).

Layout
------

::

    tests/
    ├── conftest.py                ← this file
    └── data/
        ├── …                      ← legacy per-test fixtures (Week 4+)
        └── inputs/
            ├── AutomaticSizing/
            ├── Partitioning/
            ├── RuleGeneration/
            ├── StructureRecognition/
            ├── Synthesis/
            ├── SynthesisSmallLibrary/
            └── TopologyLibraryGeneration/

Fixtures
--------

* :func:`inputs_dir`     — root path for per-mode test inputs
* :func:`device_types`   — :class:`~core.DeviceTypeRegister`
* :func:`hspice_mapping` — :class:`~ckt_io.hspice_mapping.HSpiceMapping`
* :func:`supply_nets`    — :class:`~ckt_io.supply_nets_parser.SupplyNetConfig`
* :func:`tech_params`    — :class:`~ckt_io.technology_parser.TechnologyParams`
* :func:`simple_ota`     — fully-parsed :class:`~core.Circuit` for
  the cascoded symmetrical CMOS OTA (the canonical test op-amp)

All fixtures are session-scoped: they are constructed once per ``pytest``
invocation and shared by every test that requests them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants — also importable directly:
#   from tests.conftest import INPUTS_DIR
# ---------------------------------------------------------------------------

TESTS_DIR: Path = Path(__file__).resolve().parent
"""Absolute path to the ``tests/`` directory."""

DATA_DIR: Path = TESTS_DIR / "data"
"""Absolute path to ``tests/data/`` (legacy + new fixtures live here)."""

INPUTS_DIR: Path = DATA_DIR / "inputs"
"""Root of the per-mode input bundles copied from ``acst/InputFileExamples/``."""

# AutomaticSizing supplies the canonical OTA + the most complete set of
# co-located config files (deviceTypes / mapping / supply / tech / spec),
# so it's the single source for shared session fixtures.
_AUTO_SIZING: Path = INPUTS_DIR / "AutomaticSizing"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def inputs_dir() -> Path:
    """Root directory of per-mode bundled test inputs.

    Tests should resolve mode-specific paths under this fixture rather than
    hard-coding ``Path(__file__).parent / "data" / "inputs" / "Foo"`` —
    that way the suite stays portable if the layout moves.
    """
    return INPUTS_DIR


@pytest.fixture(scope="session")
def device_types():
    """Shared :class:`~core.DeviceTypeRegister` for all tests."""
    from ckt_io.device_types_parser import load_device_types
    return load_device_types(_AUTO_SIZING / "deviceTypes.xcat")


@pytest.fixture(scope="session")
def hspice_mapping():
    """Shared :class:`~ckt_io.hspice_mapping.HSpiceMapping` for all tests."""
    from ckt_io.hspice_mapping import HSpiceMapping
    return HSpiceMapping.from_file(_AUTO_SIZING / "HSpiceMapping.xcat")


@pytest.fixture(scope="session")
def supply_nets():
    """Shared :class:`~ckt_io.supply_nets_parser.SupplyNetConfig` for all tests."""
    from ckt_io.supply_nets_parser import SupplyNetConfig
    return SupplyNetConfig.from_file(_AUTO_SIZING / "supplyNets.xcat")


@pytest.fixture(scope="session")
def tech_params():
    """Shared :class:`~ckt_io.technology_parser.TechnologyParams` for sizing tests."""
    from ckt_io.technology_parser import TechnologyParams
    return TechnologyParams.from_file(_AUTO_SIZING / "TechnologyFile.xml")


@pytest.fixture(scope="session")
def simple_ota(hspice_mapping, supply_nets, device_types):
    """Parsed cascoded symmetrical CMOS OTA — the canonical test op-amp.

    Returns a fully-wired :class:`~core.Circuit` ready to feed into
    structure recognition, partitioning, sizing, or any other downstream
    pipeline test.
    """
    from ckt_io.hspice_parser import HSpiceParser
    parser = HSpiceParser(hspice_mapping, supply_nets, device_types)
    return parser.parse(_AUTO_SIZING / "cascodedSymmetricalCMOSOTA.hspice")
