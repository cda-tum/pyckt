"""pyckt — Python re-implementation of ACST (Analog Circuit Synthesis Tool).

In addition to the ``pyckt`` command-line interface (see :mod:`cli`),
every analysis mode is available as a typed Python function for direct,
in-process use:

* :func:`~pyckt.api.recognize` — structure recognition
* :func:`~pyckt.api.generate_rules` — sizing-rule generation
* :func:`~pyckt.api.partition` — functional partitioning
* :func:`~pyckt.api.size` — automatic transistor sizing
* :func:`~pyckt.api.synthesize` — specification-driven topology synthesis
* :func:`~pyckt.api.generate_topology_library` — topology-library generation

Example
-------
::

    from pyckt import recognize

    structures = recognize(
        circuit="circuit.hspice",
        device_types="deviceTypes.xcat",
        mapping="HSpiceMapping.xcat",
        supply_nets="supplyNets.xcat",
    )
    print(structures.total_structures)
"""

from pyckt.api import (
    generate_rules,
    generate_topology_library,
    partition,
    recognize,
    size,
    synthesize,
)

__all__ = [
    "recognize",
    "generate_rules",
    "partition",
    "size",
    "synthesize",
    "generate_topology_library",
]
