"""pyckt.recognition — Structure recognition for analog circuits.

Identifies analog building blocks (differential pairs, current mirrors,
cascode structures, level shifters, etc.) in a flat transistor netlist
using a library of structural patterns.

Main classes
------------
* :class:`~recognition.library.Library` — pattern library (XML on disk)
* :class:`~recognition.recognizer.StructureRecognizer` — top-level
  bottom-up recognition pipeline (Level 0 arrays → Level 3 pairs)
* :class:`~recognition.model.StructureCircuits` — hierarchical overlay
  on a flat circuit, indexed by recognition level
* :class:`~recognition.rulegen.RuleGenerator` — extracts sizing rules
  (matched pairs, equal W/L, equal length) from the structure overlay
* :class:`~recognition.writer.StructRecXMLWriter` /
  :class:`~recognition.writer.RuleXMLWriter` — XML output writers
* :class:`~recognition.analysis.StructRecAnalysis` /
  :class:`~recognition.analysis.RuleGenAnalysis` — the
  ``--analysis structrec`` and ``--analysis rulegen`` CLI dispatch
  endpoints (see :mod:`cli`)

Typical usage
-------------
::

    from recognition.library import Library
    from recognition.recognizer import StructureRecognizer
    from recognition.rulegen import RuleGenerator

    library = Library.from_directory()        # bundled XML defaults
    overlay = StructureRecognizer(library).recognize(circuit)
    rules = RuleGenerator().generate(overlay)
"""
