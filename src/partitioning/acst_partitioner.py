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
# inverter structure names checked as second-stage transconductances
_INVERTERS = (
    "MosfetAnalogInverter",
    "MosfetCascodedAnalogInverter",
    "MosfetCascodedPMOSAnalogInverter",
    "MosfetCascodedNMOSAnalogInverter",
)


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
        self._recognize_second_second_stage()

        first = self._result.get_first_stage()
        if first is not None:
            if self._result.has_secondary_second_stage():
                first.first_stage_type = "symmetrical"
            elif not first.first_stage_type:
                first.first_stage_type = "simple"

        self._partition_remaining_current_mirrors()
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
        return "CurrentMirror" in s.name

    def _array_drain_net(self, array: "Structure") -> str | None:
        return self._idx.net_name(array, "Drain")

    # ── step 1: differential pairs → first stage ──────────────────────

    def _partition_differential_pairs(self) -> None:
        for dp in self._find(_DP):
            if self._result.structure_already_classified(dp):
                continue
            tp = TransconductancePart(self._result.next_id("trans"))
            tp.add_main_structure(dp)
            self._result.add_transconductance_part(tp)

            # feedback vs first stage: does another diff pair share both gates?
            g1 = self._idx.net_name(dp, "Input1")
            g2 = self._idx.net_name(dp, "Input2")
            others: set[int] = set()
            for net in (g1, g2):
                if not net:
                    continue
                for pin in ("Input1", "Input2"):
                    for s in self._idx.connected_via(net, _DP, pin):
                        if s is not dp:
                            others.add(id(s))
            tp.type = "feedBack" if len(others) >= 2 else "firstStage"

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
                                        dp.tech_type, load=False)
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
        arrays = dp.array_children
        if len(arrays) < 2:
            return
        load_same = LoadPart(self._result.next_id("load"))
        load_opp = LoadPart(self._result.next_id("load"))
        for arr in arrays[:2]:
            drain = self._array_drain_net(arr)
            if drain is not None:
                self._find_with_drain_connected(drain, arr, load_same, load_opp,
                                                dp.tech_type, load=True)
        tp = self._result.get_transconductance_part(dp)
        for lp in (load_same, load_opp):
            if lp.has_main_structures:
                if tp is not None:
                    tp.load_parts.append(lp)
                self._result.add_load_part(lp)

    # ── shared recursive drain walk (load + bias) ─────────────────────

    def _find_with_drain_connected(
        self, net: str, ref: "Structure",
        part_same, part_opp, ref_tech, load: bool,
    ) -> None:
        """Port of findWithDrainConnectedLoadStructures / ...Devices.

        Adds array-level structures whose Drain sits on *net* (same/opposite
        tech) and recurses up their Source net while it is not a supply rail.
        """
        for cs in self._idx.connected_structures(net):
            if self._result.structure_already_classified(cs):
                continue
            if cs is ref or not cs.has_pin("Drain"):
                continue
            if self._idx.net_name(cs, "Drain") != net:
                continue
            source = self._idx.net_name(cs, "Source")
            if part_same is not None and cs.tech_type == ref_tech:
                part_same.add_main_structure(cs)
                if source is not None and not self._idx.is_supply(source):
                    self._find_with_drain_connected(source, cs, part_same, None,
                                                    ref_tech, load)
            elif part_opp is not None:
                part_opp.add_main_structure(cs)
                if source is not None and not self._idx.is_supply(source):
                    self._find_with_drain_connected(source, cs, part_opp, None,
                                                    ref_tech, load)

    # ── step 4: second stage (inverter classifiers) ───────────────────

    def _partition_second_stage(self) -> None:
        for name in self._present_inverters():
            self._classify_inverter(name)

    def _present_inverters(self) -> list[str]:
        return [n for n in _INVERTERS if self._find(n)]

    def _classify_inverter(self, inverter_name: str) -> None:
        for inv in self._find(inverter_name):
            if self._result.structure_already_classified(inv):
                continue
            if not inv.is_pair:
                continue
            child_trans = 0
            inv_type = ""
            for gate_a, gate_b, trans_child, bias_child in (
                ("InputPMOS1", "InputNMOS1", 1, 2),
                ("InputNMOS1", "InputPMOS1", 2, 1),
            ):
                net_a = self._idx.net_name(inv, gate_a)
                if net_a is None:
                    continue
                for s in self._idx.connected_structures(net_a):
                    part = self._result.get_part(s)
                    if part is None or not (part.is_transconductance() or part.is_load()):
                        continue
                    if not self._has_stage_output_net_connection(net_a, part):
                        continue
                    if not (self._has_voltage_bias_output_connection(
                                self._idx.net_name(inv, gate_b))
                            or self._only_one_transistor_on_net(
                                self._idx.net_name(inv, gate_b))):
                        continue
                    if (part.is_load()
                            or (part.is_transconductance() and part.is_first_stage())):
                        inv_type = "primarySecondStage"
                        child_trans, _ = trans_child, bias_child
                    elif (part.is_transconductance() and part.is_primary_second_stage()):
                        inv_type = "thirdStage"
                        child_trans, _ = trans_child, bias_child
                if child_trans:
                    break
            if child_trans and inv_type:
                trans_struct = inv.get_child(child_trans)
                self._initialize_inverter_stage([trans_struct], inv_type)

    def _initialize_inverter_stage(
        self, trans_structs: list["Structure"], inv_type: str
    ) -> None:
        if any(self._result.structure_already_classified(t) for t in trans_structs):
            return
        tp = TransconductancePart(self._result.next_id("trans"))
        for t in trans_structs:
            tp.add_main_structure(t)
        tp.type = inv_type
        self._result.add_transconductance_part(tp)

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
                    if self._find_second_second_bias(potential_bias) is None:
                        continue
                    if not self._result.structure_already_classified(output_leg):
                        self._initialize_inverter_stage([arr, cs],
                                                        "secondarySecondStage")
                # fallback: whole leg if no paired array found
                if not self._result.has_secondary_second_stage():
                    drain_structs = self._idx.connected_structures(drain)
                    if (self._find_second_second_bias(drain_structs) is not None
                            and not self._result.structure_already_classified(output_leg)):
                        self._initialize_inverter_stage([output_leg],
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
        """Classify leftover building blocks as bias, at acst's granularity.

        acst emits bias parts at the component level: the cascode/voltage-ref
        children of higher current mirrors, then individual leaf arrays — each
        device counted once.  We classify intermediate bias structures first
        (CascodePair / VoltageReference), then any remaining leaf arrays whose
        devices are not yet covered.
        """
        covered = self._covered_devices()
        # 1) intermediate bias building blocks (children of higher mirrors)
        for name in ("MosfetCascodePair", "MosfetVoltageReference2",
                     "MosfetVoltageReference1", "MosfetDiodeStack"):
            for s in self._find(name):
                if self._result.structure_already_classified(s):
                    continue
                devs = {d.name for d in s.devices}
                if devs & covered:
                    continue
                self._add_bias(s, "voltageBias" if "Voltage" in name else "currentBias")
                covered |= devs
        # 2) remaining leaf arrays, one device at a time
        for lvl in self._sc.hierarchy_levels:
            for s in self._sc.get_level(lvl).structures:
                if self._result.structure_already_classified(s):
                    continue
                if not (s.name in (_NA, _DA)):
                    continue
                devs = {d.name for d in s.devices}
                if devs & covered or not devs:
                    continue
                self._add_bias(s, "voltageBias" if s.name == _DA else "currentBias")
                covered |= devs

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
        out: list[Structure] = []
        for lvl in self._sc.hierarchy_levels:
            out.extend(self._sc.get_level(lvl).structures)
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
