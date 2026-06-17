"""End-to-end CLI integration tests (Week 9 Phase 5).

One ``Test{Mode}CLI`` class per CLI subcommand, each driving the full
``cli.run([...])`` pipeline against the bundled per-mode fixtures from
``tests/data/inputs/``.

Discipline
----------

* In-process invocation via :func:`pyckt.cli.run` — no subprocess.
* Tests are *integration* tests: they assert end-to-end behaviour
  (exit code, output file present, one or two domain invariants).
  Unit-level coverage of each analysis class lives next door in
  ``test_<mode>_analysis.py``.
* Slow tests (≥ 30 s) are marked ``@pytest.mark.slow`` so the default
  ``pytest`` invocation can skip them with ``-m "not slow"``.

Note: the existing ``tests/test_integration.py`` is the Week 4
structrec → rulegen pipeline test that calls the engines directly
(no CLI); it is kept as-is.  This file is the CLI-driven counterpart.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pyckt.cli import run


# ═══════════════════════════════════════════════════════════════════════
# Shared session-scoped library fixture (used by toplibgen + synthesis)
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def generated_library_dir(tmp_path_factory) -> Path:
    """Run ``pyckt toplibgen`` once and reuse its output as a synthesis
    library directory for downstream tests.

    Module scope so the ~18 s `TopologyLibraryGenerator.generate()` cost
    is amortised across both `TestTopLibGenCLI` and `TestSynthesisCLI`.
    """
    out_dir = tmp_path_factory.mktemp("toplibgen_for_phase5")
    result = run([
        "--log-level-console", "OFF",
        "toplibgen", "--output-dir", str(out_dir),
    ])
    assert result.returncode == 0, "toplibgen fixture-build failed"
    return out_dir


# ═══════════════════════════════════════════════════════════════════════
# 1. structrec
# ═══════════════════════════════════════════════════════════════════════

class TestStructrecCLI:
    """`pyckt structrec` end-to-end: parse → recognise → write XML."""

    @pytest.fixture
    def out_xml(self, tmp_path):
        return tmp_path / "structrec.xml"

    @pytest.fixture
    def cli_args(self, inputs_dir, out_xml):
        src = inputs_dir / "Partitioning"  # has the cascoded OTA + IO files
        return [
            "--log-level-console", "OFF",
            "structrec",
            "--circuit", str(src / "cascodedSymmetricalCMOSOTA.hspice"),
            "--device-types", str(src / "deviceTypes.xcat"),
            "--mapping", str(src / "HSpiceMapping.xcat"),
            "--supply-nets", str(src / "supplyNets.xcat"),
            "--output", str(out_xml),
        ]

    def test_returncode_zero(self, cli_args):
        result = run(cli_args)
        assert result.returncode == 0, "structrec exited non-zero"

    def test_writes_output_xml(self, cli_args, out_xml):
        run(cli_args)
        assert out_xml.exists()

    def test_output_xml_root_tag(self, cli_args, out_xml):
        run(cli_args)
        root = ET.parse(out_xml).getroot()
        assert root.tag == "StructureRecognitionResult"

    def test_recognised_at_least_six_top_level_structures(self, cli_args, out_xml):
        run(cli_args)
        root = ET.parse(out_xml).getroot()
        assert len(root.findall("Structure")) >= 6

    def test_recognises_diff_pair_and_current_mirror(self, cli_args):
        result = run(cli_args)
        all_names = {s.name for s in result.data.structure_circuits.all_structures}
        assert any("DifferentialPair" in n for n in all_names), \
            f"no differential pair in {all_names}"
        assert any("CurrentMirror" in n for n in all_names), \
            f"no current mirror in {all_names}"


# ═══════════════════════════════════════════════════════════════════════
# 2. rulegen
# ═══════════════════════════════════════════════════════════════════════

class TestRulegenCLI:
    """`pyckt rulegen` end-to-end: recognise → generate rules → write XML."""

    @pytest.fixture
    def out_xml(self, tmp_path):
        return tmp_path / "rules.xml"

    @pytest.fixture
    def cli_args(self, inputs_dir, out_xml):
        src = inputs_dir / "Partitioning"
        return [
            "--log-level-console", "OFF",
            "rulegen",
            "--circuit", str(src / "cascodedSymmetricalCMOSOTA.hspice"),
            "--device-types", str(src / "deviceTypes.xcat"),
            "--mapping", str(src / "HSpiceMapping.xcat"),
            "--supply-nets", str(src / "supplyNets.xcat"),
            "--output", str(out_xml),
        ]

    def test_returncode_zero(self, cli_args):
        assert run(cli_args).returncode == 0

    def test_writes_rules_xml(self, cli_args, out_xml):
        run(cli_args)
        assert out_xml.exists()
        root = ET.parse(out_xml).getroot()
        assert root.tag == "SizingRules"

    def test_at_least_eight_rules_emitted(self, cli_args, out_xml):
        run(cli_args)
        root = ET.parse(out_xml).getroot()
        assert len(root.findall("Rule")) >= 8


# ═══════════════════════════════════════════════════════════════════════
# 3. partitioning
# ═══════════════════════════════════════════════════════════════════════

class TestPartitioningCLI:
    """`pyckt partitioning` end-to-end: recognise → partition → write XML."""

    @pytest.fixture
    def out_xml(self, tmp_path):
        return tmp_path / "partition.xml"

    @pytest.fixture
    def cli_args(self, inputs_dir, out_xml):
        # AutomaticSizing/ ships the only CircuitParameter-bearing XML in
        # the bundle (Partitioning/'s XML is a recognition reference).
        src = inputs_dir / "AutomaticSizing"
        return [
            "--log-level-console", "OFF",
            "partitioning",
            "--circuit", str(src / "cascodedSymmetricalCMOSOTA.hspice"),
            "--device-types", str(src / "deviceTypes.xcat"),
            "--mapping", str(src / "HSpiceMapping.xcat"),
            "--supply-nets", str(src / "supplyNets.xcat"),
            "--circuit-params", str(src / "CircuitParameterAndSpecifications.xml"),
            "--output", str(out_xml),
        ]

    def test_returncode_zero(self, cli_args):
        assert run(cli_args).returncode == 0

    def test_writes_partition_xml(self, cli_args, out_xml):
        run(cli_args)
        assert out_xml.exists()

    def test_partition_classifies_transconductance_and_load(self, cli_args):
        result = run(cli_args)
        partition = result.data.partition
        # The cascoded symmetrical OTA must have at least one transconductance
        # and one load part for the classifier to be working at all.
        assert len(partition.transconductance_parts()) >= 1, \
            "no transconductance parts classified"
        assert len(partition.load_parts()) >= 1, \
            "no load parts classified"


# ═══════════════════════════════════════════════════════════════════════
# 4. automaticsizing  (slow — invokes CP-SAT solver)
# ═══════════════════════════════════════════════════════════════════════

class TestAutomaticSizingCLI:
    """`pyckt automaticsizing` end-to-end: full sizing pipeline.

    Two pre-existing solver-side bugs were fixed during Phase 5:

    1. **Variable-times-variable misrouting** — `constraints.py:318`
       used `add_raw_constraint(target == var(a)*var(b))` which CP-SAT
       rejects.  Fixed by adding `CPSATAdapter.add_multiplication` and
       rerouting the 6 buggy call sites.
    2. **Strict-equality divisibility infeasibility** — the SHM
       `Id*L = (μCox/2)·W·Vov²` equation was encoded as
       `id_l*1e6 == w_vov2*k_num` (k_num=84650 NMOS, 17870 PMOS), which
       forced `id_l` to be a multiple of 1693 (NMOS) / 1787 (PMOS).
       Combined with KCL ties between NMOS and PMOS branches, the LCM
       (~3 mA) made realistic OTA specs spuriously infeasible.  Fixed by
       relaxing all three SHM equations (CurrentEquation,
       TransconductanceEquation, OutputConductanceEquation) to a ±1%
       tolerance band — well below the SHM model's own ~10% accuracy.

    Solver wall time on the cascoded OTA is sub-second; the class is
    not marked ``slow``.
    """

    @pytest.fixture
    def out_xml(self, tmp_path):
        return tmp_path / "sizing.xml"

    @pytest.fixture
    def cli_args(self, inputs_dir, out_xml):
        src = inputs_dir / "AutomaticSizing"
        return [
            "--log-level-console", "OFF",
            "automaticsizing",
            "--circuit", str(src / "cascodedSymmetricalCMOSOTA.hspice"),
            "--device-types", str(src / "deviceTypes.xcat"),
            "--mapping", str(src / "HSpiceMapping.xcat"),
            "--supply-nets", str(src / "supplyNets.xcat"),
            "--tech-file", str(src / "TechnologyFile.xml"),
            "--circuit-params", str(src / "CircuitParameterAndSpecifications.xml"),
            "--output", str(out_xml),
            # The balanced multi-objective converges within ~3 s; the solver
            # otherwise burns the whole budget trying to prove optimality, so
            # keep the CI bound short.
            "--timeout", "4",
        ]

    def test_returncode_zero(self, cli_args):
        assert run(cli_args).returncode == 0

    def test_writes_sizing_xml(self, cli_args, out_xml):
        run(cli_args)
        assert out_xml.exists()

    def test_solver_returned_a_result(self, cli_args):
        result = run(cli_args)
        sizing_result = result.data.result
        assert sizing_result is not None
        assert sizing_result.solver_status in ("optimal", "feasible"), \
            f"solver should find a sizing; got {sizing_result.solver_status}"
        assert len(sizing_result.devices) > 0, "no devices sized"

    def test_constraint_satisfied_gain_meets_spec(self, cli_args):
        """§8d: gain is constrained on the output-node path (gm_in / gds_out),
        so the post-solve performance gain must meet the 80 dB spec."""
        result = run(cli_args)
        analysis = result.data
        gain_db = analysis.result.performance.gain_db
        assert gain_db >= 80.0, f"gain {gain_db:.1f} dB < spec 80 dB"

    def test_first_stage_tail_current_meets_slew_rate(self, cli_args):
        """§8d: the slew current is the input-pair *tail* (Σ first-stage
        transconductance currents), which must be ≥ SR·CL = 3.5 V/μs · 20 pF
        = 70 μA — and the reported slew rate must meet the spec."""
        from partitioning.result import StageType

        result = run(cli_args)
        analysis = result.data
        tc = analysis.partition.transconductance_parts(StageType.FIRST)
        assert tc, "partition didn't classify a first-stage transconductance"
        tail = sum(
            analysis.result.devices[d.name].current
            for s in tc for d in s.devices
            if d.name in analysis.result.devices
        )
        assert tail >= 70_000, f"tail I = {tail} nA < 70_000 nA (SR spec)"
        assert analysis.result.performance.slew_rate >= 3.5


# ═══════════════════════════════════════════════════════════════════════
# 5. synthesis  (slow — depends on the toplibgen module fixture)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestSynthesisCLI:
    """`pyckt synthesis` end-to-end against a pre-built library directory.

    Marked slow primarily because the `generated_library_dir` fixture
    invokes `pyckt toplibgen` (~18 s) once per module session.
    """

    @pytest.fixture
    def out_dir(self, tmp_path):
        d = tmp_path / "synth_out"
        d.mkdir()
        return d

    @pytest.fixture
    def cli_args(self, inputs_dir, generated_library_dir, out_dir):
        src = inputs_dir / "Synthesis"
        return [
            "--log-level-console", "OFF",
            "synthesis",
            "--device-types", str(src / "deviceTypes.xcat"),
            "--tech-file", str(src / "TechnologieFile.xml"),
            "--spec", str(src / "CircuitSpecifications.xml"),
            "--library-dir", str(generated_library_dir),
            "--output-dir", str(out_dir),
        ]

    def test_returncode_zero(self, cli_args):
        assert run(cli_args).returncode == 0

    def test_writes_summary_json(self, cli_args, out_dir):
        run(cli_args)
        assert (out_dir / "synthesis_results.json").exists()

    def test_returns_at_least_one_candidate(self, cli_args):
        result = run(cli_args)
        # `results` is a list of (TopologySpec, SizingResult) pairs after
        # the engine's filter+rank pass.
        assert len(result.data.results) >= 1, \
            "synthesis returned no ranked candidates"


# ═══════════════════════════════════════════════════════════════════════
# 6. toplibgen  (slow — generates ~7000 topologies)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestTopLibGenCLI:
    """`pyckt toplibgen` end-to-end: enumerate topologies + write to disk."""

    def test_returncode_zero(self, generated_library_dir):
        # The fixture itself asserts returncode == 0 during build; this
        # test exists so the assertion is also visible at test-discovery time.
        assert generated_library_dir.is_dir()

    def test_writes_more_than_100_ckt_files(self, generated_library_dir):
        ckt_files = list(generated_library_dir.rglob("*.ckt"))
        assert len(ckt_files) > 100, f"only {len(ckt_files)} .ckt files written"

    def test_writes_all_four_category_directories(self, generated_library_dir):
        for category in (
            "one_stage_single_output",
            "one_stage_fully_differential",
            "two_stage_single_output",
            "two_stage_fully_differential",
        ):
            assert (generated_library_dir / category).is_dir(), \
                f"missing category {category}"

    def test_each_ckt_has_companion_json(self, generated_library_dir):
        ckt_count = len(list(generated_library_dir.rglob("*.ckt")))
        json_count = len(list(generated_library_dir.rglob("topology_*.json")))
        assert ckt_count == json_count, \
            f".ckt={ckt_count} but .json={json_count}"
