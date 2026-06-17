"""Circuit partitioning — classifies recognised structures into op-amp roles.

Implements a 12-step classification sequence that assigns each structure a
functional role (transconductance, load, bias, capacitance, or undefined)
based on net connectivity analysis.

C++ ref: ``Partitioning/src/Partitioning.cpp``
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from pyckt.core.device import DeviceType

from .result import PartitionResult, PartType, StageType

if TYPE_CHECKING:
    from pyckt.io.circuit_info_parser import CircuitParameter
    from recognition.model import Structure, StructureCircuits


class Partitioner:
    """Classifies recognised structures into functional op-amp parts.

    The 12-step algorithm analyses net connectivity relative to known
    circuit parameters (input/output/bias nets) and supply rails.

    Parameters
    ----------
    circuit_params : CircuitParameter
        Pin-to-net assignments (input+/−, output, bias current, supplies).
    """

    def __init__(self, circuit_params: CircuitParameter) -> None:
        self._params = circuit_params
        self._input_plus = circuit_params.input_plus[0]
        self._input_minus = circuit_params.input_minus[0]
        self._output_net = circuit_params.output_net
        self._bias_net = circuit_params.bias_current[0]

    # ── Public entry point ───────────────────────────────────────────

    def partition(self, sc: StructureCircuits) -> PartitionResult:
        """Run the 12-step classification on *sc* and return the result.

        Parameters
        ----------
        sc : StructureCircuits
            Output of the structure recognition engine.

        Returns
        -------
        PartitionResult
            Every structure in *sc* assigned a functional role.
        """
        result = PartitionResult()
        structures = sc.structures_without_parents

        self._first_stage_output_nets: set[str] = set()
        self._second_stage_output_nets: set[str] = set()

        self._step1_identify_input_pair(structures, result)
        self._step2_identify_first_stage_bias(structures, result)
        self._step3_identify_first_stage_load(structures, result)
        self._step4_identify_first_stage_load_cascode(structures, result)
        self._step5_identify_first_stage_tc_cascode(structures, result)
        self._step6_identify_second_stage_tc(structures, result, sc)
        self._step7_identify_second_stage_load(structures, result)
        self._step8_identify_second_stage_bias(structures, result)
        self._step9_identify_compensation_cap(structures, result)
        self._step10_identify_load_cap(structures, result)
        self._step11_identify_remaining_bias(structures, result, sc)
        self._step12_mark_remaining(structures, result)

        logger.info("Partitioning complete: {}", result.summary())
        return result

    # ── Step 1 — input differential pair ─────────────────────────────

    def _step1_identify_input_pair(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Find DifferentialPair whose gates connect to input nets."""
        for s in structures:
            if result.is_classified(s):
                continue
            if "DifferentialPair" not in s.name:
                continue
            nets = self._pin_net_names(s)
            if self._input_plus in nets or self._input_minus in nets:
                result.assign(s, PartType.TRANSCONDUCTANCE, StageType.FIRST,
                              "input differential pair")
                for pin in s.pins.values():
                    try:
                        n = pin.net
                        if not n.is_supply() and n.name not in (
                            self._input_plus, self._input_minus
                        ):
                            self._first_stage_output_nets.add(n.name)
                    except RuntimeError:
                        continue
                logger.debug("Step 1: {} → first-stage TC", s.name)

    # ── Step 2 — bias of first-stage transconductance ────────────────

    def _step2_identify_first_stage_bias(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Find structure biasing the input pair's tail current."""
        tc_parts = result.transconductance_parts(StageType.FIRST)
        if not tc_parts:
            return
        tail_nets: set[str] = set()
        for tc in tc_parts:
            for pn, pin in tc.pins.items():
                if "source" in pn.lower():
                    try:
                        tail_nets.add(pin.net.name)
                    except RuntimeError:
                        continue
        for s in structures:
            if result.is_classified(s):
                continue
            nets = self._pin_net_names(s)
            if tail_nets & nets and self._has_supply_connection(s):
                result.assign(s, PartType.BIAS, StageType.FIRST,
                              "first-stage tail bias")
                logger.debug("Step 2: {} → first-stage bias", s.name)

    # ── Step 3 — load parts of first stage ───────────────────────────

    def _step3_identify_first_stage_load(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Structures connected to first-stage output nets and supply."""
        if not self._first_stage_output_nets:
            return
        for s in structures:
            if result.is_classified(s):
                continue
            if self._is_capacitor(s):
                continue
            nets = self._pin_net_names(s)
            if (self._first_stage_output_nets & nets
                    and self._has_supply_connection(s)):
                result.assign(s, PartType.LOAD, StageType.FIRST,
                              "first-stage load")
                logger.debug("Step 3: {} → first-stage load", s.name)

    # ── Step 4 — cascode of first-stage load ─────────────────────────

    def _step4_identify_first_stage_load_cascode(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Cascode structures between diff pair drains and load."""
        load_parts = result.load_parts(StageType.FIRST)
        if not load_parts:
            return
        load_nets: set[str] = set()
        for lp in load_parts:
            load_nets |= self._pin_net_names(lp)
        for s in structures:
            if result.is_classified(s):
                continue
            if "Cascode" not in s.name and "LevelShifter" not in s.name:
                continue
            nets = self._pin_net_names(s)
            if (self._first_stage_output_nets & nets) and (load_nets & nets):
                result.assign(s, PartType.LOAD, StageType.FIRST,
                              "first-stage load cascode")
                logger.debug("Step 4: {} → first-stage load cascode", s.name)

    # ── Step 5 — cascode of first-stage transconductance ─────────────

    def _step5_identify_first_stage_tc_cascode(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Cascode between input pair and load (same tech as diff pair)."""
        tc_parts = result.transconductance_parts(StageType.FIRST)
        if not tc_parts:
            return
        tc_nets: set[str] = set()
        tc_tech = None
        for tc in tc_parts:
            tc_nets |= self._pin_net_names(tc)
            tc_tech = tc.tech_type
        for s in structures:
            if result.is_classified(s):
                continue
            if "Cascode" not in s.name:
                continue
            nets = self._pin_net_names(s)
            if tc_nets & nets and (tc_tech is None or s.tech_type == tc_tech):
                result.assign(s, PartType.TRANSCONDUCTANCE, StageType.FIRST,
                              "first-stage TC cascode")
                logger.debug("Step 5: {} → first-stage TC cascode", s.name)

    # ── Step 6 — second-stage transconductance ───────────────────────

    def _step6_identify_second_stage_tc(
        self, structures: list[Structure], result: PartitionResult,
        sc: StructureCircuits,
    ) -> None:
        """Inverter-type structure driven by first-stage output."""
        if not self._first_stage_output_nets:
            return
        for s in structures:
            if result.is_classified(s):
                continue
            if "Inverter" not in s.name and "AnalogInverter" not in s.name:
                continue
            nets = self._pin_net_names(s)
            if self._first_stage_output_nets & nets:
                result.assign(s, PartType.TRANSCONDUCTANCE, StageType.SECOND,
                              "second-stage transconductance")
                for pin in s.pins.values():
                    try:
                        n = pin.net
                        if (not n.is_supply()
                                and n.name not in self._first_stage_output_nets):
                            self._second_stage_output_nets.add(n.name)
                    except RuntimeError:
                        continue
                logger.debug("Step 6: {} → second-stage TC", s.name)

    # ── Step 7 — second-stage load ───────────────────────────────────

    def _step7_identify_second_stage_load(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Structure between second-stage output and supply."""
        if not self._second_stage_output_nets:
            return
        for s in structures:
            if result.is_classified(s):
                continue
            nets = self._pin_net_names(s)
            if (self._second_stage_output_nets & nets
                    and self._has_supply_connection(s)):
                result.assign(s, PartType.LOAD, StageType.SECOND,
                              "second-stage load")
                logger.debug("Step 7: {} → second-stage load", s.name)

    # ── Step 8 — second-stage bias ───────────────────────────────────

    def _step8_identify_second_stage_bias(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Structure biasing the second stage."""
        tc2 = result.transconductance_parts(StageType.SECOND)
        if not tc2:
            return
        tc2_nets: set[str] = set()
        for tc in tc2:
            tc2_nets |= self._pin_net_names(tc)
        for s in structures:
            if result.is_classified(s):
                continue
            nets = self._pin_net_names(s)
            if tc2_nets & nets and self._has_supply_connection(s):
                result.assign(s, PartType.BIAS, StageType.SECOND,
                              "second-stage bias")
                logger.debug("Step 8: {} → second-stage bias", s.name)

    # ── Step 9 — compensation capacitor ──────────────────────────────

    def _step9_identify_compensation_cap(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Cap between first-stage output and second-stage output."""
        if not (self._first_stage_output_nets and self._second_stage_output_nets):
            return
        for s in structures:
            if result.is_classified(s):
                continue
            if not self._is_capacitor(s):
                continue
            nets = self._pin_net_names(s)
            if (self._first_stage_output_nets & nets
                    and self._second_stage_output_nets & nets):
                result.assign(s, PartType.CAPACITANCE, StageType.COMPENSATION,
                              "compensation capacitor")
                logger.debug("Step 9: {} → compensation cap", s.name)

    # ── Step 10 — load capacitor ─────────────────────────────────────

    def _step10_identify_load_cap(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Cap connected to the output net."""
        for s in structures:
            if result.is_classified(s):
                continue
            if not self._is_capacitor(s):
                continue
            nets = self._pin_net_names(s)
            if self._output_net in nets:
                result.assign(s, PartType.CAPACITANCE, StageType.UNDEFINED,
                              "load capacitor")
                logger.debug("Step 10: {} → load cap", s.name)

    # ── Step 11 — remaining bias ─────────────────────────────────────

    def _step11_identify_remaining_bias(
        self, structures: list[Structure], result: PartitionResult,
        sc: StructureCircuits,
    ) -> None:
        """Unclassified current mirrors / diode arrays → bias."""
        for s in structures:
            if result.is_classified(s):
                continue
            nets = self._pin_net_names(s)
            if self._bias_net and self._bias_net in nets:
                result.assign(s, PartType.BIAS, StageType.UNDEFINED,
                              "bias (connected to bias net)")
                logger.debug("Step 11: {} → remaining bias (bias net)", s.name)
                continue
            if "CurrentMirror" in s.name:
                result.assign(s, PartType.BIAS, StageType.UNDEFINED,
                              "bias (unclassified current mirror)")
                logger.debug("Step 11: {} → remaining bias (mirror)", s.name)
                continue
            if "VoltageReference" in s.name:
                result.assign(s, PartType.BIAS, StageType.UNDEFINED,
                              "bias (voltage reference)")
                logger.debug("Step 11: {} → remaining bias (vref)", s.name)
                continue
            if "DiodeArray" in s.name and self._has_supply_connection(s):
                result.assign(s, PartType.BIAS, StageType.UNDEFINED,
                              "bias (diode array)")
                logger.debug("Step 11: {} → remaining bias (diode)", s.name)

    # ── Step 12 — mark remaining as undefined ────────────────────────

    def _step12_mark_remaining(
        self, structures: list[Structure], result: PartitionResult
    ) -> None:
        """Everything left gets ``PartType.UNDEFINED``."""
        for s in structures:
            if not result.is_classified(s):
                result.assign(s, PartType.UNDEFINED, StageType.UNDEFINED,
                              "unclassified")
                logger.debug("Step 12: {} → undefined", s.name)

    # ── Utility methods ──────────────────────────────────────────────

    @staticmethod
    def _pin_net_names(structure: Structure) -> set[str]:
        """Collect all net names connected to *structure*'s pins."""
        names: set[str] = set()
        for pin in structure.pins.values():
            try:
                names.add(pin.net.name)
            except RuntimeError:
                continue
        return names

    @staticmethod
    def _has_supply_connection(structure: Structure) -> bool:
        """``True`` if any pin connects to a supply/ground rail."""
        for pin in structure.pins.values():
            try:
                if pin.net.is_supply():
                    return True
            except RuntimeError:
                continue
        return False

    @staticmethod
    def _is_capacitor(structure: Structure) -> bool:
        """``True`` if the structure contains only capacitor devices."""
        if "Capacitor" in structure.name or "CapacitorArray" in structure.name:
            return True
        devs = structure.devices
        return bool(devs) and all(
            d.device_type == DeviceType.CAPACITOR for d in devs
        )
