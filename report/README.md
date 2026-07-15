# pyckt Progress Report — 2026-07-15

Material for the 1:1 progress meeting. Project: **translating the acst C++
analog-circuit-synthesis tool into Python (pyckt)**.

## Contents

| Path | What |
|------|------|
| [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md) | **One-page summary** for the supervisor — bottom line + result table |
| [`PROGRESS_REPORT.md`](PROGRESS_REPORT.md) | **Main report** — status, results, remaining work |
| [`comparison/COMPARISON_REPORT.md`](comparison/COMPARISON_REPORT.md) | Detailed acst-vs-pyckt output comparison (all modes, exact commands) |
| [`comparison/compare_acst.py`](comparison/compare_acst.py) | The comparison script behind the numbers |
| [`output_comp/`](output_comp/) | **Fresh, controlled re-run** of both tools on the same inputs, outputs collected side by side (see below) |

## Side-by-side outputs (`output_comp/`)

A clean re-run of both tools under matched conditions, with the real generated
outputs kept for inspection. Findings: [`output_comp/FINDINGS.md`](output_comp/FINDINGS.md);
driver: [`output_comp/run_all.sh`](output_comp/run_all.sh) + [`compare.py`](output_comp/compare.py).

| Folder | What it holds (`acst/` vs `pyckt/`) |
|--------|-------------------------------------|
| `output_comp/structrec/` | recognized structure hierarchy — acst vs pyckt (identical multiset) |
| `output_comp/partitioning/` | partitioning annotation (gm-path stages, bias, load) — same sections |
| `output_comp/rulegen/` | learned recognition library + items (10/10 match) |
| `output_comp/automaticsizing/` | sizing result XML + sized netlist, acst vs pyckt |
| `output_comp/toplibgen/` | generated topology library (device-for-device parity) |
| `output_comp/synthesis/` | ranked, real-sized topology candidates |
| `output_comp/set2/` | a **second** condition set (different circuit, 1 µm scaling, acst's own library) |

## One-line status

All six analysis modes run end-to-end. The three deterministic recognition modes
(**structrec, partitioning, rulegen**) reproduce acst's output essentially
exactly (structrec **2 886/2 886**, partitioning **2 885/2 886**, rulegen
**10/10**). The three generative modes now produce **real, acst-comparable
output**: **sizing** matches every output field and reproduces acst's own
reference design to ~1 % (CMRR to 0.0 %); **toplibgen** reaches **3 912/3 912**
device-for-device topology parity; **synthesis** sizes every candidate with the
real CP-SAT solver and ranks them, covering **99.4 %** of acst's sized
topologies. Remaining sizing endpoint differences are acst's own randomized-search
variance, not a correctness gap.
