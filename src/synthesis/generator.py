"""Topology library generator.

Provides :class:`TopologyLibraryGenerator`, which calls the existing
HL2–HL5 topogen factory classes to enumerate all valid op-amp topologies
and packages them into a :class:`~synthesis.library.TopologyLibrary`.

Usage
-----
>>> import tempfile, os
>>> from synthesis.generator import TopologyLibraryGenerator
>>> with tempfile.TemporaryDirectory() as d:
...     gen = TopologyLibraryGenerator(output_dir=d)
...     lib = gen.generate()
...     print(lib.size() > 100)
True
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Iterator

from core.device import TechType
from synthesis.converter import TopologyConverter
from synthesis.library import TopologyLibrary, TopologySpec


class TopologyLibraryGenerator:
    """Generate the complete topology library using the HL2–HL5 factory classes.

    The generator iterates:

    * All 16 cases of ``NonInvertingStageManager.createSimpleNonInvertingStages``
    * All 4 cases of ``createFullyDifferentialNonInvertingStages``
    * All 2 cases of ``createComplementaryNonInvertingStages``
    * All 8 cases of ``createSymmetricalNonInvertingStages``
    * Feedback stages (PMOS + NMOS transconductance)

    For each first-stage, it creates both:

    * A **one-stage** op-amp (first stage only).
    * A **two-stage** op-amp for every ``InvertingStage`` variant (12 variants).

    Each op-amp is described by a :class:`~synthesis.library.TopologySpec`
    and converted to a flat :class:`~core.Circuit` via
    :class:`~synthesis.converter.TopologyConverter`.

    Maps to the C++ ``Synthesis::TopologyLibraryGeneration`` functionality.

    Parameters
    ----------
    output_dir:
        Directory where the library will be written by
        :meth:`~synthesis.library.TopologyLibrary.to_directory`.
        Created if it does not exist.  Pass ``None`` (or omit) to skip the
        on-disk write entirely and keep the library in memory only.
    """

    def __init__(self, output_dir: str | None = None):
        # ``None`` / empty string both mean "in-memory only" — never silently
        # resolve to the cwd (which would litter the working directory with
        # thousands of stub .ckt/.json files).
        self.output_dir: str | None = str(output_dir) if output_dir else None
        self.library = TopologyLibrary()
        self._converter = TopologyConverter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> TopologyLibrary:
        """Generate all valid op-amp topologies and return the library.

        Calls the HL4/HL5 factory functions to enumerate every first-stage
        variant, combines with all inverting stages for two-stage topologies,
        assigns sequential IDs, and writes the library to :attr:`output_dir`.

        Returns
        -------
        TopologyLibrary
            The fully-populated library (also stored as ``self.library``).
        """
        topology_id = 1

        from topogen.HL4.inv import InvertingStageManager
        from topogen.HL5.opamps import createSimpleOpAmp

        inv_stages = InvertingStageManager().getInvertingStages()

        for first_stage, is_complementary, is_fd, input_tech in (
            self._iter_first_stages()
        ):
            tech = TechType.P if input_tech == "p" else TechType.N

            # ---- one-stage ------------------------------------------------
            # Fully-differential op-amps compose the first stage with a
            # common-mode feedback stage (acst createFullyDifferentialOneStageOpAmps);
            # single-output/complementary use the first stage alone.
            for opamp_1s in self._one_stage_opamps(first_stage, is_fd, input_tech):
                spec_1s = TopologySpec(
                    id=topology_id,
                    name=self._make_name(1, is_complementary, is_fd, input_tech),
                    num_stages=1,
                    is_complementary=is_complementary,
                    is_fully_differential=is_fd,
                    input_tech=tech,
                    has_cascode={},
                )
                try:
                    core_circuit = self._converter.convert(opamp_1s)
                except Exception:  # noqa: BLE001 — tolerate flatten errors per topology
                    core_circuit = None
                self.library.add(spec_1s, core_circuit)
                topology_id += 1

            # ---- two-stage (single-output only) ---------------------------
            # acst emits two-stage variants for single-output only: complementary
            # and fully-differential op-amps are one-stage (acst createOpAmps
            # guards two-stage with ``if(!isComplementary)``, and its FD path
            # is one-stage here — FD two-stage is not yet ported).
            if is_fd or is_complementary:
                continue
            for second_stage in inv_stages:
                opamp_2s = createSimpleOpAmp(
                    firstStage=deepcopy(first_stage),
                    secondStage=deepcopy(second_stage),
                )
                spec_2s = TopologySpec(
                    id=topology_id,
                    name=self._make_name(2, is_complementary, is_fd, input_tech),
                    num_stages=2,
                    is_complementary=is_complementary,
                    is_fully_differential=is_fd,
                    input_tech=tech,
                    has_cascode={},
                )
                try:
                    core_circuit_2s = self._converter.convert(opamp_2s)
                except Exception:  # noqa: BLE001
                    core_circuit_2s = None
                self.library.add(spec_2s, core_circuit_2s)
                topology_id += 1

        # Write to disk only when an output directory was supplied.
        if self.output_dir:
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
            self.library.to_directory(self.output_dir)
            print(f"Generated {self.library.size()} topologies → {self.output_dir}")
        else:
            print(f"Generated {self.library.size()} topologies (in-memory only)")
        return self.library

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _one_stage_opamps(self, first_stage, is_fd: bool, input_tech: str) -> list:
        """Build the one-stage op-amp(s) for *first_stage*.

        Single-output/complementary → one op-amp (first stage alone).
        Fully-differential → one op-amp per common-mode feedback stage of the
        matching transconductance tech (acst pairs a p-input first stage with
        the PMOS-transconductance feedback stages, an n-input one with the NMOS
        feedback stages).
        """
        from topogen.HL4.non_inv import NonInvertingStageManager
        from topogen.HL5.opamps import (
            createFullyDifferentialOpAmp,
            createSimpleOpAmp,
        )

        if not is_fd:
            return [createSimpleOpAmp(firstStage=deepcopy(first_stage), secondStage=None)]

        mgr = NonInvertingStageManager()
        feedback_stages = (
            mgr.getFeedbackNonInvertingStagesPmosTransconductance()
            if input_tech == "p"
            else mgr.getFeedbackNonInvertingStagesNmosTransconductance()
        )
        return [
            createFullyDifferentialOpAmp(deepcopy(first_stage), deepcopy(fb))
            for fb in feedback_stages
        ]

    def _iter_first_stages(self) -> Iterator[tuple]:
        """Yield ``(NonInvertingStage, is_complementary, is_fd, input_tech)``
        for every first-stage variant across all factory cases.
        """
        from topogen.HL4.non_inv import NonInvertingStageManager

        mgr = NonInvertingStageManager()

        # Simple: cases 1–16
        # Odd cases use PMOS transconductance, even cases use NMOS.
        for case_id in range(1, 17):
            input_tech = "p" if case_id % 2 == 1 else "n"
            for stage in mgr.createSimpleNonInvertingStages(case_id):
                yield stage, False, False, input_tech

        # Fully-differential: cases 1–4
        for case_id in range(1, 5):
            input_tech = "p" if case_id % 2 == 1 else "n"
            for stage in mgr.createFullyDifferentialNonInvertingStages(case_id):
                yield stage, False, True, input_tech

        # Complementary: cases 1–2 (NMOS+PMOS input pair)
        for case_id in range(1, 3):
            for stage in mgr.createComplementaryNonInvertingStages(case_id):
                yield stage, True, False, "n"

        # Symmetrical: cases 1–8
        for case_id in range(1, 9):
            input_tech = "p" if case_id % 2 == 1 else "n"
            for stage in mgr.createSymmetricalNonInvertingStages(case_id):
                yield stage, False, False, input_tech

        # NOTE: feedback non-inverting stages are *not* single-output first
        # stages — acst uses them only as the common-mode feedback stage of a
        # fully-differential op-amp (see generator._one_stage_opamps).  They were
        # previously folded in here, over-generating 12 × 13 = 156 spurious
        # single-output topologies (issue #20).

    @staticmethod
    def _make_name(
        num_stages: int,
        is_complementary: bool,
        is_fd: bool,
        input_tech: str,
    ) -> str:
        """Build a human-readable topology name from metadata fields."""
        parts = [f"{num_stages}stage"]
        if is_complementary:
            parts.append("complementary")
        if is_fd:
            parts.append("fd")
        parts.append(f"{input_tech}mos_input")
        return "_".join(parts)
