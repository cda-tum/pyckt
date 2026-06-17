"""pyckt.synthesis — Topology library + specification-driven search.

Two complementary capabilities:

1. **Topology library generation** —
   :class:`TopologyLibraryGenerator` enumerates every valid op-amp
   topology by chaining the :mod:`topogen` HL2–HL5 factories.  Each
   topogen :class:`~topogen.common.circuit.Circuit` is converted to a
   flat :class:`pyckt.core.Circuit` via :class:`TopologyConverter`, then
   indexed by a :class:`TopologySpec` (id, name, num_stages, etc.) and
   collected into a :class:`TopologyLibrary`.
2. **Synthesis** —
   :class:`SynthesisEngine` takes a populated library + a
   :class:`~pyckt.io.Specifications` object, structurally filters
   candidate topologies (by complementary / fully-differential flags),
   sizes each candidate, and returns a ranked list best-first.

Main classes
------------
* :class:`TopologySpec` / :class:`TopologyLibrary` — metadata + keyed store
* :class:`TopologyConverter` — topogen ``Circuit`` → ``pyckt.core.Circuit``
* :class:`TopologyLibraryGenerator` — runs the full HL2–HL5 enumeration
* :class:`SynthesisEngine` — filter / size / rank pipeline
* :class:`~pyckt.synthesis.analysis.SynthesisAnalysis` — the
  ``--analysis synthesis`` CLI dispatch endpoint (see :mod:`pyckt.cli`).

Typical usage
-------------
::

    from pyckt.synthesis import TopologyLibraryGenerator, SynthesisEngine
    library = TopologyLibraryGenerator(output_dir=None).generate()
    results = SynthesisEngine(library, specifications).synthesize()
    for spec, sizing in results[:10]:
        print(spec.name, sizing.performance.gain_db)
"""
from pyckt.synthesis.analysis import SynthesisAnalysis
from pyckt.synthesis.converter import TopologyConverter
from pyckt.synthesis.engine import SynthesisEngine
from pyckt.synthesis.generator import TopologyLibraryGenerator
from pyckt.synthesis.library import TopologyLibrary, TopologySpec

__all__ = [
    "TopologySpec",
    "TopologyLibrary",
    "TopologyConverter",
    "TopologyLibraryGenerator",
    "SynthesisEngine",
    "SynthesisAnalysis",
]
