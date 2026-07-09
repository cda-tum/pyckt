# pyckt Progress Report — 2026-06-05

Material for the 1:1 progress meeting. Project: **translating the acst C++
analog-circuit-synthesis tool into Python (pyckt)**.

## Contents

| Path | What |
|------|------|
| [`PROGRESS_REPORT.md`](PROGRESS_REPORT.md) | **Main report** — status, results, remaining work |
| [`slides/pyckt_progress.pptx`](slides/pyckt_progress.pptx) | Talking-point slides for the meeting |
| [`comparison/COMPARISON_REPORT.md`](comparison/COMPARISON_REPORT.md) | Detailed acst-vs-pyckt output comparison (all modes, exact commands) |
| [`comparison/compare_acst.py`](comparison/compare_acst.py) | The comparison script behind the numbers |
| [`samples/`](samples/) | Real generated outputs (see below) |

## Sample outputs (`samples/`)

| Folder | File | What it shows |
|--------|------|---------------|
| `structrec/` | `*_acst.xml`, `*_pyckt.xml` | recognized structure hierarchy — acst vs pyckt (match) |
| `partitioning/` | `*_acst.xml`, `*_pyckt.xml` | partitioning annotation (gm-path stages, bias, load) — match |
| `rulegen/` | `*_library_*.xml`, `*_item_example_pyckt.xml` | learned sizing-rule library + one item |
| `sizing/` | `sized_netlist_pyckt.hspice` | **generated sized netlist** (real output) |
| `sizing/` | `sizing_result_{acst,pyckt}.xml` | sizing result, acst vs pyckt |
| `synthesis/` | `synthesis_ranking_pyckt.json`, `rank_001_candidate.ckt` | ranked topology candidates |

## One-line status

All six analysis modes run end-to-end. The three deterministic recognition modes
(**structrec, partitioning, rulegen**) reproduce acst's output essentially
exactly. **Sizing** matches acst's output format and performance models (solver
tuning open). **Synthesis/toplibgen** have the full enumeration+ranking framework
(per-topology netlist bodies are the next phase).
