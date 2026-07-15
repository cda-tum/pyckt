"""Shared data model for the topology generator.

:mod:`topogen.common.circuit` defines the topogen-side hierarchical
:class:`~topogen.common.circuit.Circuit` and its subclasses — one per functional
block produced across HL2–HL5 (``DiffPair``, ``CurrentMirror``, ``Load``,
``Transconductance``, ``NonInvertingStage``, ``InvertingStage``, ``OpAmp``, …).

This is deliberately distinct from the flat :class:`core.Circuit` used by the
recognition / sizing pipeline: the topogen ``Circuit`` is a *nested* structure
that is flattened (via :meth:`~topogen.common.circuit.Circuit.flatten`) and
converted to a ``core.Circuit`` by
:class:`synthesis.converter.TopologyConverter` only once a topology is complete.
"""
