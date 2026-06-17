"""Tests for TopologySpec and TopologyLibrary (Phase 1 — library.py).

Coverage areas
--------------
* ``TopologySpec`` dataclass construction, fields, serialisation
* ``TopologySpec.category()`` for all four category combinations
* ``TopologyLibrary.add()`` / ``size()`` / ``get_circuit()``
* ``TopologyLibrary.filter()`` — single criterion, multiple criteria, no match
* ``TopologyLibrary.ids()`` ordering
* ``TopologyLibrary.to_directory()`` — file layout and content
* ``TopologyLibrary.from_directory()`` — round-trip (spec fields preserved)
* Error paths: ``get_circuit`` with unknown id, ``from_directory`` with missing dir
* ``__len__`` / ``__repr__``
"""
import json
import pytest
from pathlib import Path

from pyckt.core.device import TechType
from pyckt.synthesis.library import TopologySpec, TopologyLibrary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_spec(
    id: int = 1,
    name: str = "test_topo",
    num_stages: int = 1,
    is_complementary: bool = False,
    is_fully_differential: bool = False,
    input_tech: TechType = TechType.N,
    has_cascode: dict | None = None,
) -> TopologySpec:
    return TopologySpec(
        id=id,
        name=name,
        num_stages=num_stages,
        is_complementary=is_complementary,
        is_fully_differential=is_fully_differential,
        input_tech=input_tech,
        has_cascode=has_cascode or {},
    )


@pytest.fixture
def empty_lib() -> TopologyLibrary:
    return TopologyLibrary()


@pytest.fixture
def populated_lib() -> TopologyLibrary:
    """Library with 4 topologies covering all category combinations."""
    lib = TopologyLibrary()
    lib.add(_make_spec(1, "one_single_nmos", 1, False, False, TechType.N))
    lib.add(_make_spec(2, "one_diff_pmos",   1, True,  True,  TechType.P))
    lib.add(_make_spec(3, "two_single_nmos", 2, False, False, TechType.N,
                       {"tc1": True, "load1": False}))
    lib.add(_make_spec(4, "two_diff_pmos",   2, True,  True,  TechType.P,
                       {"tc1": True, "load1": True}))
    return lib


# ---------------------------------------------------------------------------
# TopologySpec — construction & fields
# ---------------------------------------------------------------------------

class TestTopologySpec:
    def test_basic_fields(self):
        spec = _make_spec(id=7, name="foo", num_stages=2,
                          is_complementary=True, is_fully_differential=False,
                          input_tech=TechType.P)
        assert spec.id == 7
        assert spec.name == "foo"
        assert spec.num_stages == 2
        assert spec.is_complementary is True
        assert spec.is_fully_differential is False
        assert spec.input_tech == TechType.P

    def test_default_has_cascode_is_empty(self):
        spec = _make_spec()
        assert spec.has_cascode == {}

    def test_has_cascode_stored(self):
        spec = _make_spec(has_cascode={"tc1": True, "load1": False})
        assert spec.has_cascode == {"tc1": True, "load1": False}

    def test_repr_contains_name(self):
        spec = _make_spec(id=3, name="my_topo")
        assert "my_topo" in repr(spec)

    # ------------------------------------------------------------------
    # category()
    # ------------------------------------------------------------------

    def test_category_one_stage_single(self):
        spec = _make_spec(num_stages=1, is_fully_differential=False)
        assert spec.category() == "one_stage_single_output"

    def test_category_one_stage_diff(self):
        spec = _make_spec(num_stages=1, is_fully_differential=True)
        assert spec.category() == "one_stage_fully_differential"

    def test_category_two_stage_single(self):
        spec = _make_spec(num_stages=2, is_fully_differential=False)
        assert spec.category() == "two_stage_single_output"

    def test_category_two_stage_diff(self):
        spec = _make_spec(num_stages=2, is_fully_differential=True)
        assert spec.category() == "two_stage_fully_differential"

    # ------------------------------------------------------------------
    # Serialisation round-trip
    # ------------------------------------------------------------------

    def test_to_dict_keys(self):
        spec = _make_spec()
        d = spec.to_dict()
        for key in ("id", "name", "num_stages", "is_complementary",
                    "is_fully_differential", "input_tech", "has_cascode"):
            assert key in d

    def test_to_dict_input_tech_is_string(self):
        spec = _make_spec(input_tech=TechType.N)
        assert spec.to_dict()["input_tech"] == "n"

    def test_from_dict_round_trip(self):
        spec = _make_spec(id=5, name="rt", num_stages=2,
                          is_complementary=True, is_fully_differential=True,
                          input_tech=TechType.P,
                          has_cascode={"tc1": False})
        restored = TopologySpec.from_dict(spec.to_dict())
        assert restored.id == spec.id
        assert restored.name == spec.name
        assert restored.num_stages == spec.num_stages
        assert restored.is_complementary == spec.is_complementary
        assert restored.is_fully_differential == spec.is_fully_differential
        assert restored.input_tech == spec.input_tech
        assert restored.has_cascode == spec.has_cascode


# ---------------------------------------------------------------------------
# TopologyLibrary — mutation & query
# ---------------------------------------------------------------------------

class TestTopologyLibrary:
    def test_empty_library_size(self, empty_lib):
        assert empty_lib.size() == 0

    def test_add_increases_size(self, empty_lib):
        empty_lib.add(_make_spec(id=1))
        assert empty_lib.size() == 1

    def test_add_second_entry(self, empty_lib):
        empty_lib.add(_make_spec(id=1))
        empty_lib.add(_make_spec(id=2, name="b"))
        assert empty_lib.size() == 2

    def test_len_matches_size(self, populated_lib):
        assert len(populated_lib) == populated_lib.size()

    def test_add_overwrites_duplicate_id(self, empty_lib):
        empty_lib.add(_make_spec(id=1, name="first"))
        empty_lib.add(_make_spec(id=1, name="second"))
        assert empty_lib.size() == 1
        assert empty_lib.topologies[1].name == "second"

    def test_get_circuit_returns_none_when_none_added(self, empty_lib):
        empty_lib.add(_make_spec(id=1), circuit=None)
        assert empty_lib.get_circuit(1) is None

    def test_get_circuit_returns_stored_object(self, empty_lib):
        sentinel = object()
        empty_lib.add(_make_spec(id=1), circuit=sentinel)
        assert empty_lib.get_circuit(1) is sentinel

    def test_get_circuit_unknown_id_raises(self, empty_lib):
        with pytest.raises(KeyError):
            empty_lib.get_circuit(999)

    def test_ids_ascending(self, populated_lib):
        assert populated_lib.ids() == [1, 2, 3, 4]

    def test_repr_contains_size(self, populated_lib):
        assert "4" in repr(populated_lib)

    # ------------------------------------------------------------------
    # filter()
    # ------------------------------------------------------------------

    def test_filter_single_criterion(self, populated_lib):
        results = populated_lib.filter(num_stages=1)
        assert len(results) == 2
        assert all(s.num_stages == 1 for s in results)

    def test_filter_two_criteria(self, populated_lib):
        results = populated_lib.filter(num_stages=2, is_complementary=True)
        assert len(results) == 1
        assert results[0].id == 4

    def test_filter_no_match_returns_empty(self, populated_lib):
        results = populated_lib.filter(num_stages=3)
        assert results == []

    def test_filter_all_match(self, populated_lib):
        results = populated_lib.filter()
        assert len(results) == 4

    def test_filter_result_sorted_by_id(self, populated_lib):
        ids = [s.id for s in populated_lib.filter(num_stages=1)]
        assert ids == sorted(ids)

    def test_filter_by_fully_differential(self, populated_lib):
        results = populated_lib.filter(is_fully_differential=True)
        assert len(results) == 2
        assert all(s.is_fully_differential for s in results)


# ---------------------------------------------------------------------------
# TopologyLibrary — to_directory / from_directory
# ---------------------------------------------------------------------------

class TestTopologyLibraryIO:
    def test_to_directory_creates_ckt_files(self, populated_lib, tmp_path):
        populated_lib.to_directory(str(tmp_path))
        ckt_files = list(tmp_path.rglob("*.ckt"))
        assert len(ckt_files) == 4

    def test_to_directory_creates_json_files(self, populated_lib, tmp_path):
        populated_lib.to_directory(str(tmp_path))
        json_files = list(tmp_path.rglob("*.json"))
        assert len(json_files) == 4

    def test_to_directory_creates_category_subdirs(self, populated_lib, tmp_path):
        populated_lib.to_directory(str(tmp_path))
        subdirs = {p.name for p in tmp_path.iterdir() if p.is_dir()}
        expected = {
            "one_stage_single_output", "one_stage_fully_differential",
            "two_stage_single_output", "two_stage_fully_differential",
        }
        assert expected == subdirs

    def test_ckt_file_contains_macro(self, tmp_path):
        lib = TopologyLibrary()
        lib.add(_make_spec(id=1, name="my_ota"))
        lib.to_directory(str(tmp_path))
        ckt_files = list(tmp_path.rglob("*.ckt"))
        content = ckt_files[0].read_text()
        assert ".MACRO" in content
        assert ".EOM" in content

    def test_json_sidecar_is_valid(self, tmp_path):
        lib = TopologyLibrary()
        lib.add(_make_spec(id=1, name="test_ota"))
        lib.to_directory(str(tmp_path))
        json_files = list(tmp_path.rglob("*.json"))
        data = json.loads(json_files[0].read_text())
        assert data["id"] == 1
        assert data["name"] == "test_ota"

    def test_from_directory_round_trip_size(self, populated_lib, tmp_path):
        populated_lib.to_directory(str(tmp_path))
        loaded = TopologyLibrary.from_directory(str(tmp_path))
        assert loaded.size() == 4

    def test_from_directory_round_trip_fields(self, populated_lib, tmp_path):
        populated_lib.to_directory(str(tmp_path))
        loaded = TopologyLibrary.from_directory(str(tmp_path))
        for orig_id in populated_lib.ids():
            orig = populated_lib.topologies[orig_id]
            restored = loaded.topologies[orig_id]
            assert restored.name == orig.name
            assert restored.num_stages == orig.num_stages
            assert restored.is_complementary == orig.is_complementary
            assert restored.is_fully_differential == orig.is_fully_differential
            assert restored.input_tech == orig.input_tech
            assert restored.has_cascode == orig.has_cascode

    def test_from_directory_circuit_is_none(self, populated_lib, tmp_path):
        populated_lib.to_directory(str(tmp_path))
        loaded = TopologyLibrary.from_directory(str(tmp_path))
        for tid in loaded.ids():
            assert loaded.get_circuit(tid) is None

    def test_from_directory_missing_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            TopologyLibrary.from_directory(str(tmp_path / "nonexistent"))


# ---------------------------------------------------------------------------
# Phase 2 — TopologyConverter
# ---------------------------------------------------------------------------

class TestTopologyConverter:
    """Tests for TopologyConverter.convert() — topogen Circuit → core.Circuit."""

    @pytest.fixture(scope="class")
    def sample_opamp(self):
        """Return a single simple one-stage op-amp from the HL5 factory."""
        from topogen.HL5.opamps import createSimpleOneStageOpAmps
        return next(iter(createSimpleOneStageOpAmps()))

    @pytest.fixture(scope="class")
    def core_circuit(self, sample_opamp):
        from pyckt.synthesis.converter import TopologyConverter
        return TopologyConverter().convert(sample_opamp)

    def test_converter_imports(self):
        from pyckt.synthesis.converter import TopologyConverter
        assert TopologyConverter is not None

    def test_convert_returns_core_circuit(self, core_circuit):
        from pyckt.core.circuit import Circuit as CoreCircuit
        assert isinstance(core_circuit, CoreCircuit)

    def test_convert_has_mosfets(self, core_circuit):
        assert len(core_circuit.mosfets) > 0

    def test_convert_mosfet_count_positive(self, core_circuit):
        # a minimal op-amp has at least 4 transistors
        assert len(core_circuit.mosfets) >= 4

    def test_convert_all_devices_are_mosfets(self, core_circuit):
        from pyckt.core.device import DeviceType
        for device in core_circuit.devices:
            assert device.device_type == DeviceType.MOSFET

    def test_convert_tech_types_valid(self, core_circuit):
        from pyckt.core.device import TechType
        for device in core_circuit.mosfets:
            assert device.tech_type in (TechType.N, TechType.P)

    def test_convert_nets_created(self, core_circuit):
        assert len(core_circuit.nets) > 0

    def test_convert_terminals_created(self, core_circuit):
        assert len(core_circuit._terminals) > 0

    def test_convert_does_not_mutate_source(self, sample_opamp):
        from copy import deepcopy
        from pyckt.synthesis.converter import TopologyConverter
        original_instance_count = len(sample_opamp.instances)
        TopologyConverter().convert(sample_opamp)
        # source must still have the same hierarchical structure (not flattened)
        assert len(sample_opamp.instances) == original_instance_count

    def test_convert_device_names_sequential(self, core_circuit):
        names = [d.name for d in core_circuit.mosfets]
        for i, name in enumerate(names, start=1):
            assert name == f"M{i}"

    def test_convert_two_stage_opamp(self):
        from topogen.HL5.opamps import createSimpleTwoStageOpAmps
        from pyckt.synthesis.converter import TopologyConverter
        opamp = next(iter(createSimpleTwoStageOpAmps()))
        core_ckt = TopologyConverter().convert(opamp)
        # two-stage has more transistors than one-stage
        assert len(core_ckt.mosfets) >= 6

    def test_convert_empty_circuit_raises(self):
        from topogen.common.circuit import Circuit
        from pyckt.synthesis.converter import TopologyConverter
        empty = Circuit(name="empty", id=1, techtype="n")
        with pytest.raises(ValueError):
            TopologyConverter().convert(empty)

    def test_converter_re_exported_from_synthesis(self):
        from pyckt.synthesis import TopologyConverter
        assert TopologyConverter is not None


# ---------------------------------------------------------------------------
# Phase 2 — TopologyLibraryGenerator
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestTopologyLibraryGenerator:
    """Tests for TopologyLibraryGenerator.generate().

    Marked ``slow`` (Week 9 Phase 5) — every test in this class
    requires the ~18 s ``generate()`` pass over all HL2–HL5 factory
    combinations.  ``test_generate_idempotent`` is even slower (~40 s)
    because it generates twice.  Run with ``pytest -m slow`` to include.
    """

    @pytest.fixture(scope="class")
    def generated_lib(self, tmp_path_factory):
        """Generate the full library once and reuse across all tests in this class."""
        from pyckt.synthesis.generator import TopologyLibraryGenerator
        d = tmp_path_factory.mktemp("generated_lib")
        gen = TopologyLibraryGenerator(output_dir=str(d))
        return gen.generate(), d

    def test_generator_imports(self):
        from pyckt.synthesis.generator import TopologyLibraryGenerator
        assert TopologyLibraryGenerator is not None

    def test_generate_returns_topology_library(self, generated_lib):
        lib, _ = generated_lib
        assert isinstance(lib, TopologyLibrary)

    def test_generate_count_positive(self, generated_lib):
        lib, _ = generated_lib
        assert lib.size() > 100

    def test_generate_has_one_stage_topologies(self, generated_lib):
        lib, _ = generated_lib
        one_stage = lib.filter(num_stages=1)
        assert len(one_stage) > 0

    def test_generate_has_two_stage_topologies(self, generated_lib):
        lib, _ = generated_lib
        two_stage = lib.filter(num_stages=2)
        assert len(two_stage) > 0

    def test_generate_two_stage_count_greater_than_one_stage(self, generated_lib):
        lib, _ = generated_lib
        assert len(lib.filter(num_stages=2)) > len(lib.filter(num_stages=1))

    def test_generate_has_complementary_topologies(self, generated_lib):
        lib, _ = generated_lib
        assert len(lib.filter(is_complementary=True)) > 0

    def test_generate_has_fd_topologies(self, generated_lib):
        lib, _ = generated_lib
        assert len(lib.filter(is_fully_differential=True)) > 0

    def test_generate_has_nmos_input_topologies(self, generated_lib):
        lib, _ = generated_lib
        assert len(lib.filter(input_tech=TechType.N)) > 0

    def test_generate_has_pmos_input_topologies(self, generated_lib):
        lib, _ = generated_lib
        assert len(lib.filter(input_tech=TechType.P)) > 0

    def test_generate_ids_are_sequential(self, generated_lib):
        lib, _ = generated_lib
        ids = lib.ids()
        assert ids == list(range(1, lib.size() + 1))

    def test_generate_writes_to_disk(self, generated_lib):
        _, output_dir = generated_lib
        ckt_files = list(output_dir.rglob("*.ckt"))
        assert len(ckt_files) > 0

    def test_generate_written_count_matches_library(self, generated_lib):
        lib, output_dir = generated_lib
        ckt_files = list(output_dir.rglob("*.ckt"))
        assert len(ckt_files) == lib.size()

    def test_generate_idempotent(self, tmp_path):
        """Calling generate twice with different output dirs gives same count."""
        from pyckt.synthesis.generator import TopologyLibraryGenerator
        lib1 = TopologyLibraryGenerator(str(tmp_path / "a")).generate()
        lib2 = TopologyLibraryGenerator(str(tmp_path / "b")).generate()
        assert lib1.size() == lib2.size()

    def test_generator_re_exported_from_synthesis(self):
        from pyckt.synthesis import TopologyLibraryGenerator
        assert TopologyLibraryGenerator is not None

    def test_opamp_factory_create_one_stage(self):
        from topogen.HL5.opamps import OpAmpFactory
        one = OpAmpFactory().create_one_stage_opamps()
        assert len(one) > 0

    def test_opamp_factory_create_two_stage(self):
        from topogen.HL5.opamps import OpAmpFactory
        two = OpAmpFactory().create_two_stage_opamps()
        assert len(two) > 0


# ---------------------------------------------------------------------------
# TopologyLibraryGenerator — exception handlers around the converter
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestGeneratorConverterExceptionHandlers:
    """`TopologyLibraryGenerator.generate()` wraps every
    `TopologyConverter.convert(opamp)` call in `try/except` so a single
    broken topogen Circuit doesn't take down the whole library build.
    This test forces every conversion to raise and verifies the
    generator still populates the library with `circuit=None` entries."""

    @pytest.fixture
    def raising_converter_class(self):
        """Swap the module-level `TopologyConverter` for a stand-in
        whose `.convert()` always raises."""
        from pyckt.synthesis import converter as conv_mod

        class _RaisingConverter:
            def convert(self, _opamp):
                raise RuntimeError("simulated convert failure")

        original = conv_mod.TopologyConverter
        conv_mod.TopologyConverter = _RaisingConverter
        try:
            yield
        finally:
            conv_mod.TopologyConverter = original

    def test_convert_failures_dont_abort_generation(
        self, raising_converter_class, tmp_path
    ):
        from pyckt.synthesis.generator import TopologyLibraryGenerator
        from pyckt.synthesis import converter as conv_mod

        gen = TopologyLibraryGenerator(output_dir=None)
        # `__init__` already instantiated a converter — re-bind to the
        # swapped class so the exception path actually fires.
        gen._converter = conv_mod.TopologyConverter()

        library = gen.generate()

        # Library is fully populated regardless of convert failures, and
        # every entry's circuit is None (the exception branch ran).
        assert library.size() > 100
        none_count = sum(
            1 for tid in library.ids() if library.get_circuit(tid) is None
        )
        assert none_count == library.size(), (
            f"expected all circuits to be None; got {none_count}/{library.size()}"
        )

