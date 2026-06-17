"""pyckt.partitioning — Functional classification of recognised structures.

Takes the hierarchical overlay produced by :mod:`recognition` and
assigns each structure a functional role within the op-amp:
**transconductance**, **load**, **bias**, **capacitance**, or
**undefined**.  The 12-step classifier in :class:`Partitioner` analyses
net connectivity relative to the user-supplied input/output/bias pins
and the supply rails (from
:class:`~pyckt.io.circuit_info_parser.CircuitParameter`).

Main classes
------------
* :class:`Partitioner` — 12-step classifier that produces a `PartitionResult`
* :class:`PartitionResult` — keyed lookup of (structure → role + stage)
* :class:`PartType` — enum: transconductance / load / bias / capacitance / undefined
* :class:`StageType` — enum: FIRST / SECOND (for two-stage op-amps)
* :class:`PartitionXMLWriter` — XML output writer
* :class:`~partitioning.analysis.PartitioningAnalysis` — the
  ``--analysis partitioning`` CLI dispatch endpoint (see :mod:`pyckt.cli`)

Typical usage
-------------
::

    from partitioning import Partitioner, PartitionXMLWriter
    result = Partitioner(circuit_params).partition(structure_overlay)
    PartitionXMLWriter(result).write("partition.xml")
"""

from .partitioner import Partitioner
from .result import PartAssignment, PartitionResult, PartType, StageType
from .writer import PartitionXMLWriter

__all__ = [
    "Partitioner",
    "PartitionResult",
    "PartAssignment",
    "PartType",
    "StageType",
    "PartitionXMLWriter",
]
