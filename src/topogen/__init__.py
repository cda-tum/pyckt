"""pyckt.topogen — Hierarchical topology generation for analog op-amps.

Builds op-amp topologies by composing a 5-level hierarchy of factory
classes (HL1–HL5).  Each level produces variants of one functional
sub-block; higher levels combine lower-level outputs.  See the
``planning/08-week8-synthesis.md`` document for the full hierarchy
diagram.

Hierarchy
---------
==== =====================  ==============================================
HL   Concept                 Concrete factories
==== =====================  ==============================================
HL1  Devices                 (placeholder — handled at the core level)
HL2  Two-transistor cells    ``DiffPairManager``, ``VoltageBiasManager``,
                             ``CurrentBiasManager``, ``InverterManager``,
                             ``CurrentMirrorFactory``,
                             ``CrossCoupledPairFactory``
HL3  Stages                  ``LoadFactory``, ``LoadPartFactory``,
                             ``StageBiasFactory``, ``TransconductanceFactory``
HL4  Functional blocks       ``InvertingStageFactory``,
                             ``NonInvertingStageFactory``
HL5  Op-amps                 ``OpAmpFactory`` (one- + two-stage assemblies)
==== =====================  ==============================================

Main classes
------------
* :class:`~topogen.common.circuit.Circuit` — the topogen-side circuit
  data model (distinct from :class:`core.Circuit`)
* :class:`~topogen.analysis.TopLibGenAnalysis` — the
  ``--analysis toplibgen`` CLI dispatch endpoint that drives the full
  HL2–HL5 generator into a
  :class:`synthesis.TopologyLibrary` (see :mod:`cli`).

Typical usage
-------------
::

    from topogen.HL2 import DiffPairManager
    pmos_dp = DiffPairManager().getDifferentialPairPmos()
    nmos_dp = DiffPairManager().getDifferentialPairNmos()

For programmatic library generation see
:class:`synthesis.TopologyLibraryGenerator`.
"""
