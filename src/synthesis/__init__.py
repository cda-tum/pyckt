"""synthesis — Topology library + specification-driven search.

Two complementary capabilities:

1. **Topology library generation** —
   :class:`TopologyLibraryGenerator` enumerates every valid op-amp
   topology by chaining the :mod:`topogen` HL2–HL5 factories.  Each
   topogen :class:`~topogen.common.circuit.Circuit` is converted to a
   flat :class:`core.Circuit` via :class:`TopologyConverter`, then
   indexed by a :class:`TopologySpec` (id, name, num_stages, etc.) and
   collected into a :class:`TopologyLibrary`.
2. **Synthesis** —
   :class:`SynthesisEngine` takes a populated library + a
   :class:`~ckt_io.Specifications` object, structurally filters
   candidate topologies (by complementary / fully-differential flags),
   sizes each candidate, and returns a ranked list best-first.

Main classes
------------
* :class:`TopologySpec` / :class:`TopologyLibrary` — metadata + keyed store
* :class:`TopologyConverter` — topogen ``Circuit`` → ``core.Circuit``
* :class:`TopologyLibraryGenerator` — runs the full HL2–HL5 enumeration
* :class:`SynthesisEngine` — filter / size / rank pipeline
* :class:`~synthesis.analysis.SynthesisAnalysis` — the
  ``--analysis synthesis`` CLI dispatch endpoint (see :mod:`cli`).

Typical usage
-------------
::

    from synthesis import TopologyLibraryGenerator, SynthesisEngine
    library = TopologyLibraryGenerator(output_dir=None).generate()
    results = SynthesisEngine(library, specifications).synthesize()
    for spec, sizing in results[:10]:
        print(spec.name, sizing.performance.gain_db)
"""
from synthesis.analysis import SynthesisAnalysis
from synthesis.converter import TopologyConverter
from synthesis.engine import SynthesisEngine
from synthesis.generator import TopologyLibraryGenerator
from synthesis.library import TopologyLibrary, TopologySpec

__all__ = [
    "TopologySpec",
    "TopologyLibrary",
    "TopologyConverter",
    "TopologyLibraryGenerator",
    "SynthesisEngine",
    "SynthesisAnalysis",
]
