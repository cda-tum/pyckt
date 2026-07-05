"""acst-faithful circuit partitioner.

A port of acst's ``Partitioning`` (``Partitioning/src/Partitioning.cpp``)
operating on pyckt's recognition hierarchy (now matching acst after the §8c
recogniser rewrite) plus the :class:`~partitioning.net_index.StructureNetIndex`
that recovers shared-net connectivity.

It produces the acst gm-path / Part model (:mod:`partitioning.acst_parts`):
``firstStage`` / ``primarySecondStage`` / ``secondarySecondStage`` gm parts,
load parts, bias parts, capacitances, and undefined parts — consumed by the
acst-format partition writer.  pyckt's native :class:`Partitioner` is untouched.

C++ ref: ``Partitioning::compute`` and its helpers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from .acst_parts import (
    AcstPartitionResult,
    BiasPart,
    CapacitancePart,
    LoadPart,
    TransconductancePart,
    UndefinedPart,
)
from .net_index import StructureNetIndex

if TYPE_CHECKING:
    from ckt_io.circuit_info_parser import CircuitParameter
    from recognition.model import Structure, StructureCircuits

_DP = "MosfetDifferentialPair"
_NA = "MosfetNormalArray"
_DA = "MosfetDiodeArray"
_VREF1 = "MosfetVoltageReference1"
# inverter structure names checked as second-stage transconductances, in
# acst's exact partitioningSecondStage order (Partitioning.cpp:235-253)
_INVERTERS = (
    "MosfetAnalogInverter",
    "MosfetCascodedAnalogInverter",
    "MosfetCascodeAnalogInverterNmosCurrentMirrorLoad",
    "MosfetCascodeAnalogInverterPmosCurrentMirrorLoad",
    "MosfetCascodeAnalogInverterNmosDiodeTransistor",
    "MosfetCascodeAnalogInverterPmosDiodeTransistor",
    "MosfetCascodeAnalogInverterNmosDiodeTransistorPmosCurrentMirrorLoad",
    "MosfetCascodeAnalogInverterPmosDiodeTransistorNmosCurrentMirrorLoad",
    "MosfetCascodedPMOSAnalogInverter",
    "MosfetCascodedNMOSAnalogInverter",
    "MosfetCascodePMOSAnalogInverterCurrentMirrorLoad",
    "MosfetCascodeNMOSAnalogInverterCurrentMirrorLoad",
    "MosfetCascodePMOSAnalogInverterOneDiodeTransistor",
    "MosfetCascodeNMOSAnalogInverterOneDiodeTransistor",
    "MosfetCascodeAnalogInverterTwoCurrentMirrorLoads",
)

# acst isCurrentMirror: an exact name list (MosfetCurrentMirrorLoad and
# MosfetCascodePair are NOT current mirrors here)
_CURRENT_MIRRORS = frozenset((
    "MosfetSimpleCurrentMirror",
    "MosfetCascodeCurrentMirror",
    "MosfetImprovedWilsonCurrentMirror",
    "MosfetWideSwingCascodeCurrentMirror",
    "MosfetWideSwingCurrentMirror",
    "MosfetFourTransistorCurrentMirror",
    "MosfetWilsonCurrentMirror",
))


class AcstPartitioner:
    """Partition a recognition result the way acst does."""

    def __init__(self, circuit_params: "CircuitParameter") -> None:
        self._params = circuit_params
        self._output_net = circuit_params.output_net

    # ── entry point ───────────────────────────────────────────────────

    def partition(self, sc: "StructureCircuits") -> AcstPartitionResult:
        self._sc = sc
        self._idx = StructureNetIndex.build(sc)
        self._result = AcstPartitionResult()

        self._partition_differential_pairs()
        if self._result.transconductance_parts:
            self._partition_bias_parts_of_diff_pairs()
            self._partition_load_parts_of_diff_pairs()
        self._partition_second_stage()
        self._partition_third_stage()
        self._recognize_second_second_stage()

        first = self._result.get_first_stage()
        if first is not None:
            if self._result.has_secondary_second_stage():
                first.first_stage_type = "symmetrical"
            elif not first.first_stage_type:
                first.first_stage_type = "simple"

        self._partition_remaining_current_mirrors()
        self._partition_voltage_reference1()
        self._classify_diode_arrays()
        self._partition_capacitances()
        self._create_undefined_parts()

        logger.info(
            "acst partition: {} gm, {} load, {} bias, {} cap, {} undef",
            len(self._result.transconductance_parts), len(self._result.load_parts),
            len(self._result.bias_parts), len(self._result.capacitance_parts),
            len(self._result.undefined_parts),
        )
        return self._result

    # ── structure lookup helpers ──────────────────────────────────────

    def _find(self, name: str) -> list["Structure"]:
        out: list[Structure] = []
        for lvl in self._sc.hierarchy_levels:
            out.extend(s for s in self._sc.get_level(lvl).structures if s.name == name)
        return out

    @staticmethod
    def _is_current_mirror(s: "Structure") -> bool:
        return s.name in _CURRENT_MIRRORS

    def _array_drain_net(self, array: "Structure") -> str | None:
        return self._idx.net_name(array, "Drain")

    # ── step 1: differential pairs → first stage ──────────────────────

    def _partition_differential_pairs(self) -> None:
        """Port of ``Partitioning::partitioningDifferentialPairs``.

        A lone diff pair is the first stage (with its parent's sibling
        recorded as the cascode *helper structure*, typing it telescopic /
        foldedCascode); diff pairs sharing both gate nets are either the two
        halves of a complementary first stage (different tech) or the
        common-mode feedback sensing pairs (same tech), grouped into one part.
        """
        for dp in self._find(_DP):
            if self._result.structure_already_classified(dp):
                continue
            tp = TransconductancePart(self._result.next_id("trans"))
            tp.add_main_structure(dp, self._result)
            self._result.add_transconductance_part(tp)

            g1 = self._idx.net_name(dp, "Input1")
            g2 = self._idx.net_name(dp, "Input2")

            def _on(net: str | None, pin: str) -> list:
                # acst does NOT exclude dp itself: its own pins count toward
                # the shared-gate threshold (findConnectedStructures is
                # unfiltered in partitioningDifferentialPairs)
                if not net:
                    return []
                return list(self._idx.connected_via(net, _DP, pin))

            l11, l21 = _on(g1, "Input1"), _on(g1, "Input2")
            l12, l22 = _on(g2, "Input1"), _on(g2, "Input2")

            if len(l11) + len(l21) + len(l12) + len(l22) > 2:
                same_sets = (
                    {id(x) for x in l11} == {id(x) for x in l22}
                    and {id(x) for x in l21} == {id(x) for x in l12}
                )
                if same_sets:
                    other = next(
                        (x for x in (*l11, *l21) if x is not dp), None
                    )
                    if other is not None and other.tech_type != dp.tech_type:
                        tp.type = "firstStage"
                        tp.first_stage_type = "complementary"
                    else:
                        tp.type = "feedBack"
                else:
                    tp.type = "feedBack"
                for group in (l11, l21, l12, l22):
                    for member in group:
                        if member is not dp:
                            tp.add_main_structure(member, self._result)
            else:
                tp.type = "firstStage"
                if dp.has_parent:
                    parent = dp.parents[0]
                    helper = getattr(parent, "child2", None)
                    if helper is not None:
                        tp.helper_structure = helper
                        tp.first_stage_type = (
                            "telescopic"
                            if helper.tech_type == dp.tech_type
                            else "foldedCascode"
                        )

    # ── step 2: bias of the diff pair (tail current) ──────────────────

    def _partition_bias_parts_of_diff_pairs(self) -> None:
        for tp in list(self._result.transconductance_parts):
            for main in list(tp.main_structures):
                self._initialize_bias_part_of_diff_pair(main)

    def _initialize_bias_part_of_diff_pair(self, dp: "Structure") -> None:
        source_net = self._idx.net_name(dp, "Source")
        if source_net is None:
            return
        bias = BiasPart(self._result.next_id("bias"))
        self._find_with_drain_connected(source_net, dp, bias, None,
                                        dp.tech_type)
        if bias.has_main_structures:
            tp = self._result.get_transconductance_part(dp)
            if tp is not None:
                bias.add_biased_part(tp)
                tp.bias_parts.append(bias)
            bias.type = "currentBias"
            self._result.add_bias_part(bias)

    # ── step 3: load parts of the diff pair ───────────────────────────

    def _partition_load_parts_of_diff_pairs(self) -> None:
        # feedback parts first (acst ordering), then the rest
        order = ([t for t in self._result.transconductance_parts if t.is_feedback()]
                 + [t for t in self._result.transconductance_parts if not t.is_feedback()])
        for tp in order:
            for main in list(tp.main_structures):
                self._initialize_load_parts_of_diff_pair(main)

    def _initialize_load_parts_of_diff_pair(self, dp: "Structure") -> None:
        """Port of ``Partitioning::initializeLoadPartsOfDifferentialPair``.

        Walks drain-connected arrays from both pair outputs into same-/
        opposite-tech load parts; a cascoded first stage additionally folds
        its helper pair's arrays into the matching load part (marking the
        folded pair's current biases) and recurses from the helper's own
        drains; each surviving load part gets its gate-connected voltage
        biases attached (``findBiasOfLoadPart``).
        """
        arrays = dp.array_children
        if len(arrays) < 2:
            return
        load_same = LoadPart(self._result.next_id("load"))
        load_opp = LoadPart(self._result.next_id("load"))
        for arr in arrays[:2]:
            drain = self._array_drain_net(arr)
            if drain is not None:
                self._find_with_drain_connected(drain, arr, load_same, load_opp,
                                                dp.tech_type)

        tp = self._result.get_transconductance_part(dp)
        if (
            dp.name == _DP
            and dp.has_parent
            and tp is not None
            and tp.first_stage_type != "complementary"
            and tp.helper_structure is not None
        ):
            cascoded = tp.helper_structure
            target = (load_same if cascoded.tech_type == dp.tech_type
                      else load_opp)
            target.cascoded_pair = cascoded
            cascode_arrays = cascoded.array_children[:2]
            for ca in cascode_arrays:
                target.add_main_structure(ca, self._result)
            if dp.parents[0].name == "MosfetFoldedCascodeDifferentialPair":
                for ms in target.main_structures:
                    if ms not in cascode_arrays:
                        target.current_biases_of_folded_pair.append(ms)
            self._initialize_load_parts_of_diff_pair(cascoded)
        elif tp is not None and tp.first_stage_type == "complementary":
            self._find_structure_between_dp_and_first_stage_output(dp, load_opp)

        # attach to the (parent's) transconductance part and record biases
        owner = None
        if dp.has_parent:
            owner = self._result.get_transconductance_part(dp.parents[0])
        if owner is None:
            owner = self._result.get_transconductance_part(dp)
        for lp in (load_same, load_opp):
            if lp.has_main_structures:
                if owner is not None:
                    owner.load_parts.append(lp)
                self._result.add_load_part(lp)
                self._find_bias_of_load_part(lp)

    def _find_structure_between_dp_and_first_stage_output(
        self, dp: "Structure", load_opp: LoadPart
    ) -> None:
        """Port of ``findStructureBetweenDifferentialPairAndOutputFirstStage``:
        the complementary first stage's folding devices are the opposite-tech
        structures on the pair outputs whose sources are off-rail."""
        for arr in dp.array_children[:2]:
            drain = self._array_drain_net(arr)
            if drain is None:
                continue
            for cs in self._idx.connected_structures(drain):
                if cs.is_pair or cs.tech_type == dp.tech_type:
                    continue
                source = self._idx.net_name(cs, "Source")
                if source is not None and not self._idx.is_supply(source):
                    load_opp.add_main_structure(cs, self._result)

    def _find_bias_of_load_part(self, load_part: LoadPart) -> None:
        """Port of ``Partitioning::findBiasOfLoadPart``: attach (or create)
        the voltage bias driving each normal-array load gate."""
        for main in list(load_part.main_structures):
            if main.name != _NA:
                continue
            gate_net = self._idx.net_name(main, "Gate")
            if gate_net is None:
                continue
            for cs in self._idx.connected_structures(gate_net):
                if cs is main or cs.is_pair:
                    continue
                if cs.tech_type != main.tech_type:
                    continue
                source_net = self._idx.net_name(cs, "Source")
                drain_net = self._idx.net_name(cs, "Drain")
                if cs.has_parent and self._is_voltage_bias(cs) and \
                        source_net != gate_net:
                    for parent in cs.parents:
                        if self._result.structure_already_classified(cs):
                            existing = self._result.get_part(cs)
                            if isinstance(existing, BiasPart):
                                if existing not in load_part.bias_parts:
                                    load_part.bias_parts.append(existing)
                                if load_part not in existing.biased_parts:
                                    existing.biased_parts.append(load_part)
                            elif (isinstance(existing, LoadPart)
                                  and existing is not load_part
                                  and existing not in load_part.bias_parts):
                                load_part.bias_parts.append(existing)
                        else:
                            vb = BiasPart(self._result.next_id("bias"))
                            vb.type = "voltageBias"
                            owner = (parent if self._is_voltage_bias(parent)
                                     else cs)
                            vb.add_main_structure(owner, self._result)
                            vb.biased_parts.append(load_part)
                            load_part.bias_parts.append(vb)
                            self._result.add_bias_part(vb)
                if self._is_voltage_bias(cs) and drain_net == gate_net:
                    if self._result.structure_already_classified(cs):
                        existing = self._result.get_part(cs)
                        if isinstance(existing, BiasPart):
                            if existing not in load_part.bias_parts:
                                load_part.bias_parts.append(existing)
                            if load_part not in existing.biased_parts:
                                existing.biased_parts.append(load_part)
                    else:
                        vb = BiasPart(self._result.next_id("bias"))
                        vb.type = "voltageBias"
                        vb.add_main_structure(cs, self._result)
                        vb.biased_parts.append(load_part)
                        load_part.bias_parts.append(vb)
                        self._result.add_bias_part(vb)

    # ── shared recursive drain walk (load + bias) ─────────────────────

    def _find_with_drain_connected(
        self, net: str, ref: "Structure",
        part_same, part_opp, ref_tech,
    ) -> None:
        """Port of findWithDrainConnectedLoadStructures / ...Devices.

        Adds array-level structures whose Drain sits on *net* (same/opposite
        tech) and recurses up their Source net while it is not a supply rail.
        acst walks the *array-level* net view, so composite (pair) structures
        never join these parts directly — their arrays do.
        """
        for cs in self._idx.connected_structures(net):
            if cs.is_pair:
                continue
            if self._result.structure_already_classified(cs):
                continue
            if cs is ref or not cs.has_pin("Drain"):
                continue
            if self._idx.net_name(cs, "Drain") != net:
                continue
            source = self._idx.net_name(cs, "Source")
            # acst compares each candidate against the *immediate* reference
            # structure (the recursion's just-added structure), not the
            # original walk root — that is what lets a mirror stack chain
            # (top array -> its diode below) into one load part.
            if part_same is not None and cs.tech_type == ref.tech_type:
                part_same.add_main_structure(cs, self._result)
                if source is not None and not self._idx.is_supply(source):
                    self._find_with_drain_connected(source, cs, part_same, None,
                                                    ref_tech)
            elif part_opp is not None:
                part_opp.add_main_structure(cs, self._result)
                if source is not None and not self._idx.is_supply(source):
                    self._find_with_drain_connected(source, cs, part_opp, None,
                                                    ref_tech)

    # ── step 4: second stage (inverter classifiers) ───────────────────

    def _partition_second_stage(self) -> None:
        for name in self._present_inverters():
            self._classify_inverter(name)
        # the FUBOCO-era library's cascaded non-inverting inverters classify
        # as a whole-composite gm stage after the plain inverters (their
        # inner analog inverter classifies first; the gallery shows both gm
        # parts, e.g. s-1-2/raw/3_7)
        for name in ("MosfetNmosNonInvertingInverter",
                     "MosfetPmosNonInvertingInverter"):
            self._classify_noninverting_inverter(name)

    def _partition_third_stage(self) -> None:
        """Port of ``Partitioning::partitioningThirdStage``: re-run four of
        the inverter classifiers now that second stages exist (an inverter
        sensing a ``primarySecondStage`` output types as ``thirdStage``),
        then the symmetrical-OTA fixup — a ``primarySecondStage`` whose
        supply-sourced gm transistor is gated by an inverter output that
        itself senses the first stage is really a third stage."""
        for name in ("MosfetAnalogInverter",
                     "MosfetCascodedAnalogInverter",
                     "MosfetCascodedPMOSAnalogInverter",
                     "MosfetCascodedNMOSAnalogInverter"):
            self._classify_inverter(name)

        if len(self._result.get_second_stages()) <= 1:
            return
        for stage in list(self._result.get_second_stages()):
            if not stage.is_primary_second_stage():
                continue
            gate_net = None
            for main in stage.main_structures:
                for arr in main.array_children:
                    if arr.name != "MosfetNormalArray":
                        continue
                    src = self._idx.net_name(arr, "Source")
                    if src is not None and self._idx.is_supply(src):
                        gate_net = self._idx.net_name(arr, "Gate")
            if gate_net is None:
                continue
            # acst compares against each *other* second stage, but the check
            # (hasSecondStageOutputConnection) is global over the current
            # second-stage set, re-evaluated after each retype — once a
            # stage is retyped the remaining ones see a smaller set, which
            # is what lets exactly one duplicate stage survive as primary.
            others = [o for o in self._result.get_second_stages()
                      if o is not stage]
            if others and self._has_second_stage_output_connection(gate_net):
                stage.type = "thirdStage"

    # acst hasSecondStageOutputConnection recognises "the output of a second
    # stage" purely structurally: the net must be the Output of a classified
    # inverter (that is not the first stage's load) whose own input senses
    # the first-stage output.  The gallery's acst extends the inverter-name
    # list with the four FUBOCO-era items (the diode inverters and the
    # cascaded non-inverting composites) — s-1-2/raw/5_7 needs the diode
    # inverter, 101_1 the composite.
    _OUTPUT_INVERTERS = frozenset(_INVERTERS) | frozenset((
        "MosfetNmosDiodeAnalogInverter", "MosfetPmosDiodeAnalogInverter",
        "MosfetNmosNonInvertingInverter", "MosfetPmosNonInvertingInverter",
    ))

    def _has_second_stage_output_connection(self, net: str) -> bool:
        first = self._result.get_first_stage()
        # acst skips connected structures whose part isLoadPartOfFirstStage.
        # Its getPart resolves through the composite's first array child; that
        # ordering surfaces a first-stage load there, but pyckt's ordering can
        # surface the first-stage gm of the same composite instead (a
        # structure that also spans the input pair, e.g. s-1-2/raw/5_7's
        # MosfetCascodeAnalogInverterNmosCurrentMirrorLoad = m4,m5,m6,m8).
        # Skip the first stage either way — a genuine downstream inverter
        # output resolves to a second-stage / undefined part.
        first_parts = [first, *first.load_parts] if first is not None else []
        for cs in self._idx.connected_structures(net):
            if not self._result.structure_already_classified(cs):
                continue
            part = self._result.get_part(cs)
            if part is not None and part in first_parts:
                continue
            if cs.name not in self._OUTPUT_INVERTERS:
                continue
            if self._idx.net_name(cs, "Output") != net:
                continue
            if self._inverter_input_senses_first_stage(cs):
                return True
        return False

    def _inverter_input_senses_first_stage(self, inv: "Structure") -> bool:
        """acst ``inputOfInverterIsConnectedToFirstStageOutput``: either
        inverter input net carries the first-stage output, where acst's
        ``hasFirstStageOutputConnection`` general branch accepts a
        MosfetDifferentialPair *or* MosfetGateConnectedCouple with an
        Output1/Output2 pin on the net."""
        for pin in ("InputNMOS1", "InputPMOS1"):
            in_net = self._idx.net_name(inv, pin)
            if in_net is None:
                continue
            for cs in self._idx.connected_structures(in_net):
                if cs.name not in ("MosfetDifferentialPair",
                                   "MosfetGateConnectedCouple"):
                    continue
                if (self._idx.net_name(cs, "Output1") == in_net
                        or self._idx.net_name(cs, "Output2") == in_net):
                    return True
        return False

    def _classify_noninverting_inverter(self, name: str) -> None:
        """Classify a cascaded non-inverting inverter composite as one gm
        part: same sensing-gate logic as ``classifyInverter``, but the whole
        composite is the transconductance and its diode-inverter child the
        stage bias.

        When two composites share the diode-inverter reference (mirror-OTA
        templates like s-1-2/raw/101_1), acst's instance ordering classifies
        the one driving the real stage output first, which then absorbs the
        shared reference and makes the other fully-classified.  pyckt's
        recognition order differs, so defer composites whose Output net is
        itself a first-stage drain net."""
        candidates = self._find(name)
        candidates.sort(
            key=lambda s: self._touches_first_stage_output(
                self._idx.net_name(s, "Output") or "")
        )
        for inv in candidates:
            if self._result.structure_already_classified(inv):
                continue
            if not inv.is_pair:
                continue
            inv_type = ""
            matched = False
            for gate_a, gate_b in (("InputPMOS1", "InputNMOS1"),
                                   ("InputNMOS1", "InputPMOS1")):
                net_a = self._idx.net_name(inv, gate_a)
                net_b = self._idx.net_name(inv, gate_b)
                if net_a is None:
                    continue
                for cs in self._idx.connected_structures(net_a):
                    if not self._result.structure_already_classified(cs):
                        continue
                    part = self._result.get_part(cs)
                    if part is None or not (part.is_transconductance()
                                            or part.is_load()):
                        continue
                    if not self._has_stage_output_net_connection(net_a, part):
                        continue
                    if not (self._has_voltage_bias_output_connection(net_b)
                            or self._only_one_transistor_on_net(net_b)):
                        continue
                    matched = True
                    if (part.is_load()
                            or (part.is_transconductance()
                                and part.is_first_stage())):
                        inv_type = "primarySecondStage"
                    elif (part.is_transconductance()
                          and part.is_primary_second_stage()):
                        inv_type = "thirdStage"
            if matched:
                self._initialize_inverter_stage([inv], inv.child1, inv_type)

    def _present_inverters(self) -> list[str]:
        return [n for n in _INVERTERS if self._find(n)]

    def _classify_inverter(self, inverter_name: str) -> None:
        """Port of ``Partitioning::classifyInverter``: an inverter whose one
        gate senses a stage output (while the other gate is a voltage-bias
        node or single-transistor net) becomes the next gm stage — that gate's
        child is the transconductor, the other child its stage bias.

        Note: acst declares the child numbers *outside* the inverter loop, so
        a matched child assignment leaks into subsequent unmatched inverters
        of the same name (bug-compatible on purpose — the gallery reference
        was produced by this code).
        """
        child_trans = 0
        child_bias = 0
        for inv in self._find(inverter_name):
            if self._result.structure_already_classified(inv):
                continue
            if not inv.is_pair:
                continue
            inv_type = ""
            for gate_a, gate_b, trans_child, bias_child in (
                ("InputPMOS1", "InputNMOS1", 1, 2),
                ("InputNMOS1", "InputPMOS1", 2, 1),
            ):
                net_a = self._idx.net_name(inv, gate_a)
                net_b = self._idx.net_name(inv, gate_b)
                if net_a is None:
                    continue
                for s in self._idx.connected_structures(net_a):
                    if not self._result.structure_already_classified(s):
                        continue
                    part = self._result.get_part(s)
                    if part is None or not (part.is_transconductance() or part.is_load()):
                        continue
                    if not self._has_stage_output_net_connection(net_a, part):
                        continue
                    if not (self._has_voltage_bias_output_connection(net_b)
                            or self._only_one_transistor_on_net(net_b)):
                        continue
                    if inv.get_child(trans_child).name == "MosfetMixedCascodePair2":
                        continue
                    child_trans, child_bias = trans_child, bias_child
                    if (part.is_load()
                            or (part.is_transconductance() and part.is_first_stage())):
                        inv_type = "primarySecondStage"
                    elif (part.is_transconductance()
                          and part.is_primary_second_stage()):
                        inv_type = "thirdStage"
            if child_trans:
                self._initialize_inverter_stage(
                    [inv.get_child(child_trans)],
                    inv.get_child(child_bias),
                    inv_type,
                )

    def _initialize_inverter_stage(
        self, trans_structs: list["Structure"], bias_struc: "Structure",
        inv_type: str,
    ) -> None:
        """Port of ``Partitioning::initializeInverterStage``: create the gm
        part for the transconductor side and classify the stage-bias side —
        a current bias, plus the voltage bias mirrored into it when the bias
        sits under a current mirror (directly or via its pair's arrays)."""
        if any(self._result.structure_already_classified(t) for t in trans_structs):
            return
        tp = TransconductancePart(self._result.next_id("trans"))
        for t in trans_structs:
            tp.add_main_structure(t, self._result)
        tp.type = inv_type
        tp.helper_structure = bias_struc
        self._result.add_transconductance_part(tp)

        def _link_existing(struct, target_part) -> None:
            existing = self._result.get_part(struct)
            if isinstance(existing, BiasPart):
                if target_part not in existing.biased_parts:
                    existing.add_biased_part(target_part)
                    if isinstance(target_part, TransconductancePart):
                        target_part.bias_parts.append(existing)

        def _mirror_reference_bias(mirror, current_bias: BiasPart) -> None:
            child1 = getattr(mirror, "child1", None)
            if child1 is None:
                return
            if not self._result.structure_already_classified(child1):
                vb = BiasPart(self._result.next_id("bias"))
                vb.type = "voltageBias"
                vb.add_main_structure(child1, self._result)
                vb.add_biased_part(current_bias)
                self._result.add_bias_part(vb)
            else:
                _link_existing(child1, current_bias)

        def _direct_mirror_parent(struct):
            for parent in struct.parents:
                if self._is_current_mirror(parent):
                    return parent
            return None

        mirror = _direct_mirror_parent(bias_struc)
        if mirror is not None:
            if not self._result.structure_already_classified(bias_struc):
                bp = BiasPart(self._result.next_id("bias"))
                bp.type = "currentBias"
                bp.add_main_structure(bias_struc, self._result)
                bp.add_biased_part(tp)
                tp.bias_parts.append(bp)
                self._result.add_bias_part(bp)
                _mirror_reference_bias(mirror, bp)
            else:
                _link_existing(bias_struc, tp)
        elif bias_struc.is_pair:
            if not self._result.structure_already_classified(bias_struc):
                bp = BiasPart(self._result.next_id("bias"))
                bp.type = "currentBias"
                bp.add_main_structure(bias_struc, self._result)
                bp.add_biased_part(tp)
                tp.bias_parts.append(bp)
                self._result.add_bias_part(bp)
                for arr in bias_struc.array_children:
                    arr_mirror = _direct_mirror_parent(arr)
                    if arr_mirror is not None:
                        _mirror_reference_bias(arr_mirror, bp)
            else:
                _link_existing(bias_struc, tp)
        else:
            arrays = bias_struc.array_children
            gate = self._idx.net_name(arrays[0], "Gate") if arrays else None
            if self._only_one_transistor_on_net(gate):
                if not self._result.structure_already_classified(bias_struc):
                    bp = BiasPart(self._result.next_id("bias"))
                    bp.type = "currentBias"
                    bp.add_main_structure(bias_struc, self._result)
                    bp.add_biased_part(tp)
                    tp.bias_parts.append(bp)
                    self._result.add_bias_part(bp)

    # ── step 5: symmetrical second-second stage ───────────────────────

    def _recognize_second_second_stage(self) -> None:
        first = self._result.get_first_stage()
        if (not self._result.has_second_stage() or first is None
                or len(first.load_parts) != 1):
            return
        load_part = first.load_parts[0]
        if not self._is_symmetrical_load_part(load_part):
            return
        for main in load_part.main_structures:
            if not main.is_part_of_current_mirror:
                continue
            cm = self._recursive_current_mirror_parent(main)
            if cm is None or not cm.is_pair:
                continue
            # the output leg (child2) is the candidate second-stage gm
            output_leg = cm.child2
            for arr in output_leg.array_children:
                if arr.name != _NA:
                    continue
                if not self._idx.is_supply(self._idx.net_name(arr, "Source") or ""):
                    continue
                drain = self._idx.net_name(arr, "Drain")
                if drain is None:
                    continue
                # acst: pair the supply-sourced leg array with the same-tech
                # NormalArray on its drain → {arrayChild, connectedStruct}
                for cs in self._idx.connected_structures(drain):
                    if cs is arr or cs.name != _NA:
                        continue
                    if cs.tech_type != output_leg.tech_type:
                        continue
                    potential_bias = self._idx.connected_structures(
                        self._idx.net_name(cs, "Drain") or "")
                    bias_struc = self._find_second_second_bias(potential_bias)
                    if bias_struc is None:
                        continue
                    if not self._result.structure_already_classified(output_leg):
                        self._initialize_inverter_stage([arr, cs], bias_struc,
                                                        "secondarySecondStage")
                # fallback: whole leg if no paired array found
                if not self._result.has_secondary_second_stage():
                    drain_structs = self._idx.connected_structures(drain)
                    bias_struc = self._find_second_second_bias(drain_structs)
                    if (bias_struc is not None
                            and not self._result.structure_already_classified(output_leg)):
                        self._initialize_inverter_stage([output_leg], bias_struc,
                                                        "secondarySecondStage")

    def _find_second_second_bias(self, structs: list["Structure"]):
        for s in structs:
            if self._is_voltage_bias(s):
                return s
            for p in s.parents:
                if self._is_voltage_bias(p):
                    return p
        return None

    def _is_symmetrical_load_part(self, load_part: LoadPart) -> bool:
        mains = load_part.main_structures
        if len(mains) == 2:
            ref = None
            equal_names = False
            all_voltage_bias = True
            for m in mains:
                if ref is None:
                    ref = m
                elif ref.name == m.name:
                    equal_names = True
                if not self._is_voltage_bias(m):
                    all_voltage_bias = False
            return all_voltage_bias and equal_names
        return False

    # ── step 6: remaining structures → bias ───────────────────────────

    def _partition_remaining_current_mirrors(self) -> None:
        """Port of ``Partitioning::partitioningRemainingCurrentMirrors``:
        every unconsumed current mirror (any hierarchy level) classifies its
        reference child (child1) as a voltage bias and its output child
        (child2) as a current bias — as *whole* structures, which is how
        composite references like ``MosfetMixedCascodePair1`` become single
        bias parts.  (acst's addBiasedPartTypeVoltageBias /
        addBiasedPartToCurrentBias only add biased-part cross-links, which the
        acst XML comparison does not key on, so they are not ported.)
        """
        for structure in self._all_structures():
            if not self._is_current_mirror(structure) or not structure.is_pair:
                continue
            c1, c2 = structure.child1, structure.child2
            c1_done = self._result.structure_already_classified(c1)
            c2_done = self._result.structure_already_classified(c2)
            if not c1_done and not c2_done:
                vb = BiasPart(self._result.next_id("bias"))
                vb.type = "voltageBias"
                vb.add_main_structure(c1, self._result)
                self._result.add_bias_part(vb)
                cb = BiasPart(self._result.next_id("bias"))
                cb.type = "currentBias"
                cb.add_main_structure(c2, self._result)
                self._result.add_bias_part(cb)
                vb.add_biased_part(cb)
            elif not c2_done:
                cb = BiasPart(self._result.next_id("bias"))
                cb.type = "currentBias"
                cb.add_main_structure(c2, self._result)
                self._result.add_bias_part(cb)
                p1 = self._result.get_part(c1)
                if isinstance(p1, BiasPart):
                    p1.add_biased_part(cb)
            elif not c1_done:
                vb = BiasPart(self._result.next_id("bias"))
                vb.type = "voltageBias"
                vb.add_main_structure(c1, self._result)
                self._result.add_bias_part(vb)
                p2 = self._result.get_part(c2)
                if p2 is not None:
                    vb.add_biased_part(p2)

    def _has_current_bias_input_on_net(self, s: "Structure", net: str) -> bool:
        """acst ``hasCurrentBiasInputConnectionOnNet``: the structure's Gate
        (or Gate1) pin sits on *net*."""
        for pin in ("Gate", "Gate1"):
            if s.has_pin(pin):
                return self._idx.net_name(s, pin) == net
        return False

    def _partition_voltage_reference1(self) -> None:
        """Port of ``Partitioning::partitioningVoltageReference1``: an
        unconsumed voltage reference whose Input net drives a load part's
        mirror gate becomes a voltage bias."""
        for vref in self._find(_VREF1):
            if self._result.structure_already_classified(vref):
                continue
            input_net = self._idx.net_name(vref, "Input")
            if input_net is None:
                continue
            is_load = False
            for cs in self._idx.connected_structures(input_net):
                if (self._result.structure_already_classified(cs)
                        and self._has_current_bias_input_on_net(cs, input_net)):
                    part = self._result.get_part(cs)
                    if part is not None and part.is_load():
                        is_load = True
                        break
            if is_load:
                vb = BiasPart(self._result.next_id("bias"))
                vb.type = "voltageBias"
                vb.add_main_structure(vref, self._result)
                self._result.add_bias_part(vb)
                for cs in self._idx.connected_structures(input_net):
                    if not self._result.structure_already_classified(cs):
                        continue
                    if not self._has_current_bias_input_on_net(cs, input_net):
                        continue
                    part = self._result.get_part(cs)
                    if part is None or part is vb:
                        continue
                    if part.is_load() and part not in vb.biased_parts:
                        vb.add_biased_part(part)
                        part.bias_parts.append(vb)
                    elif (isinstance(part, BiasPart)
                          and part.type == "currentBias"):
                        vb.add_biased_part(part)

    def _classify_diode_arrays(self) -> None:
        """Port of ``Partitioning::classifyDiodeArrays``: a leftover
        rail-sourced diode whose node drives an already-classified load /
        gm / bias gate of its own tech becomes a voltage bias."""
        for diode in self._find(_DA):
            if self._result.structure_already_classified(diode):
                continue
            source = self._idx.net_name(diode, "Source")
            if source is None or not self._idx.is_supply(source):
                continue
            gate_net = self._idx.net_name(diode, "Drain")
            if gate_net is None:
                continue
            is_load = is_trans = is_current_bias = False
            for cs in self._idx.connected_structures(gate_net):
                if not self._result.structure_already_classified(cs):
                    continue
                if not self._has_current_bias_input_on_net(cs, gate_net):
                    continue
                if cs.tech_type != diode.tech_type:
                    continue
                part = self._result.get_part(cs)
                if part is None:
                    continue
                is_load = is_load or part.is_load()
                is_trans = is_trans or part.is_transconductance()
                # the FUBOCO-era acst also classifies diodes that reference a
                # current bias (the local snapshot computes this flag but its
                # creation gate predates it — the gallery is the oracle here,
                # e.g. s-1-2/raw/1_3's m16 driving the second stage's bias)
                is_current_bias = is_current_bias or (
                    isinstance(part, BiasPart) and part.type == "currentBias"
                )
                if is_load or is_trans:
                    break
            if is_load or is_trans or is_current_bias:
                vb = BiasPart(self._result.next_id("bias"))
                vb.type = "voltageBias"
                vb.add_main_structure(diode, self._result)
                self._result.add_bias_part(vb)
                for cs in self._idx.connected_structures(gate_net):
                    if not self._result.structure_already_classified(cs):
                        continue
                    if not self._has_current_bias_input_on_net(cs, gate_net):
                        continue
                    if cs.tech_type != diode.tech_type:
                        continue
                    part = self._result.get_part(cs)
                    if part is None or part is vb:
                        continue
                    if part.is_load() or part.is_transconductance():
                        if part not in vb.biased_parts:
                            vb.add_biased_part(part)
                            part.bias_parts.append(vb)
                    elif isinstance(part, BiasPart):
                        vb.add_biased_part(part)

    def _covered_devices(self) -> set[str]:
        """Device names already assigned to a gm / load / bias / cap part."""
        covered: set[str] = set()
        for parts in (self._result.transconductance_parts, self._result.load_parts,
                      self._result.bias_parts, self._result.capacitance_parts):
            for p in parts:
                covered.update(p.devices())
        return covered

    def _add_bias(self, s: "Structure", btype: str) -> None:
        bias = BiasPart(self._result.next_id("bias"))
        bias.add_main_structure(s)
        bias.type = btype
        self._result.add_bias_part(bias)

    # ── step 7: capacitances ──────────────────────────────────────────

    def _partition_capacitances(self) -> None:
        for s in self._all_structures():
            if self._result.structure_already_classified(s):
                continue
            if not self._is_capacitor(s):
                continue
            nets = self._structure_nets(s)
            cap = CapacitancePart(self._result.next_id("cap"))
            cap.add_main_structure(s)
            cap.type = "load" if self._output_net in nets else "compensation"
            self._result.add_capacitance_part(cap)

    # ── step 8: undefined ─────────────────────────────────────────────

    def _create_undefined_parts(self) -> None:
        covered = self._covered_devices()
        for s in self._sc.structures_without_parents:
            if self._result.structure_already_classified(s):
                continue
            devs = {d.name for d in s.devices}
            # a composite whose devices are all already classified elsewhere
            # (e.g. the AnalogInverter feeding the second stage) is not undefined
            if devs and devs <= covered:
                continue
            part = UndefinedPart(self._result.next_id("undef"))
            part.add_main_structure(s)
            self._result.add_undefined_part(part)
            covered |= devs

    # ── small helpers ─────────────────────────────────────────────────

    def _all_structures(self) -> list["Structure"]:
        # acst StructureCircuits::findAllStructures iterates hierarchy levels
        # from the highest down to 0, and each level's std::map orders by
        # StructureId (name, then index).  partitioningRemainingCurrentMirrors
        # depends on this: a composite mirror must claim its reference child
        # before a lower-level mirror sharing the same diode gets a turn.
        out: list[Structure] = []
        for lvl in reversed(self._sc.hierarchy_levels):
            out.extend(sorted(self._sc.get_level(lvl).structures,
                              key=lambda s: (s.name, s.structure_id.index)))
        return out

    def _structure_nets(self, s: "Structure") -> set[str]:
        names: set[str] = set()
        for pin_name in s.pins:
            n = self._idx.net_name(s, pin_name)
            if n is not None:
                names.add(n)
        return names

    @staticmethod
    def _is_capacitor(s: "Structure") -> bool:
        from core.device import DeviceType
        if "Capacitor" in s.name:
            return True
        devs = s.devices
        return bool(devs) and all(d.device_type == DeviceType.CAPACITOR for d in devs)

    def _recursive_current_mirror_parent(self, s: "Structure"):
        for p in s.parents:
            if self._is_current_mirror(p):
                return p
            if p.is_part_of_current_mirror:
                r = self._recursive_current_mirror_parent(p)
                if r is not None:
                    return r
        return None

    def _is_voltage_bias(self, s: "Structure") -> bool:
        if s.name in (_DA, _VREF1):
            return True
        if s.has_exactly_one_parent and s.parents[0].name == _VREF1:
            return True
        for p in s.parents:
            if self._is_current_mirror(p) and p.is_pair and p.child1 is s:
                return True
            if self._is_voltage_bias(p):
                return True
        return False

    # ── second-stage classifier sub-checks ────────────────────────────

    def _has_stage_output_net_connection(self, net: str, part) -> bool:
        """Whether *net* touches the output of the given (already-classified) part."""
        if part.is_transconductance():
            tp = self._result.get_transconductance_part(part.main_structures[0])
            if tp is None:
                return False
            if tp.is_first_stage():
                return self._touches_first_stage_output(net)
            if tp.is_second_stage():
                return self._touches_second_stage_output(net)
            return False
        if part.is_load():
            first = self._result.get_first_stage()
            if (first is None or len(first.load_parts) != 1
                    or not self._is_symmetrical_load_part(first.load_parts[0])):
                return False
            for cs in self._idx.connected_structures(net):
                if cs.name == _DA:
                    g = self._idx.net_name(cs, "Drain")
                    src = self._idx.net_name(cs, "Source")
                    if g == net and src is not None and self._idx.is_supply(src):
                        return True
                elif cs.name == _NA:
                    g = self._idx.net_name(cs, "Gate")
                    src = self._idx.net_name(cs, "Source")
                    if g == net and src is not None and self._idx.is_supply(src):
                        return True
        return False

    def _touches_first_stage_output(self, net: str) -> bool:
        first = self._result.get_first_stage()
        if first is None:
            return False
        for main in first.main_structures:
            for arr in main.array_children:
                if self._idx.net_name(arr, "Drain") == net:
                    return True
        for lp in first.load_parts:
            for m in lp.main_structures:
                for pin in ("Drain", "Output"):
                    if self._idx.net_name(m, pin) == net:
                        return True
        return False

    def _touches_second_stage_output(self, net: str) -> bool:
        for tp in self._result.get_second_stages():
            for m in tp.main_structures:
                for pin in ("Drain", "Output"):
                    if self._idx.net_name(m, pin) == net:
                        return True
        return False

    def _has_voltage_bias_output_connection(self, net: str | None) -> bool:
        if net is None:
            return False
        return any(self._is_voltage_bias(s)
                   for s in self._idx.connected_structures(net))

    def _only_one_transistor_on_net(self, net: str | None) -> bool:
        if net is None:
            return False
        arrays = [s for s in self._idx.connected_structures(net)
                  if s.name in (_NA, _DA)]
        return len(arrays) == 1
