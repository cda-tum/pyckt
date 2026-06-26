"""sizing — Automatic transistor sizing via constraint programming.

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
* :class:`~sizing.problem.SizingProblem` — assembles the complete
  CSP from a parsed circuit + recognition + partition + rules + specs.
* :class:`~sizing.solver.SizingSolver` — drives CP-SAT to solve
  the assembled problem.
* :class:`~sizing.result.SizingResult` — solved sizings + an
  estimated :class:`ExpectedPerformance` summary.
* :class:`~sizing.writer.SizingXMLWriter` /
  :class:`~sizing.writer.SizedCircuitWriter` — XML and HSpice
  output writers.
* :class:`~sizing.analysis.AutomaticSizingAnalysis` — the
  ``--analysis automaticsizing`` CLI dispatch endpoint that runs the
  full pipeline (parse → recognise → partition → rulegen → assemble →
  solve → write).

Typical usage
-------------
::

    from sizing.problem import SizingProblem
    from sizing.solver  import SizingSolver
    problem = SizingProblem.build(circuit, partition, rules, circuit_info)
    result = SizingSolver(problem).solve()
"""
