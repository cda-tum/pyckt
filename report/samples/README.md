# Output samples — pyckt vs acst

Side-by-side outputs for each analysis mode, regenerated 2026-07-09 on the same
input bundles. acst is the reference; `*_pyckt.*` files are pyckt's
`--output-format acst` output. See [`../PROGRESS_REPORT.md`](../PROGRESS_REPORT.md)
and [`../comparison/COMPARISON_REPORT.md`](../comparison/COMPARISON_REPORT.md).

| Mode | Files | What to look at |
|------|-------|-----------------|
| `structrec/` | `structrec_acst.xml`, `structrec_pyckt.xml` | Same structure tree — 16/16 devices, identical hierarchy (2 886/2 886 across the full gallery). |
| `partitioning/` | `partitioning_acst.xml`, `partitioning_pyckt.xml` | Same gm-path/stage sections — 19/19 devices in the same bucket. |
| `rulegen/` | `rulegen_library_{acst,pyckt}.xml`, `rulegen_item_example_pyckt.xml` | Same `pairLibrary` — 10/10 items, levels and persistence match. |
| `sizing/` | `sizing_result_{acst,pyckt}.xml`, `sized_netlist_pyckt.hspice` | Every field present on both sides (CMRR/PSRR/CM-range/Voltages/Capacitors); pyckt also writes a fully-sized netlist. |
| `synthesis/` | `synthesis_ranking_pyckt.json`, `rank_001_candidate.ckt` | 2 836 candidates ranked on real solved performance; the top candidate is a fully dimensioned (`W=…/L=…`) netlist. |

Note: acst's sizing/synthesis numbers are one draw from a randomized,
time-bounded search — see the comparison report for why the exact W/L values
differ run-to-run even for acst against itself.
