"""Tests for the ACST-format topology-library emitter (``--output-format acst``).

Covers the three pieces wired together for toplibgen Stage 2:

* :class:`~ckt_io.hspice_writer.AcstNetlistWriter` — circuit → ``.ckt`` lines
* :meth:`~synthesis.library.TopologySpec.acst_category` /
  :meth:`~synthesis.library.TopologySpec.acst_name_prefix`
* :meth:`~synthesis.library.TopologyLibrary.to_acst_directory`
* :meth:`~topogen.analysis.TopLibGenAnalysis.write` honouring ``output_format``

The heavy end-to-end run of the real generator is marked ``slow``.
"""
from __future__ import annotations

import argparse

import pytest

from ckt_io.hspice_writer import AcstNetlistWriter
from core import Circuit, Device, DeviceType, PinType, TechType, Terminal
from synthesis.library import TopologyLibrary, TopologySpec

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _spec(id, *, stages=1, complementary=False, fd=False, tech=TechType.N):
    return TopologySpec(
        id=id,
        name=f"t{id}",
        num_stages=stages,
        is_complementary=complementary,
        is_fully_differential=fd,
        input_tech=tech,
    )


def _mosfet(name, tech, nets):
    """Build a MOSFET with the given ``{PinType: net_name}`` connections."""
    dev = Device(name=name, device_type=DeviceType.MOSFET, tech_type=tech)
    ckt = Circuit(name="probe")
    for pin, net_name in nets.items():
        net = ckt.find_or_create_net(net_name)
        dev.add_terminal(Terminal(device=dev, pin_type=pin, net=net))
    return dev


def _one_device_circuit(dev):
    ckt = Circuit(name="opamp")
    ckt.add_device(dev)
    return ckt


# ---------------------------------------------------------------------------
# AcstNetlistWriter
# ---------------------------------------------------------------------------

class TestAcstNetlistWriter:
    def test_full_mosfet_line_has_bulk_and_short_model(self, tmp_path):
        dev = _mosfet("M1", TechType.N, {
            PinType.DRAIN: "out", PinType.GATE: "in1", PinType.SOURCE: "source_nmos",
        })
        out = tmp_path / "t.ckt"
        AcstNetlistWriter().write(_one_device_circuit(dev), out, name="t")
        lines = out.read_text().splitlines()

        assert lines[0] == (
            ".suckt  t ibias in1 in2 out source_nmos source_pmos"
        )
        # drain gate source bulk(=source) nmos
        assert lines[1] == "M1 out in1 source_nmos source_nmos nmos"
        assert lines[-1] == ".end t"

    def test_pmos_model_token(self, tmp_path):
        dev = _mosfet("M2", TechType.P, {
            PinType.DRAIN: "out", PinType.GATE: "in2", PinType.SOURCE: "source_pmos",
        })
        out = tmp_path / "t.ckt"
        AcstNetlistWriter().write(_one_device_circuit(dev), out, name="t")
        assert out.read_text().splitlines()[1].endswith(" pmos")

    def test_explicit_bulk_pin_is_respected(self, tmp_path):
        dev = _mosfet("M1", TechType.N, {
            PinType.DRAIN: "out", PinType.GATE: "in1",
            PinType.SOURCE: "s", PinType.BULK: "gnd",
        })
        out = tmp_path / "t.ckt"
        AcstNetlistWriter().write(_one_device_circuit(dev), out, name="t")
        assert out.read_text().splitlines()[1] == "M1 out in1 s gnd nmos"

    def test_missing_pins_are_skipped(self, tmp_path):
        # Only a gate connection — mirrors topogen's partial connectivity.
        dev = _mosfet("M1", TechType.P, {PinType.GATE: "in1"})
        out = tmp_path / "t.ckt"
        AcstNetlistWriter().write(_one_device_circuit(dev), out, name="t")
        assert out.read_text().splitlines()[1] == "M1 in1 pmos"

    def test_custom_ports(self, tmp_path):
        dev = _mosfet("M1", TechType.N, {PinType.GATE: "a"})
        out = tmp_path / "t.ckt"
        AcstNetlistWriter().write(
            _one_device_circuit(dev), out, name="t", ports=("a", "b"),
        )
        assert out.read_text().splitlines()[0] == ".suckt  t a b"


# ---------------------------------------------------------------------------
# TopologySpec ACST helpers
# ---------------------------------------------------------------------------

class TestTopologySpecAcstHelpers:
    @pytest.mark.parametrize("kw, category", [
        (dict(), "SingleOutputOpAmps"),
        (dict(fd=True), "FullyDifferentialOpAmps"),
        (dict(complementary=True), "ComplementaryOpAmps"),
        # complementary wins over fully-differential
        (dict(complementary=True, fd=True), "ComplementaryOpAmps"),
    ])
    def test_acst_category(self, kw, category):
        assert _spec(1, **kw).acst_category() == category

    @pytest.mark.parametrize("kw, prefix", [
        (dict(stages=1), "one_stage_single_output_op_amp"),
        (dict(stages=2), "two_stage_single_output_op_amp"),
        (dict(stages=1, fd=True), "one_stage_fully_differential_op_amp"),
        (dict(stages=2, fd=True), "two_stage_fully_differential_op_amp"),
        (dict(complementary=True), "complementary_op_amp"),
        (dict(stages=2, complementary=True), "complementary_op_amp"),
    ])
    def test_acst_name_prefix(self, kw, prefix):
        assert _spec(1, **kw).acst_name_prefix() == prefix


# ---------------------------------------------------------------------------
# TopologyLibrary.to_acst_directory
# ---------------------------------------------------------------------------

class TestToAcstDirectory:
    def _lib(self):
        lib = TopologyLibrary()
        # two single-output (1- and 2-stage), one FD, one complementary
        lib.add(_spec(1, stages=1), _one_device_circuit(
            _mosfet("M1", TechType.N, {PinType.GATE: "in1"})))
        lib.add(_spec(2, stages=2), _one_device_circuit(
            _mosfet("M1", TechType.P, {PinType.GATE: "in2"})))
        lib.add(_spec(3, fd=True), _one_device_circuit(
            _mosfet("M1", TechType.N, {PinType.GATE: "in1"})))
        lib.add(_spec(4, complementary=True), _one_device_circuit(
            _mosfet("M1", TechType.N, {PinType.GATE: "in1"})))
        return lib

    def test_counts_and_layout(self, tmp_path):
        counts = self._lib().to_acst_directory(str(tmp_path))
        assert counts == {
            "SingleOutputOpAmps": 2,
            "FullyDifferentialOpAmps": 1,
            "ComplementaryOpAmps": 1,
        }
        assert (tmp_path / "SingleOutputOpAmps"
                / "one_stage_single_output_op_amp1.ckt").exists()
        assert (tmp_path / "SingleOutputOpAmps"
                / "two_stage_single_output_op_amp1.ckt").exists()
        assert (tmp_path / "FullyDifferentialOpAmps"
                / "one_stage_fully_differential_op_amp1.ckt").exists()
        assert (tmp_path / "ComplementaryOpAmps"
                / "complementary_op_amp1.ckt").exists()

    def test_running_index_per_prefix(self, tmp_path):
        lib = TopologyLibrary()
        # distinct circuits (different gate nets) — identical ones would be
        # de-duplicated at emission (issue #48)
        for i, net in ((1, "in1"), (2, "in2"), (3, "ibias")):
            lib.add(_spec(i, stages=1), _one_device_circuit(
                _mosfet("M1", TechType.N, {PinType.GATE: net})))
        lib.to_acst_directory(str(tmp_path))
        names = sorted(p.name for p in
                       (tmp_path / "SingleOutputOpAmps").glob("*.ckt"))
        assert names == [
            "one_stage_single_output_op_amp1.ckt",
            "one_stage_single_output_op_amp2.ckt",
            "one_stage_single_output_op_amp3.ckt",
        ]

    def test_structural_duplicates_deduplicated(self, tmp_path):
        """acst emits one file per distinct topology: entries serialising to
        the same name-independent netlist are written once (issue #48)."""
        lib = TopologyLibrary()
        for i in (1, 2, 3):  # three identical circuits
            lib.add(_spec(i, stages=1), _one_device_circuit(
                _mosfet("M1", TechType.N, {PinType.GATE: "in1"})))
        lib.add(_spec(4, stages=1), _one_device_circuit(
            _mosfet("M1", TechType.N, {PinType.GATE: "in2"})))  # distinct
        counts = lib.to_acst_directory(str(tmp_path))
        assert counts == {"SingleOutputOpAmps": 2}
        names = sorted(p.name for p in
                       (tmp_path / "SingleOutputOpAmps").glob("*.ckt"))
        assert names == [
            "one_stage_single_output_op_amp1.ckt",
            "one_stage_single_output_op_amp2.ckt",
        ]

    def test_stale_files_cleared_before_write(self, tmp_path):
        """Re-running into the same directory replaces the category dirs
        instead of mixing stale files from earlier runs (issue #48 — the
        2026-07-08 comparison found 1 795 + 1 134 June leftovers)."""
        stale = tmp_path / "SingleOutputOpAmps" / "one_stage_single_output_op_amp99.ckt"
        stale.parent.mkdir(parents=True)
        stale.write_text("stale")
        self._lib().to_acst_directory(str(tmp_path))
        assert not stale.exists()
        assert (tmp_path / "SingleOutputOpAmps"
                / "one_stage_single_output_op_amp1.ckt").exists()

    def test_unconverted_circuits_are_skipped(self, tmp_path):
        lib = TopologyLibrary()
        lib.add(_spec(1, stages=1), None)  # convert failed
        lib.add(_spec(2, stages=1), _one_device_circuit(
            _mosfet("M1", TechType.N, {PinType.GATE: "in1"})))
        counts = lib.to_acst_directory(str(tmp_path))
        assert counts == {"SingleOutputOpAmps": 1}
        # the surviving one is numbered 1 (skipped entry consumes no index)
        assert (tmp_path / "SingleOutputOpAmps"
                / "one_stage_single_output_op_amp1.ckt").exists()

    def test_suckt_name_matches_file_stem(self, tmp_path):
        self._lib().to_acst_directory(str(tmp_path))
        f = (tmp_path / "SingleOutputOpAmps"
             / "one_stage_single_output_op_amp1.ckt")
        first = f.read_text().splitlines()[0]
        assert first.split()[1] == "one_stage_single_output_op_amp1"


# ---------------------------------------------------------------------------
# TopLibGenAnalysis.write — output_format dispatch
# ---------------------------------------------------------------------------

def _make_args(**kw):
    defaults = dict(output_dir=None, output_format="native")
    defaults.update(kw)
    return argparse.Namespace(**defaults)


class TestTopLibGenWriteDispatch:
    def _prepared(self, out_dir, output_format):
        from topogen.analysis import TopLibGenAnalysis
        analysis = TopLibGenAnalysis(
            _make_args(output_dir=str(out_dir), output_format=output_format))
        analysis.initialize()
        # inject a tiny hand-built library instead of running the generator
        lib = TopologyLibrary()
        lib.add(_spec(1, stages=1), _one_device_circuit(
            _mosfet("M1", TechType.N, {PinType.GATE: "in1"})))
        analysis.library = lib
        return analysis

    def test_acst_format_writes_category_dirs_no_json(self, tmp_path):
        self._prepared(tmp_path, "acst").write()
        assert (tmp_path / "SingleOutputOpAmps"
                / "one_stage_single_output_op_amp1.ckt").exists()
        assert list(tmp_path.rglob("*.json")) == []

    def test_native_format_writes_json_sidecar(self, tmp_path):
        self._prepared(tmp_path, "native").write()
        assert list(tmp_path.rglob("*.json"))
        assert list(tmp_path.rglob("topology_*.ckt"))

    def test_default_format_is_native(self, tmp_path):
        from topogen.analysis import TopLibGenAnalysis
        # args without an output_format attribute → getattr default "native"
        analysis = TopLibGenAnalysis(argparse.Namespace(output_dir=str(tmp_path)))
        analysis.initialize()
        lib = TopologyLibrary()
        lib.add(_spec(1, stages=1), _one_device_circuit(
            _mosfet("M1", TechType.N, {PinType.GATE: "in1"})))
        analysis.library = lib
        analysis.write()
        assert list(tmp_path.rglob("*.json"))


# ---------------------------------------------------------------------------
# Slow end-to-end: full generator → acst format
# ---------------------------------------------------------------------------

@pytest.mark.slow
class TestAcstEndToEnd:
    def test_full_generator_emits_three_categories(self, tmp_path):
        from topogen.analysis import TopLibGenAnalysis
        analysis = TopLibGenAnalysis(
            _make_args(output_dir=str(tmp_path), output_format="acst"))
        analysis.initialize()
        analysis.compute()
        analysis.write()

        # one file per *distinct* topology (issue #48): the generated library
        # carries 390 structural duplicates (30 one-stage + 360 two-stage
        # single-output), so the emission matches acst's 3912-file reference
        # set rather than library.size() == 4302
        ckt = list(tmp_path.rglob("*.ckt"))
        assert len(ckt) == 3912
        assert len(ckt) == analysis.library.size() - 390
        for cat in ("SingleOutputOpAmps", "FullyDifferentialOpAmps",
                    "ComplementaryOpAmps"):
            assert (tmp_path / cat).is_dir()
            assert list((tmp_path / cat).glob("*.ckt"))
        # no native sidecars in acst mode
        assert list(tmp_path.rglob("*.json")) == []
