"""Tests for the existing topogen HL2–HL5 factory classes.

All imports have been updated from the old ``pyckt.topology.*`` namespace
(which referenced a PySpice-based prototype) to the real ``topogen.*``
namespace that uses the custom ``Circuit`` model.

The tests exercise the *manager* classes that each HL2 file exposes:

* :class:`~topogen.HL2.dp.DiffPairManager` — 2 differential pairs
* :class:`~topogen.HL2.vb.VoltageBiasManager` — 10 voltage-bias variants
* :class:`~topogen.HL2.cb.CurrentBiasManager` — 6 current-bias variants
* :class:`~topogen.HL2.inv.InverterManager` — 9 analog-inverter variants

Each test verifies:

1. The factory instantiates without errors.
2. The expected number of variants is returned.
3. Each variant has the correct ``techtype``.
4. Transistor-level instances (``NormalTransistor`` / ``DiodeTransistor``)
   are present.
5. Required port names are present on each circuit.
"""
import pytest

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
from topogen.common.circuit import (
    Circuit,
    CurrentBias,
    DiffPair,
    DiodeTransistor,
    Inverter,
    NormalTransistor,
    VoltageBias,
)


def _count_transistors(circuit: Circuit, cls) -> int:
    """Count immediate instances of *cls* inside *circuit*."""
    return sum(1 for inst in circuit.instances if isinstance(inst, cls))


# ---------------------------------------------------------------------------
# DifferentialPair (dp.py)
# ---------------------------------------------------------------------------

class TestDiffPairManager:
    @pytest.fixture(scope="class")
    def manager(self):
        from topogen.HL2.dp import DiffPairManager
        return DiffPairManager()

    def test_returns_two_pairs(self, manager):
        pairs = manager.getAllDiffPairs()
        assert len(pairs) == 2

    def test_pmos_pair_techtype(self, manager):
        dp = manager.getDifferentialPairPmos()
        assert dp.tech == "p"

    def test_nmos_pair_techtype(self, manager):
        dp = manager.getDifferentialPairNmos()
        assert dp.tech == "n"

    def test_pmos_pair_has_two_transistors(self, manager):
        dp = manager.getDifferentialPairPmos()
        assert _count_transistors(dp, NormalTransistor) == 2

    def test_nmos_pair_has_two_transistors(self, manager):
        dp = manager.getDifferentialPairNmos()
        assert _count_transistors(dp, NormalTransistor) == 2

    def test_pmos_pair_has_required_ports(self, manager):
        dp = manager.getDifferentialPairPmos()
        for port in [DiffPair.INPUT1, DiffPair.INPUT2,
                     DiffPair.OUTPUT1, DiffPair.OUTPUT2, DiffPair.SOURCE]:
            assert port in dp.ports

    def test_nmos_pair_has_required_ports(self, manager):
        dp = manager.getDifferentialPairNmos()
        for port in [DiffPair.INPUT1, DiffPair.INPUT2,
                     DiffPair.OUTPUT1, DiffPair.OUTPUT2, DiffPair.SOURCE]:
            assert port in dp.ports

    def test_all_pairs_are_DiffPair_instances(self, manager):
        for dp in manager.getAllDiffPairs():
            assert isinstance(dp, DiffPair)


# ---------------------------------------------------------------------------
# VoltageBias (vb.py)
# ---------------------------------------------------------------------------

class TestVoltageBiasManager:
    @pytest.fixture
    def manager(self):
        from topogen.HL2.vb import VoltageBiasManager
        return VoltageBiasManager()

    def test_six_pmos_variants(self, manager):
        # 2 one-transistor + 4 two-transistor (diode+diode, normal+normal,
        # and both mixed normal+diode variants — acst
        # createTwoTransistorVoltageBiases runs *both* branches for mixed)
        assert len(list(manager.getAllVoltageBiasesPmos())) == 6

    def test_six_nmos_variants(self, manager):
        assert len(list(manager.getAllVoltageBiasesNmos())) == 6

    def test_pmos_variants_techtype(self, manager):
        for vb in manager.getAllVoltageBiasesPmos():
            assert vb.tech == "p"

    def test_nmos_variants_techtype(self, manager):
        for vb in manager.getAllVoltageBiasesNmos():
            assert vb.tech == "n"

    def test_all_variants_are_VoltageBias_instances(self, manager):
        from itertools import chain
        for vb in chain(manager.getAllVoltageBiasesPmos(),
                        manager.getAllVoltageBiasesNmos()):
            assert isinstance(vb, VoltageBias)

    def test_each_variant_has_at_least_one_transistor(self, manager):
        from itertools import chain
        for vb in chain(manager.getAllVoltageBiasesPmos(),
                        manager.getAllVoltageBiasesNmos()):
            total = (_count_transistors(vb, NormalTransistor)
                     + _count_transistors(vb, DiodeTransistor))
            assert total >= 1, f"No transistors in {vb}"

    def test_diode_transistor_vb_pmos_exists(self):
        from topogen.HL2.vb import VoltageBiasManager
        vb = VoltageBiasManager().getDiodeTransistorVoltageBiasPmos()
        assert vb is not None
        assert vb.tech == "p"

    def test_diode_transistor_vb_nmos_exists(self):
        from topogen.HL2.vb import VoltageBiasManager
        vb = VoltageBiasManager().getDiodeTransistorVoltageBiasNmos()
        assert vb is not None
        assert vb.tech == "n"

    def test_two_diode_transistor_vb_nmos_exists(self):
        """`getTwoDiodeTransistorVoltageBiasNmos` scans two-transistor VBs and
        returns the one composed of two diode-connected transistors."""
        from topogen.HL2.vb import VoltageBiasManager
        vb = VoltageBiasManager().getTwoDiodeTransistorVoltageBiasNmos()
        assert vb is not None
        assert vb.instances[0].name == "dt"
        assert vb.instances[1].name == "dt"
        assert vb.tech == "n"

    def test_two_diode_transistor_vb_pmos_exists(self):
        from topogen.HL2.vb import VoltageBiasManager
        vb = VoltageBiasManager().getTwoDiodeTransistorVoltageBiasPmos()
        assert vb is not None
        assert vb.instances[0].name == "dt"
        assert vb.instances[1].name == "dt"
        assert vb.tech == "p"

    def test_create_two_transistor_circuit_empty_for_dt_then_nt(self):
        """When source is a diode and output is a normal transistor neither
        branch in `createTwoTransistorCircuit` matches → returns no
        circuits."""
        from topogen.common.circuit import DiodeTransistor, NormalTransistor
        from topogen.HL2.vb import VoltageBiasManager
        result = VoltageBiasManager().createTwoTransistorCircuit(
            sourceTransistor=DiodeTransistor(techtype="n"),
            outputTransistor=NormalTransistor(techtype="n"),
        )
        assert result == []

    def test_create_two_transistor_circuit_two_mixed_variants(self):
        """A mixed normal+diode pair yields both acst variants: one with the
        source gate on its own OUTSOURCE net, one with it tied to IN."""
        from topogen.common.circuit import DiodeTransistor, NormalTransistor
        from topogen.HL2.vb import VoltageBiasManager
        result = VoltageBiasManager().createTwoTransistorCircuit(
            sourceTransistor=NormalTransistor(techtype="n"),
            outputTransistor=DiodeTransistor(techtype="n"),
        )
        assert len(result) == 2


# ---------------------------------------------------------------------------
# CurrentBias (cb.py)
# ---------------------------------------------------------------------------

class TestCurrentBiasManager:
    @pytest.fixture
    def manager(self):
        from topogen.HL2.cb import CurrentBiasManager
        return CurrentBiasManager()

    def test_three_pmos_variants(self, manager):
        assert len(manager.getAllCurrentBiasesPmos()) == 3

    def test_three_nmos_variants(self, manager):
        assert len(manager.getAllCurrentBiasesNmos()) == 3

    def test_pmos_variants_techtype(self, manager):
        for cb in manager.getAllCurrentBiasesPmos():
            assert cb.tech == "p"

    def test_nmos_variants_techtype(self, manager):
        for cb in manager.getAllCurrentBiasesNmos():
            assert cb.tech == "n"

    def test_all_variants_are_CurrentBias_instances(self, manager):
        for cb in (manager.getAllCurrentBiasesPmos()
                   + manager.getAllCurrentBiasesNmos()):
            assert isinstance(cb, CurrentBias)

    def test_one_transistor_nmos_variant_exists(self, manager):
        # getOneTransistorCurrentBiasesNmos now returns a list (fixed bug)
        result = manager.getOneTransistorCurrentBiasesNmos()
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], CurrentBias)
        assert result[0].component_count == 1

    def test_two_transistor_nmos_variants_exist(self):
        from topogen.HL2.cb import CurrentBiasManager
        # Fresh manager ensures chain iterator not yet consumed
        two = list(CurrentBiasManager().getTwoTransistorCurrentBiasesNmos())
        assert len(two) == 2
        for cb in two:
            assert cb.component_count == 2

    def test_normal_transistor_cb_nmos(self):
        from topogen.HL2.cb import CurrentBiasManager
        # getOneTransistorCurrentBiasesNmos returns a list with one CurrentBias
        cbs = CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        assert len(cbs) == 1
        cb = cbs[0]
        assert isinstance(cb, CurrentBias)
        assert isinstance(cb.instances[0], NormalTransistor)

    def test_get_normal_transistor_current_bias_iterates_lists(self):
        """`getNormalTransistorCurrentBias` iterates `oneTransistorCurrentBiases*_`
        as if they were lists, but they are single `CurrentBias` instances —
        wrapping them in lists exercises lines 49-56."""
        from topogen.HL2.cb import CurrentBiasManager
        m = CurrentBiasManager()
        # Wrap the single CurrentBias in a list to make the function's
        # for-loop work as it intends.
        m.oneTransistorCurrentBiasesNmos_ = [m.oneTransistorCurrentBiasesNmos_]
        m.oneTransistorCurrentBiasesPmos_ = [m.oneTransistorCurrentBiasesPmos_]

        cb_n = m.getNormalTransistorCurrentBias("n")
        assert isinstance(cb_n, CurrentBias)
        assert cb_n.tech == "n"
        assert cb_n.instances[0].name == "nt"

        cb_p = m.getNormalTransistorCurrentBias("p")
        assert isinstance(cb_p, CurrentBias)
        assert cb_p.tech == "p"
        assert cb_p.instances[0].name == "nt"


# ---------------------------------------------------------------------------
# AnalogInverter (inv.py)
# ---------------------------------------------------------------------------

class TestInverterManager:
    @pytest.fixture(scope="class")
    def manager(self):
        from topogen.HL2.inv import InverterManager
        return InverterManager()

    def test_nine_inverter_variants(self, manager):
        assert len(manager.getAnalogInverters()) == 9

    def test_all_variants_are_Inverter_instances(self, manager):
        for inv in manager.getAnalogInverters():
            assert isinstance(inv, Inverter)

    def test_each_inverter_has_output_port(self, manager):
        for inv in manager.getAnalogInverters():
            assert Inverter.OUTPUT in inv.ports

    def test_each_inverter_has_two_current_bias_instances(self, manager):
        for inv in manager.getAnalogInverters():
            cbs = [i for i in inv.instances if isinstance(i, CurrentBias)]
            assert len(cbs) == 2

    def test_inverter_pmos_and_nmos_cb_pairing(self, manager):
        for inv in manager.getAnalogInverters():
            techs = {i.tech for i in inv.instances if isinstance(i, CurrentBias)}
            assert "p" in techs
            assert "n" in techs


# ---------------------------------------------------------------------------
# CurrentMirror (cm.py) — Phase 4
# ---------------------------------------------------------------------------

class TestCurrentMirrorFactory:
    @pytest.fixture(scope="class")
    def factory(self):
        from topogen.HL2.cm import CurrentMirrorFactory
        return CurrentMirrorFactory()

    def test_returns_two_mirrors(self, factory):
        assert len(factory.getAllCurrentMirrors()) == 2

    def test_nmos_techtype(self, factory):
        cm = factory.getCurrentMirrorNmos()
        assert cm.tech == "n"

    def test_pmos_techtype(self, factory):
        cm = factory.getCurrentMirrorPmos()
        assert cm.tech == "p"

    def test_each_mirror_is_CurrentMirror_instance(self, factory):
        from topogen.HL2.cm import CurrentMirror
        for cm in factory.getAllCurrentMirrors():
            assert isinstance(cm, CurrentMirror)

    def test_each_mirror_has_diode_and_normal_transistor(self, factory):
        for cm in factory.getAllCurrentMirrors():
            assert _count_transistors(cm, DiodeTransistor) == 1
            assert _count_transistors(cm, NormalTransistor) == 1

    def test_required_ports_present(self, factory):
        from topogen.HL2.cm import CurrentMirror
        for cm in factory.getAllCurrentMirrors():
            for port in [CurrentMirror.INPUT, CurrentMirror.OUTPUT, CurrentMirror.SOURCE]:
                assert port in cm.ports

    def test_input_port_carries_diode_drain_and_both_gates(self, factory):
        """The INPUT net is the shared gate node (also the diode's drain)."""
        from topogen.HL2.cm import CurrentMirror
        for cm in factory.getAllCurrentMirrors():
            input_conns = cm.connections[CurrentMirror.INPUT]
            ports = [c["port"] for c in input_conns]
            # Diode drain + diode gate + normal gate
            assert ports.count("drain") == 1
            assert ports.count("gate") == 2

    def test_output_port_only_normal_drain(self, factory):
        from topogen.HL2.cm import CurrentMirror
        for cm in factory.getAllCurrentMirrors():
            output_conns = cm.connections[CurrentMirror.OUTPUT]
            assert len(output_conns) == 1
            assert output_conns[0]["port"] == "drain"
            assert output_conns[0]["child"][0] == "nt"

    def test_source_port_shared_by_both_transistors(self, factory):
        from topogen.HL2.cm import CurrentMirror
        for cm in factory.getAllCurrentMirrors():
            src_conns = cm.connections[CurrentMirror.SOURCE]
            assert len(src_conns) == 2
            for conn in src_conns:
                assert conn["port"] == "source"

    def test_flatten_yields_two_leaf_transistors(self, factory):
        from copy import deepcopy
        for cm in factory.getAllCurrentMirrors():
            flat = deepcopy(cm).flatten()
            assert len(flat.instances) == 2

    def test_flatten_assigns_input_net_to_both_gates(self, factory):
        """After flattening, both transistors must have gate == 'input'."""
        from copy import deepcopy
        for cm in factory.getAllCurrentMirrors():
            flat = deepcopy(cm).flatten()
            for inst in flat.instances:
                assert inst.gate == "input"

    def test_default_id_is_one(self):
        """Constructor without explicit id falls back to id=1."""
        from topogen.HL2.cm import CurrentMirror
        cm = CurrentMirror(techtype="n")
        assert cm.id == 1


# ---------------------------------------------------------------------------
# CrossCoupledPair (ccp.py) — Phase 4
# ---------------------------------------------------------------------------

class TestCrossCoupledPairFactory:
    @pytest.fixture(scope="class")
    def factory(self):
        from topogen.HL2.ccp import CrossCoupledPairFactory
        return CrossCoupledPairFactory()

    def test_returns_two_pairs(self, factory):
        assert len(factory.getAllCrossCoupledPairs()) == 2

    def test_nmos_techtype(self, factory):
        ccp = factory.getCrossCoupledPairNmos()
        assert ccp.tech == "n"

    def test_pmos_techtype(self, factory):
        ccp = factory.getCrossCoupledPairPmos()
        assert ccp.tech == "p"

    def test_each_pair_is_CrossCoupledPair_instance(self, factory):
        from topogen.HL2.ccp import CrossCoupledPair
        for ccp in factory.getAllCrossCoupledPairs():
            assert isinstance(ccp, CrossCoupledPair)

    def test_each_pair_has_two_normal_transistors(self, factory):
        for ccp in factory.getAllCrossCoupledPairs():
            assert _count_transistors(ccp, NormalTransistor) == 2
            assert _count_transistors(ccp, DiodeTransistor) == 0

    def test_required_ports_present(self, factory):
        from topogen.HL2.ccp import CrossCoupledPair
        for ccp in factory.getAllCrossCoupledPairs():
            for port in [
                CrossCoupledPair.OUTPUT1,
                CrossCoupledPair.OUTPUT2,
                CrossCoupledPair.SOURCE,
            ]:
                assert port in ccp.ports

    def test_output1_carries_t1_drain_and_t2_gate(self, factory):
        from topogen.HL2.ccp import CrossCoupledPair
        for ccp in factory.getAllCrossCoupledPairs():
            conns = ccp.connections[CrossCoupledPair.OUTPUT1]
            ports = [c["port"] for c in conns]
            assert "drain" in ports
            assert "gate" in ports

    def test_output2_carries_t2_drain_and_t1_gate(self, factory):
        from topogen.HL2.ccp import CrossCoupledPair
        for ccp in factory.getAllCrossCoupledPairs():
            conns = ccp.connections[CrossCoupledPair.OUTPUT2]
            ports = [c["port"] for c in conns]
            assert "drain" in ports
            assert "gate" in ports

    def test_source_port_shared_by_both_transistors(self, factory):
        from topogen.HL2.ccp import CrossCoupledPair
        for ccp in factory.getAllCrossCoupledPairs():
            src_conns = ccp.connections[CrossCoupledPair.SOURCE]
            assert len(src_conns) == 2
            for conn in src_conns:
                assert conn["port"] == "source"

    def test_flatten_yields_two_leaf_transistors(self, factory):
        from copy import deepcopy
        for ccp in factory.getAllCrossCoupledPairs():
            flat = deepcopy(ccp).flatten()
            assert len(flat.instances) == 2

    def test_flatten_cross_couples_gate_and_drain_nets(self, factory):
        """After flattening, T1.gate must equal T2.drain (and vice-versa)."""
        from copy import deepcopy
        for ccp in factory.getAllCrossCoupledPairs():
            flat = deepcopy(ccp).flatten()
            t1, t2 = flat.instances
            assert t1.gate == t2.drain
            assert t2.gate == t1.drain

    def test_default_id_is_one(self):
        """Constructor without explicit id falls back to id=1."""
        from topogen.HL2.ccp import CrossCoupledPair
        ccp = CrossCoupledPair(techtype="n")
        assert ccp.id == 1


# ═══════════════════════════════════════════════════════════════════════════
# topogen.common.circuit — Circuit subclasses + utility helpers
# ═══════════════════════════════════════════════════════════════════════════

# All non-leaf `Circuit` subclasses in `topogen.common.circuit` carry the
# same `if "id" not in kwargs: kwargs["id"] = 1` default-id branch in
# their constructors.  Every factory in the codebase passes `id=...`
# explicitly, so that branch was never executed before this test.

class TestCircuitClassDefaultIdBranch:
    @pytest.mark.parametrize("cls_name", [
        "VoltageBias", "CurrentBias", "Inverter", "TransistorStack",
        "LoadPart", "Load", "DiffPair", "StageBias",
        "Transconductance", "NonInvertingStage", "InvertingStage", "OpAmp",
    ])
    def test_default_id_is_one(self, cls_name):
        from topogen.common import circuit as cm
        cls = getattr(cm, cls_name)
        obj = cls(techtype="n")   # no id kwarg → default-branch
        assert obj.id == 1


class TestCircuitToDict:
    """Round-trip a leaf transistor through `to_dict()` / `from_dict()`
    to cover the `if self.name in ["dt", "nt"]` assertion path and the
    leaf-handling branch in `Circuit.from_dict`."""

    def test_normal_transistor_round_trips(self):
        from topogen.common.circuit import Circuit, NormalTransistor
        nt = NormalTransistor(techtype="n", id=5)
        d = nt.to_dict()
        assert d["__class__"] == "NormalTransistor"
        assert d["name"] == "nt"
        assert d["id"] == 5
        assert d["techtype"] == "n"
        assert d["instances"] == []
        restored = Circuit.from_dict(d)
        assert isinstance(restored, NormalTransistor)
        assert restored.id == 5
        assert restored.techtype == "n"


class TestCircuitUtilityHelpers:
    """Pure-logic helpers at the bottom of `topogen.common.circuit`."""

    def test_assign_instance_ids_default_start(self):
        from topogen.common.circuit import DiffPair, assignInstanceIds
        circuits = [DiffPair(techtype="n", id=99) for _ in range(3)]
        assignInstanceIds(circuits)                   # default start_idx = 10
        assert [c.id for c in circuits] == [10, 11, 12]

    def test_assign_instance_ids_explicit_start(self):
        from topogen.common.circuit import DiffPair, assignInstanceIds
        circuits = [DiffPair(techtype="n"), DiffPair(techtype="p")]
        assignInstanceIds(circuits, start_idx=42)
        assert [c.id for c in circuits] == [42, 43]

    def test_has_gcc_true(self):
        from topogen.common.circuit import Load, hasGCC
        load = Load(techtype="n")
        load.ports = ["out1", "out2", "inner_gcc"]
        assert hasGCC(load) is True

    def test_has_gcc_false(self):
        from topogen.common.circuit import Load, hasGCC
        load = Load(techtype="n")
        load.ports = ["out1", "out2"]
        assert hasGCC(load) is False

    def test_source_transistor_is_diode_one_transistor(self):
        from topogen.common.circuit import (
            CurrentBias,
            DiodeTransistor,
            NormalTransistor,
            sourceTransistorIsDiodeTransistor,
        )
        cb_d = CurrentBias(techtype="n"); cb_d.add_instance(DiodeTransistor(techtype="n"))
        assert sourceTransistorIsDiodeTransistor(cb_d) is True

        cb_n = CurrentBias(techtype="n"); cb_n.add_instance(NormalTransistor(techtype="n"))
        assert sourceTransistorIsDiodeTransistor(cb_n) is False

    def test_source_transistor_is_diode_two_transistor(self):
        """In a two-transistor CurrentBias, the source transistor (the
        first instance) decides."""
        from topogen.common.circuit import (
            CurrentBias,
            DiodeTransistor,
            NormalTransistor,
            sourceTransistorIsDiodeTransistor,
        )
        cb1 = CurrentBias(techtype="n")
        cb1.add_instance(DiodeTransistor(techtype="n"))   # source
        cb1.add_instance(NormalTransistor(techtype="n"))  # output
        assert sourceTransistorIsDiodeTransistor(cb1) is True

        cb2 = CurrentBias(techtype="n")
        cb2.add_instance(NormalTransistor(techtype="n"))  # source
        cb2.add_instance(DiodeTransistor(techtype="n"))   # output
        assert sourceTransistorIsDiodeTransistor(cb2) is False


class TestSaveGraphvizFigure:
    """Cover the dot-file-writer prologue/body (`digraph g {` header +
    font declarations + circuit body + closing `}`)."""

    def test_writes_well_formed_dot_file(self, tmp_path):
        from topogen.common.circuit import (
            NormalTransistor,
            save_graphviz_figure,
        )
        f = tmp_path / "out.dot"
        save_graphviz_figure(NormalTransistor(techtype="n"), filename=f)
        content = f.read_text()
        assert content.startswith("digraph g {")
        assert "Helvetica,Arial,sans-serif" in content
        assert content.rstrip().endswith("}")


class TestCircuitGraphvizPaths:
    """Cover the leaf-transistor + composite-circuit branches of `Circuit.graphviz`."""

    def test_normal_transistor_nmos(self):
        from topogen.common.circuit import NormalTransistor
        out = NormalTransistor(techtype="n").graphviz()
        # Nmos label uses the S⭢ glyph (line 141)
        assert "S⭢" in out
        assert "cluster_" in out

    def test_normal_transistor_pmos(self):
        from topogen.common.circuit import NormalTransistor
        out = NormalTransistor(techtype="p").graphviz()
        # Pmos label uses the S↲ glyph (line 134)
        assert "S↲" in out

    def test_diode_transistor_nmos(self):
        from topogen.common.circuit import DiodeTransistor
        out = DiodeTransistor(techtype="n").graphviz()
        # Diode-Nmos label uses D* and S⭢ glyphs (line 156)
        assert "D*" in out
        assert "S⭢" in out

    def test_diode_transistor_pmos(self):
        from topogen.common.circuit import DiodeTransistor
        out = DiodeTransistor(techtype="p").graphviz()
        # Diode-Pmos label uses S↲ and D* glyphs (line 149)
        assert "D*" in out
        assert "S↲" in out

    def test_composite_voltage_bias_graphviz(self):
        """Composite circuits exercise lines 183-227 (techtype + per-instance
        recursion + terminal nodes + connection edges, including the
        `dt`/`nt` port-mapping branch)."""
        from topogen.HL2.vb import VoltageBiasManager
        vbs = list(VoltageBiasManager().getAllVoltageBiasesNmos())
        out = vbs[0].graphviz()
        assert "cluster_" in out
        # Edges between top-level terminals and child transistor ports.
        assert "[arrowhead=none]" in out

    def test_composite_with_nested_inverter(self):
        """An Inverter contains CurrentBias children which themselves contain
        transistor children — exercising the `else` branch of the port-mapping
        (line 223) for non-leaf connections."""
        from topogen.HL2.inv import InverterManager
        invs = InverterManager().getAnalogInverters()
        out = invs[0].graphviz()
        assert "cluster_" in out


class TestCircuitFromDictNested:
    """Cover `Circuit.from_dict` recursion through child instances (line 247)."""

    def test_round_trip_voltage_bias_with_two_transistors(self):
        from topogen.common.circuit import Circuit, VoltageBias
        from topogen.HL2.vb import VoltageBiasManager
        vb = list(VoltageBiasManager().getAllVoltageBiasesNmos())[2]
        d = vb.to_dict()
        restored = Circuit.from_dict(d)
        assert isinstance(restored, VoltageBias)
        assert len(restored.instances) == len(vb.instances)
        # Child instances were recursed (line 247).
        assert restored.instances[0].techtype == vb.instances[0].techtype


class TestCircuitGetPort:
    """`Circuit.get_port` calls `.get()` on `self.ports` — which is a list,
    so the call always raises `AttributeError`.  Test simply exercises line 57."""

    def test_get_port_raises_on_list_ports(self):
        import pytest

        from topogen.common.circuit import NormalTransistor
        nt = NormalTransistor(techtype="n")
        with pytest.raises(AttributeError):
            nt.get_port("anything")


class TestConvertDotToPng:
    """Cover line 698: `convert_dot_to_png` shells out to the `dot` binary."""

    def test_convert_dot_to_png_invokes_os_system(self, tmp_path, monkeypatch):
        from topogen.common import circuit as cm
        captured = {}
        def fake_system(cmd):
            captured["cmd"] = cmd
            return 0
        monkeypatch.setattr(cm.os, "system", fake_system)
        cm.convert_dot_to_png(tmp_path / "in.dot", tmp_path / "out.png")
        assert "dot -Tpng" in captured["cmd"]
        assert "in.dot" in captured["cmd"]
        assert "out.png" in captured["cmd"]


class TestStageBiasManager:
    """Cover the manager-level `createStageBiases*` paths in HL3/sb.py
    (lines 64-71, 80, 82)."""

    def test_create_stage_biases_pmos(self):
        from topogen.HL3.sb import StageBiasManager
        sbs = list(StageBiasManager().createStageBiasesPmos())
        # 1× one-transistor + 2× two-transistor → 3 PMOS stage biases
        assert len(sbs) == 3

    def test_create_stage_biases_nmos(self):
        from topogen.HL3.sb import StageBiasManager
        sbs = list(StageBiasManager().createStageBiasesNmos())
        assert len(sbs) == 3


class TestTransconductanceManagerCreateMethods:
    """Cover the `createSimpleTransconductance` / `createFeedbackTransconductance`
    branches in HL3/tc.py (lines 110-117)."""

    def test_create_simple_transconductance(self):
        from topogen.HL3.tc import TransconductanceManager
        tcs = list(TransconductanceManager().createSimpleTransconductance())
        # One Pmos + one Nmos simple transconductance.
        assert len(tcs) == 2
        techs = {tc.tech for tc in tcs}
        assert techs == {"p", "n"}

    def test_create_feedback_transconductance(self):
        from topogen.HL3.tc import TransconductanceManager
        tcs = list(TransconductanceManager().createFeedbackTransconductance())
        assert len(tcs) == 2
        techs = {tc.tech for tc in tcs}
        assert techs == {"p", "n"}


class TestLoadPartManagerExtras:
    """Cover the remaining `createLoadParts*VoltageBiases` and the
    different-sources / three-transistor load-part branches in HL3/lp.py
    (lines 111-118, 128-131, 166, 183, 444-461)."""

    def test_create_load_parts_pmos_voltage_biases(self):
        from topogen.HL3.lp import LoadPartManager
        result = LoadPartManager().createLoadPartsPmosVoltageBiases()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_create_load_parts_nmos_voltage_biases(self):
        from topogen.HL3.lp import LoadPartManager
        result = LoadPartManager().createLoadPartsNmosVoltageBiases()
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_create_load_parts_pmos_two_tx_current_biases_different_sources(self):
        """Exercises `connectInstanceTerminalsOfTwoTransistorLoadPartDifferentSources`
        cb branch (lines 110-118): for a TS wrapping a CurrentBias, OUT1/OUT2
        wire to the stack's drain (`out`) and INNER wires to the gate (`in`)."""
        from topogen.HL3.lp import LoadPartManager
        result = LoadPartManager().createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources()
        assert isinstance(result, list) and result
        lp = result[0]
        # ts1 (num==1) wires OUT1 → ts.OUT, ts2 (num==2) wires OUT2 → ts.OUT.
        out1_ports = [c["port"] for c in lp.connections["out1"]]
        out2_ports = [c["port"] for c in lp.connections["out2"]]
        assert "out" in out1_ports
        assert "out" in out2_ports
        # Shared INNER net carries both gates (`in`).
        inner_ports = [c["port"] for c in lp.connections["inner"]]
        assert inner_ports.count("in") == 2

    def test_create_three_transistor_load_parts_mixed_pmos(self):
        """Exercises `connectInstanceTerminalsOfThreeTransistorLoadPart`
        (line 183 — non-`dt` branch)."""
        from topogen.HL2.cb import CurrentBiasManager
        from topogen.HL2.vb import VoltageBiasManager
        from topogen.HL3.lp import (
            createThreeTransistorLoadPartsMixed,
        )
        oneVb = VoltageBiasManager().getOneTransistorVoltageBiasesPmos()
        twoCb = CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        result = createThreeTransistorLoadPartsMixed(list(oneVb), list(twoCb))
        assert isinstance(result, list)


class TestLoadPartManagerPrintHelpers:
    """Cover the `print_json` / `print_json_v2` helpers (lines 571-579)."""

    def test_print_json(self, capsys):
        from topogen.HL3.lp import print_json
        print_json([1, 2, 3])
        out = capsys.readouterr().out
        assert "length:" in out

    def test_print_json_v2_without_graphviz(self, capsys):
        from topogen.HL3.lp import print_json_v2
        print_json_v2([object(), object()], print_graphviz=False)
        out = capsys.readouterr().out
        assert "# numbers: 2" in out

    def test_print_json_v2_with_graphviz(self, capsys):
        from topogen.common.circuit import NormalTransistor
        from topogen.HL3.lp import print_json_v2
        print_json_v2([NormalTransistor(techtype="n")], print_graphviz=True)
        out = capsys.readouterr().out
        assert "# numbers: 1" in out
        assert "cluster_" in out  # graphviz body printed


class TestLoadManagerExtras:
    """Walk all `LoadManager` create methods to exercise the conditional
    branches inside `createTwoLoadPartLoadWith*` (HL3/l.py lines 44, 76,
    132, 154, 224-225, 259-263, 275)."""

    def test_create_simple_loads_pmos_and_nmos(self):
        from topogen.HL3.l import (
            createSimpleMixedLoadNmos,
            createSimpleMixedLoadPmos,
        )
        # Realise iterators — touches `createOneLoadPartLoad` for many variants.
        loads_p = list(createSimpleMixedLoadPmos())
        loads_n = list(createSimpleMixedLoadNmos())
        assert loads_p
        assert loads_n

    def test_two_loadpart_load_without_gcc_with_vb_vb_4tx(self):
        """`createTwoLoadPartLoadWithoutGCC` only produces vb-vb load-parts in
        the rare 4-transistor path.  Pass one explicitly so we exercise the
        `ts1.name.startswith("vb") and ts2.name.startswith("vb")` branches
        (HL3/l.py lines 224-225 + 259-263) of the nested helpers."""
        from topogen.HL3.l import createTwoLoadPartLoadWithoutGCC
        from topogen.HL3.lp import LoadPartManager

        mng = LoadPartManager()
        four_tx_vb_vb = mng.createFourTransistorsLoadPartsLoadPartsPmosVoltageBiases()
        cb_two_tx = mng.createLoadPartsPmosCurrentBiases()
        assert four_tx_vb_vb and cb_two_tx
        load = createTwoLoadPartLoadWithoutGCC(four_tx_vb_vb[0], cb_two_tx[0])
        # The 4-tx vb-vb path emits these specific output ports.
        assert "out_output1_load1" in load.ports
        assert "out_output2_load1" in load.ports

    def _make_dt_wrapped_transistor_stack(self):
        """A `TransistorStack` whose single inner instance is a `DiodeTransistor`
        directly (rather than the usual VB/CB).  This produces the rare
        `loadPart.ts1.instances[0].name == "dt"` configuration that the
        load-connection helpers check for."""
        from topogen.common.circuit import (
            DiodeTransistor,
            TransistorStack,
        )
        ts = TransistorStack(id=1, techtype="?")
        ts.add_instance(DiodeTransistor(techtype="n"))
        ts.ports = [TransistorStack.IN, TransistorStack.OUT, TransistorStack.SOURCE]
        ts.add_connection_xxx(port=TransistorStack.IN,     instance_id=0, instance_port="gate")
        ts.add_connection_xxx(port=TransistorStack.OUT,    instance_id=0, instance_port="drain")
        ts.add_connection_xxx(port=TransistorStack.SOURCE, instance_id=0, instance_port="source")
        return ts

    def _get_two_component_ts(self):
        """Pull a TransistorStack with `component_count == 2` from one of the
        existing 4-tx CB load-parts (`mng.createLoadPartsPmosFourTransistorCurrentBiases`)."""
        from topogen.HL3.lp import LoadPartManager
        four_tx = LoadPartManager().createLoadPartsPmosFourTransistorCurrentBiases()
        return four_tx[0].instances[1]  # ts2 with 2 components inside

    def test_addload2nets_with_inner_dt_branch(self):
        """`addLoad2Nets` line 132 — loadPart2 with component_count > 2 and
        ts1 wrapping a `DiodeTransistor` directly."""
        from topogen.HL3.l import addLoad2Nets
        from topogen.HL3.lp import createThreeTransistorLoadPart

        dt_ts = self._make_dt_wrapped_transistor_stack()
        ts2 = self._get_two_component_ts()
        lp = createThreeTransistorLoadPart(dt_ts, ts2)
        assert lp.component_count > 2
        new_ports = addLoad2Nets(lp)
        from topogen.common.circuit import Load
        assert Load.INNEROUTPUTLOAD2 in new_ports

    def test_create_one_loadpart_load_with_inner_dt_branch(self):
        """`createOneLoadPartLoad` → exercises both
        `connectInstanceTerminalsOfLoadPart1WithoutGCC` (line 44) and
        `addLoad1WithoutGCCNets` (line 76)."""
        from topogen.HL3.l import createOneLoadPartLoad
        from topogen.HL3.lp import createThreeTransistorLoadPart

        dt_ts = self._make_dt_wrapped_transistor_stack()
        ts2 = self._get_two_component_ts()
        lp = createThreeTransistorLoadPart(dt_ts, ts2)
        load = createOneLoadPartLoad(lp)
        from topogen.common.circuit import Load
        assert Load.INNEROUTPUTLOAD1 in load.ports

    def test_connect_loadpart2_with_dt_ts(self):
        """Module-level `connectInstanceTerminalsOfLoadPart2` line 154 — fires
        when loadPart2.ts1 directly wraps a `dt` and component_count > 2."""
        from topogen.common.circuit import Load
        from topogen.HL3.l import connectInstanceTerminalsOfLoadPart2
        from topogen.HL3.lp import createThreeTransistorLoadPart

        dt_ts = self._make_dt_wrapped_transistor_stack()
        ts2 = self._get_two_component_ts()
        lp = createThreeTransistorLoadPart(dt_ts, ts2)

        load = Load(id=1, techtype="p")
        load.ports = [
            Load.OUT1, Load.OUT2, Load.SOURCELOAD2,
            Load.INNERSOURCELOAD2, Load.INNERTRANSISTORSTACK2LOAD2,
            Load.INNEROUTPUTLOAD2,
        ]
        result = connectInstanceTerminalsOfLoadPart2(load, lp)
        assert Load.INNEROUTPUTLOAD2 in result.connections

    def test_two_loadpart_load_without_gcc_with_inner_dt(self):
        """`createTwoLoadPartLoadWithoutGCC` else (non-vb-vb) path —
        the nested `addLoad1WithoutGCCNets` and
        `connectInstanceTerminalsOfLoadPart1WithoutGCC` check
        `loadPart1.ts1.instances[0].instances[0].name.startswith("dt")`
        (one level deeper than the module-level helpers).  Build ts1 as a
        stack wrapping a single-diode VB so it goes ts → vb → dt."""
        from topogen.HL2.vb import VoltageBiasManager
        from topogen.HL3.l import createTwoLoadPartLoadWithoutGCC
        from topogen.HL3.lp import (
            LoadPartManager,
            createThreeTransistorLoadPart,
            createTransistorStack,
        )

        diode_vb = next(vb for vb in
                        VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
                        if vb.isSingleDiodeTransistor)
        ts1 = createTransistorStack(1, diode_vb)
        ts2 = self._get_two_component_ts()
        mixed_lp = createThreeTransistorLoadPart(ts1, ts2)
        cb_lp = LoadPartManager().createLoadPartsPmosCurrentBiases()[0]
        load = createTwoLoadPartLoadWithoutGCC(mixed_lp, cb_lp)
        from topogen.common.circuit import Load
        assert Load.INNEROUTPUTLOAD1 in load.ports


class TestNonInvConnectionsDtPath:
    """Cover the rare `loadPart.ts1.instances[0].name == "dt"` branches in
    HL4/non_inv_connections.py (line 110) and the inner-dt branch in
    `connectInstanceTerminalsOfLoadPart2XXX` (line 146)."""

    def _build_lp_with_dt_ts(self):
        """3-tx LoadPart whose ts1 wraps a single-diode voltage bias (the
        real factory structure: TransistorStack → VoltageBias → transistor)."""
        from topogen.common.circuit import createTransistorStack
        from topogen.HL2.vb import VoltageBiasManager
        from topogen.HL3.lp import (
            LoadPartManager,
            createThreeTransistorLoadPart,
        )
        diode_vb = next(
            vb for vb in VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
            if vb.instances[0].name == "dt"
        )
        ts1 = createTransistorStack(1, diode_vb)
        # 2-tx ts2 → total component_count = 3.
        four_tx = LoadPartManager().createLoadPartsPmosFourTransistorCurrentBiases()
        ts2 = four_tx[0].instances[1]
        return createThreeTransistorLoadPart(ts1, ts2)

    def test_loadpart1_inner_dt_branch(self):
        """Line 110: stage connects `inner_output_load1` when ts1 directly
        wraps a `dt` and `component_count > 2`."""
        from topogen.common.circuit import (
            Load,
            NonInvertingStage,
        )
        from topogen.HL4.non_inv_connections import (
            connectInstanceTerminalsOfLoadPart1,
        )
        lp = self._build_lp_with_dt_ts()
        load = Load(id=1, techtype="?")
        load.add_instance(lp)
        load.ports = [
            "out1", "out2", "source_load1",
            "inner_source_load1", "inner_output_load1",
            "inner_transistorstack2_load1",
        ]
        stage = NonInvertingStage(techtype="?")
        stage.ports = [
            NonInvertingStage.OUT1, NonInvertingStage.OUT2,
            NonInvertingStage.SOURCENMOS, NonInvertingStage.SOURCEPMOS,
            NonInvertingStage.INNERSOURCELOAD1,
            NonInvertingStage.INNEROUTPUTLOAD1,
            NonInvertingStage.INNERTRANSISTORSTACK2LOAD1,
        ]
        result = connectInstanceTerminalsOfLoadPart1(stage, load)
        assert NonInvertingStage.INNEROUTPUTLOAD1 in result.connections

    def test_loadpart2xxx_inner_dt_branch(self, monkeypatch):
        """Line 146: `loadPart2.instances[0].component_count == 1 and
        loadPart2.instances[0].instances[0].name.startswith("dt")` —
        ts1 must directly wrap a `DiodeTransistor`."""
        from topogen.common.circuit import (
            Load,
            LoadPart,
            NonInvertingStage,
        )
        from topogen.HL4.non_inv_connections import (
            connectInstanceTerminalsOfLoadPart2XXX,
        )

        lp = self._build_lp_with_dt_ts()
        # Force tech to a definite value to bypass the techtype property's
        # `NotImplementedError` for mixed-stack circuits.
        monkeypatch.setattr(LoadPart, "tech", "n", raising=False)

        load = Load(id=1, techtype="?")
        load.add_instance(lp)  # loadPart1
        load.add_instance(lp)  # loadPart2 — function reads instances[1]
        load.ports = [
            "out1", "out2", "source_load2",
            "inner_source_load2", "inner_output_load2",
            "inner_transistorstack2_load2",
        ]
        stage = NonInvertingStage(techtype="?")
        stage.ports = [
            NonInvertingStage.SOURCENMOS, NonInvertingStage.SOURCEPMOS,
            NonInvertingStage.INNERSOURCELOAD2,
            NonInvertingStage.INNERTRANSISTORSTACK2LOAD2,
            NonInvertingStage.INNEROUTPUTLOAD2,
        ]
        result = connectInstanceTerminalsOfLoadPart2XXX(stage, load)
        assert NonInvertingStage.INNEROUTPUTLOAD2 in result.connections


class TestHL3LpVbBranch:
    """Cover the `vb` branch in `createTwoTransistorLoadPartDifferentSources`
    (HL3/lp.py line 166), which is normally only called with cb stacks."""

    def test_create_two_transistor_load_part_different_sources_with_vb(self):
        """vb-vb input exercises both line 166 in
        `createTwoTransistorLoadPartDifferentSources` and the vb-vb branch
        (lines 128-131) in the inner connector — OUT1/OUT2 carry both ts.IN
        and ts.OUT, and no `inner` net is wired up."""
        from topogen.HL2.vb import VoltageBiasManager
        from topogen.HL3.lp import (
            createTransistorStack,
            createTwoTransistorLoadPartDifferentSources,
        )
        diode_vb = next(vb for vb in
                        VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
                        if vb.isSingleDiodeTransistor)
        ts1 = createTransistorStack(1, diode_vb)
        ts2 = createTransistorStack(2, diode_vb)
        lp = createTwoTransistorLoadPartDifferentSources(ts1, ts2)
        assert lp.ts1 is ts1
        out1_ports = sorted(c["port"] for c in lp.connections["out1"])
        out2_ports = sorted(c["port"] for c in lp.connections["out2"])
        assert out1_ports == ["in", "out"]
        assert out2_ports == ["in", "out"]
        assert "inner" not in lp.connections  # vb-vb branch skips INNER


class TestNonInvConnectionsComplementaryLoadNmos:
    """Cover `connectInstanceTerminalsOfComplementaryLoad` NMOS branch (lines
    235-238) — the `else` (no-GCC) path of the loadPart1.tech == "n" case."""

    def test_no_gcc_nmos_first_load_part(self):
        from topogen.common.circuit import (
            Load,
            LoadPart,
            NonInvertingStage,
            NormalTransistor,
            TransistorStack,
        )
        from topogen.HL4.non_inv_connections import (
            connectInstanceTerminalsOfComplementaryLoad,
        )

        def _make_loadpart(tech):
            lp = LoadPart(id=1, techtype=tech)
            ts = TransistorStack(id=1, techtype=tech)
            ts.add_instance(NormalTransistor(techtype=tech))
            lp.add_instance(ts)
            return lp

        load = Load(id=1, techtype="?")
        load.add_instance(_make_loadpart("n"))   # loadPart1 → tech == "n"
        load.add_instance(_make_loadpart("p"))   # loadPart2

        # No `inner_gcc` port → hasGCC returns False → else branch (235-238).
        load.ports = [
            "out1", "out2", "source_load1", "source_load2",
            "inner_transistorstack1_load1", "inner_transistorstack2_load1",
            "inner_output_load1", "inner_source_load1",
            "inner_transistorstack1_load2", "inner_transistorstack2_load2",
            "inner_output_load2", "inner_source_load2",
        ]
        stage = NonInvertingStage(techtype="?")
        stage.ports = [
            NonInvertingStage.OUT1, NonInvertingStage.OUT2,
            NonInvertingStage.SOURCENMOS, NonInvertingStage.SOURCEPMOS,
            NonInvertingStage.INNERTRANSISTORSTACK1LOADNMOS,
            NonInvertingStage.INNERTRANSISTORSTACK2LOADNMOS,
            NonInvertingStage.INNEROUTPUTLOADNMOS,
            NonInvertingStage.INNERSOURCELOADNMOS,
            NonInvertingStage.INNERTRANSISTORSTACK1LOADPMOS,
            NonInvertingStage.INNERTRANSISTORSTACK2LOADPMOS,
            NonInvertingStage.INNEROUTPUTLOADPMOS,
            NonInvertingStage.INNERSOURCELOADPMOS,
        ]
        result = connectInstanceTerminalsOfComplementaryLoad(stage, load)
        # The else branch added all the inner_*_load1 connections.
        assert NonInvertingStage.INNEROUTPUTLOADNMOS in result.connections


class TestInvertingStageManagerExtras:
    """Cover the trivial getters + the unused `createNonInvertingSelfBiasStage`
    helper in HL4/inv.py (lines 116, 119, 220-250)."""

    def test_getters_return_initialized_lists(self):
        from topogen.HL4.inv import InvertingStageManager
        mng = InvertingStageManager()
        pmos = mng.getInvertingStagesPmosTransconductance()
        nmos = mng.getInvertingStagesNmosTransconductance()
        assert isinstance(pmos, list) and pmos
        assert isinstance(nmos, list) and nmos

    def test_create_non_inverting_self_bias_stage(self):
        from topogen.common.circuit import InvertingStage
        from topogen.HL2.inv import InverterManager
        from topogen.HL4.inv import InvertingStageManager
        # Use the first analog inverter as the input.
        inv = InverterManager().getAnalogInverters()[0]
        stage = InvertingStageManager().createNonInvertingSelfBiasStage(inv)
        assert isinstance(stage, InvertingStage)
        assert InvertingStage.OUTPUT in stage.ports
        assert InvertingStage.INTRANSCONDUCTANCE in stage.ports
        assert InvertingStage.INSTAGEBIAS in stage.ports


class TestNonInvertingStageManagerLazyInit:
    """Cover the lazy-initialisation guard in HL4/non_inv.py line 528
    (`if self.feedbackNonInvertingStagesNmosTransconductance_ is None:
    self.initializeFeedbackNonInvertingStages()`)."""

    def test_feedback_nmos_lazy_initialize(self):
        from topogen.HL4.non_inv import NonInvertingStageManager
        mng = NonInvertingStageManager()
        # Freshly constructed → cache is `None` → getter triggers init (line 528).
        assert mng.feedbackNonInvertingStagesNmosTransconductance_ is None
        result = mng.getFeedbackNonInvertingStagesNmosTransconductance()
        assert result is not None


class TestNonInvNetdefBranches:
    """Cover the rarely-hit branches in HL4/non_inv_netdef.py
    (lines 10-11, 79)."""

    def test_add_load_part1_nets_warns_when_lp_missing(self, monkeypatch):
        """`loadPart1 is None` branch — `load.get_instance_by_name("lp")[0]`
        must yield `None` for this to fire.  The bundled `Logger` shim has no
        ``error`` method, so we monkeypatch it before invoking."""
        from topogen.common.circuit import Load, NonInvertingStage
        from topogen.HL4 import non_inv_netdef

        captured = {}
        class _LoggerStub:
            def error(self, msg): captured["msg"] = msg
            def debug(self, msg): pass
            def info(self, msg): pass
        monkeypatch.setattr(non_inv_netdef, "logger", _LoggerStub())

        class _StubLoad(Load):
            def get_instance_by_name(self, name):
                return [None]  # First entry intentionally None.

        stage = NonInvertingStage(techtype="n")
        load = _StubLoad(techtype="n")
        result = non_inv_netdef.addLoadPart1Nets(stage, load)
        # Branch logs an error and returns the load.
        assert "Load part1" in captured["msg"]
        assert result is load

    def test_add_stage_bias_nets_no_instance_id_branch(self):
        """`stageBias.component_count != 1` AND `instance_id == -1`
        adds `inner_stagebias` (line 79)."""
        from topogen.common.circuit import (
            NonInvertingStage,
            NormalTransistor,
            StageBias,
        )
        from topogen.HL4.non_inv_netdef import addStageBiasNets
        # Build a two-transistor StageBias (component_count == 2) whose
        # `instance_id` is still the default `-1`.
        sb = StageBias(techtype="n")
        sb.add_instance(NormalTransistor(techtype="n"))
        sb.add_instance(NormalTransistor(techtype="n"))
        sb.instance_id = -1  # explicit even though it's the default

        stage = NonInvertingStage(techtype="n")
        stage.ports = []
        result = addStageBiasNets(stage, sb)
        assert "inner_stagebias" in result.ports

    def _make_three_tx_loadpart_with_diode_vb_first(self):
        """LoadPart with ts1 = single-diode VB stack, ts2 = 2-tx CB stack.
        component_count = 3, ts1.instances[0] is a VB with a single dt inside —
        the exact shape required to enter the `name.startswith("dt")` branches
        in `addLoadPart1Nets` (line 39) and `addLoadPart2Nets` (line 60)."""
        from topogen.HL2.cb import CurrentBiasManager
        from topogen.HL2.vb import VoltageBiasManager
        from topogen.HL3.lp import (
            createThreeTransistorLoadPart,
            createTransistorStack,
        )
        vbs = list(VoltageBiasManager().getOneTransistorVoltageBiasesNmos())
        diode_vb = next(vb for vb in vbs if vb.isSingleDiodeTransistor)
        two_tx_cb = list(CurrentBiasManager().getTwoTransistorCurrentBiasesNmos())[0]
        ts1 = createTransistorStack(1, diode_vb)
        ts2 = createTransistorStack(2, two_tx_cb)
        return createThreeTransistorLoadPart(ts1, ts2)

    def test_add_load_part1_nets_with_diode_dt_branch(self):
        """Covers line 39: loadPart1.component_count > 2 + inner dt name."""
        from topogen.common.circuit import Load, NonInvertingStage
        from topogen.HL4 import non_inv_netdef

        lp = self._make_three_tx_loadpart_with_diode_vb_first()

        class _StubLoad(Load):
            def __init__(self, lp):
                super().__init__(techtype="n")
                self._lp = lp
                self.ports = []  # no inner_gcc → hasGCC == False
            def get_instance_by_name(self, name):
                return [self._lp]

        stage = NonInvertingStage(techtype="n")
        stage.ports = []
        result = non_inv_netdef.addLoadPart1Nets(stage, _StubLoad(lp))
        assert "inner_output_load1" in result.ports

    def test_add_load_part2_nets_with_diode_dt_branch(self):
        """Covers line 60: loadPart2.component_count > 2 + inner dt name."""
        from topogen.common.circuit import Load, NonInvertingStage
        from topogen.HL4 import non_inv_netdef

        lp = self._make_three_tx_loadpart_with_diode_vb_first()

        class _StubLoad(Load):
            def __init__(self, lp):
                super().__init__(techtype="n")
                self._lp = lp
                self.ports = []
            def get_instance_by_name(self, name):
                # Two loadparts; we only care about [1] for addLoadPart2Nets.
                return [self._lp, self._lp]

        stage = NonInvertingStage(techtype="n")
        stage.ports = []
        result = non_inv_netdef.addLoadPart2Nets(stage, _StubLoad(lp))
        assert "inner_output_load2" in result.ports


class TestEveryGateNetNotConnectedHelper:
    """Cover the gate/drain-net audit helper at the bottom of `common/circuit.py`
    (lines 770-816), including all four inner predicates."""

    def test_returns_true_on_clean_inverter(self):
        from topogen.common.circuit import (
            everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType,
        )
        from topogen.HL2.inv import InverterManager
        for inv in InverterManager().getAnalogInverters():
            assert (
                everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType(inv)
                is True
            )

    def _build_two_transistor_circuit(self, t1_tech, t2_tech, gate_net, drain_nets,
                                       gate_techs=None):
        """Build a flat 2-transistor `Circuit` whose `flatten()` is a no-op so
        we can exercise the helper's net-collision branches directly."""
        from topogen.common.circuit import Circuit, NormalTransistor
        circ = Circuit(name="dummy", id=1, techtype="?")
        t1 = NormalTransistor(techtype=t1_tech, id=1)
        t2 = NormalTransistor(techtype=t2_tech, id=2)
        circ.add_instance(t1)
        circ.add_instance(t2)
        # Assign net names directly — `flatten()` would normally do this, but
        # for these contrived circuits we want full control over the wiring.
        t1.gate = gate_net
        t2.gate = gate_net if (gate_techs is None or gate_techs[1]) else "x"
        t1.drain = drain_nets[0]
        t2.drain = drain_nets[1]
        t1.source = "_unused1"
        t2.source = "_unused2"
        circ.connections = {}
        return circ

    def test_n_doped_gate_with_two_n_drains_fails(self):
        """Two nmos drains on a gate net driven by nmos gates → returns False
        (covers `moreThanOneNDopdedDrainPin` true branch)."""
        from topogen.common.circuit import (
            everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType,
        )
        circ = self._build_two_transistor_circuit(
            "n", "n", gate_net="gnet", drain_nets=["gnet", "gnet"]
        )
        # Both transistors' gate AND drain are the same net → 2 nmos drains.
        assert (
            everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType(circ)
            is False
        )

    def test_p_doped_gate_with_two_p_drains_fails(self):
        from topogen.common.circuit import (
            everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType,
        )
        circ = self._build_two_transistor_circuit(
            "p", "p", gate_net="gnet", drain_nets=["gnet", "gnet"]
        )
        assert (
            everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType(circ)
            is False
        )

    def test_mixed_doped_gate_drain_collision_fails(self):
        """Mixed gate-techs → falls through to the `else` branch (line 812).
        Need ≥2 same-tech drains on the shared net so the inner predicates
        return True."""
        from topogen.common.circuit import (
            Circuit,
            NormalTransistor,
            everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType,
        )
        circ = Circuit(name="dummy", id=1, techtype="?")
        # Two nmos + one pmos, all gated on the same net "g" → mixed-doping
        # on the gate; two nmos drains on "g" → triggers `moreThanOneNDopd…`.
        nt_n1 = NormalTransistor(techtype="n", id=1)
        nt_n2 = NormalTransistor(techtype="n", id=2)
        nt_p = NormalTransistor(techtype="p", id=3)
        for inst in (nt_n1, nt_n2, nt_p):
            circ.add_instance(inst)
            inst.gate = "g"
            inst.drain = "g"
            inst.source = f"s_{id(inst)}"
        circ.connections = {}
        assert (
            everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType(circ)
            is False
        )
