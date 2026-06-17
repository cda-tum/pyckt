"""pyckt.sizing — Automatic transistor sizing via constraint programming.

Wraps Google OR-Tools' CP-SAT solver to size every MOSFET in an
op-amp such that the chosen widths, lengths, currents and overdrive
voltages satisfy:

* Transistor model equations (SHM by default — strong-inversion
  saturation Id = (μCox/2)·(W/L)·Vov², plus gm, gds, area, …).
* KCL at every internal net (currents balance).
* Sizing rules from structure recognition (matched pairs share W/L).
* Performance specifications (gain, bandwidth, slew rate, power, area,
  output swing).
* Frequency-domain poles & zeros (basic phase-margin shaping).

Main classes
------------
* :class:`~pyckt.sizing.problem.SizingProblem` — assembles the complete
  CSP from a parsed circuit + recognition + partition + rules + specs.
* :class:`~pyckt.sizing.solver.SizingSolver` — drives CP-SAT to solve
  the assembled problem.
* :class:`~pyckt.sizing.result.SizingResult` — solved sizings + an
  estimated :class:`ExpectedPerformance` summary.
* :class:`~pyckt.sizing.writer.SizingXMLWriter` /
  :class:`~pyckt.sizing.writer.SizedCircuitWriter` — XML and HSpice
  output writers.
* :class:`~pyckt.sizing.analysis.AutomaticSizingAnalysis` — the
  ``--analysis automaticsizing`` CLI dispatch endpoint that runs the
  full pipeline (parse → recognise → partition → rulegen → assemble →
  solve → write).

Typical usage
-------------
::

    from pyckt.sizing.problem import SizingProblem
    from pyckt.sizing.solver  import SizingSolver
    problem = SizingProblem.build(circuit, partition, rules, circuit_info)
    result = SizingSolver(problem).solve()
"""
