"""HL4 — complete amplifier stages.

The fourth hierarchy level assembles HL3 building blocks (transconductor + load +
stage bias) into whole amplifier stages, which HL5 then chains into one- and
two-stage op-amps:

=========================================================  ==========================================
Factory                                                    Produces
=========================================================  ==========================================
:class:`~topogen.HL4.non_inv.NonInvertingStageManager`     non-inverting (input / first) stages
:class:`~topogen.HL4.inv.InvertingStageManager`            inverting (second / output) stages
=========================================================  ==========================================

See :mod:`topogen` for the full HL1–HL5 hierarchy.
"""
