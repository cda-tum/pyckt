topogen
=======

The HL2–HL5 topology factories that enumerate op-amp topologies, plus the
``toplibgen`` analysis entry point.

.. automodule:: topogen
   :no-members:

Hierarchy levels
----------------

.. automodule:: topogen.HL2
   :no-members:

.. automodule:: topogen.HL3
   :no-members:

.. automodule:: topogen.HL4
   :no-members:

.. automodule:: topogen.HL5
   :no-members:

Data model & analysis
---------------------

.. automodule:: topogen.common
   :no-members:

.. automodule:: topogen.common.circuit
   :members:
   :exclude-members: Circuit

.. autoclass:: topogen.common.circuit.Circuit
   :members:
   :no-index:

   .. note::
      Named ``Circuit`` like :class:`~core.circuit.Circuit`, but distinct —
      this is the topogen-side *nested* tree node, not the flat data model.
      Marked ``:no-index:`` so cross-references to the bare name ``Circuit``
      elsewhere in the docs resolve unambiguously to :class:`~core.circuit.Circuit`
      (the far more commonly referenced one).

.. automodule:: topogen.analysis
   :members:
