# pyckt — Progress Report

**Project:** Python re-implementation of **acst** (Analog Circuit Synthesis Tool, TU München)
**Author:** Firas
**Date:** 2026-06-05
**Repositories:**
- pyckt (Python, this work): `https://github.com/cda-tum/pyckt`
- acst (C++, reference): `https://github.com/inga000/acst`

---

## 1. Goal

Translate the acst C++ analog-circuit-synthesis tool (~112 k lines of C++) into a
maintainable Python package (**pyckt**), reproducing the same six analysis modes
and — as far as possible — the **same outputs** so the Python tool can be
validated against the original.

acst is the reference: for any given input, pyckt should produce functionally
equivalent results.

---

## 2. Where we stand — at a glance

| Analysis mode | Pipeline implemented | Output vs acst | State |
|---------------|:--:|----------------|-------|
| **structrec** — structure recognition | ✅ | **16/16 devices + full hierarchy match** | ✅ Done |
| **partitioning** — circuit partitioning | ✅ | **19/19 devices same section** | ✅ Done |
| **rulegen** — sizing-rule generation | ✅ | **10/10 library items, 9/10 same level** | ✅ Done |
| **automaticsizing** — CP-SAT sizing | ✅ | schema + performance models match; W/L not yet converged | ◑ Functional, tuning |
| **synthesis** — topology synthesis | ✅ pipeline | ranked list (4 914 candidates); netlist bodies are placeholders | ◑ Framework done |
| **toplibgen** — topology library gen | ✅ enumeration | 1 725 topologies enumerated; netlist bodies are placeholders | ◑ Framework done |

**Headline:** all six modes run end-to-end. The three deterministic
*recognition* modes (structrec, partitioning, rulegen) now reproduce acst's
output essentially **exactly**. Sizing reproduces acst's output *format* and
*performance models*; the optimiser is not yet tuned to the same operating
point. Synthesis/toplibgen have the full enumeration+ranking framework; the
per-topology netlist generation is the next implementation phase.

---

## 3. Implementation status

**Codebase:** ~16 800 lines of Python across 78 modules, **821 tests**.

| Module | Lines | What it does |
|--------|------:|--------------|
| `src/pyckt/` (core + IO) | 7 051 | netlist/XML parsing, device model, CP-SAT sizing, CLI |
| `src/topogen/` | 4 698 | topology enumeration (synthesis + toplibgen) |
| `src/recognition/` | 3 194 | structure recognition engine + library |
| `src/partitioning/` | 1 844 | gm-path/stage partitioner |

**Cross-validation layer (new):** pyckt now has an **acst-compatible output
writer** (`--output-format acst`). Each mode can emit XML in acst's exact schema
(element names, units, `/`-prefixed nets, `[instance]` indices), so outputs can
be diffed tag-for-tag against the C++ reference instead of by eye. This was the
key enabler for the validation results below.

---

## 4. Results — pyckt vs acst

Same input bundle on both tools; acst is the reference. Comparison driven by
`comparison/compare_acst.py`. Full detail in
[`comparison/COMPARISON_REPORT.md`](comparison/COMPARISON_REPORT.md).

### 4.1 structrec — ✅ exact match
- **16/16** leaf devices assigned to the same structure.
- **16/16** devices in the same top-level composite.
- Full hierarchy type-count identical (2× CascodeCurrentMirror, 2× DiffPair,
  2× SimpleCurrentMirror, 2× DiodeStack, 2× CascodePair, 6× DiodeArray, 10× NormalArray).
- A previous mismatch (spurious `MosfetLevelShifter`, and a swapped
  `Input1`/`Input2` on the differential pair) was **found and fixed** this week.
- Sample: [`samples/structrec/`](samples/structrec/) (acst vs pyckt, side by side).

### 4.2 partitioning — ✅ exact match
- **19/19** devices land in the same section.
- Same gm-path decomposition: firstStage / primarySecondStage / secondarySecondStage,
  loadParts, biasParts, capacitances — section counts identical.
- This was the **largest divergence** at the start (only 1/6 agreed); pyckt's
  partitioner was re-implemented to acst's stage logic and now matches fully.
- Sample: [`samples/partitioning/`](samples/partitioning/).

### 4.3 rulegen — ✅ near-exact match
- Emits the same `pairLibrary` artifact (top-level library + per-item XML with
  full `pairConnection` / `characteristicConnection` / `recognitionRules`).
- **10/10** library items; **9/10** at the same hierarchy level.
- Sample: [`samples/rulegen/`](samples/rulegen/).

### 4.4 automaticsizing — ◑ format & models match, optimiser tuning open

**Solver background — CP-SAT:**
Searches a discrete grid of W/L values for an assignment that satisfies all circuit constraints (KCL, operating region, gain/power/phase-margin targets) while minimising area. Chosen over gradient-based methods because transistor dimensions are inherently discrete and constraints are hard. acst uses **Gecode**; pyckt uses **OR-Tools CP-SAT** — same paradigm, different implementation, which is why outputs don't match yet even with equivalent constraints.

- Output **schema matches** acst (ExpectedPerformance / Currents / Dimensions).
- Performance models that were previously stubbed are now implemented:

  | Metric | acst | pyckt | Δ |
  |--------|-----:|------:|--:|
  | Gain (dB) | 90.0 | 91.3 | **1.4 %** ✅ |
  | Slew rate (V/µs) | 22.5 | 24.5 | **8.8 %** ✅ |
  | Power (mW) | 6.12 | 7.53 | 23 % ◑ |
  | Phase margin (°) | 60.7 | 87.2 | ✗ |
  | Transit freq (MHz) | 6.93 | 23.1 | ✗ |
  | Area (µm²) | 10 868 | 207 | ✗ |

- The **solver does not yet reach acst's operating point** (it under-sizes most
  transistors). This is the main open numeric item.
- pyckt **does** produce a valid, fully sized HSPICE netlist —
  [`samples/sizing/sized_netlist_pyckt.hspice`](samples/sizing/sized_netlist_pyckt.hspice).

### 4.5 synthesis & toplibgen — ◑ framework complete
- **synthesis**: enumerates and ranks **4 914** candidate topologies
  (rank/score/gain/power/area/ft) →
  [`samples/synthesis/synthesis_ranking_pyckt.json`](samples/synthesis/synthesis_ranking_pyckt.json).
- **toplibgen**: enumerates **1 725** op-amp topologies (133 one-stage +
  1 592 two-stage), each with structured metadata.
- The ranking, scoring, enumeration and file-emission framework is complete; the
  **per-topology netlist bodies are still placeholders** (next phase).
- acst's synthesis/toplibgen are combinatorial generators that exceed the
  short run budget (minutes–hours), so a direct output diff is deferred until
  acst is run to completion offline.

---

## 5. What changed recently (this reporting period)

- Added the **acst-compatible output writer** across all deterministic modes —
  enabling tag-for-tag validation.
- **partitioning** re-implemented to acst's gm-path/stage semantics → 1/6 → 19/19.
- **structrec** composite grouping fixed → full hierarchy now matches (16/16).
- **structrec** symmetric-pin-label bug fixed (differential-pair `Input1`/`Input2`
  now match acst's convention).
- **automaticsizing** performance models (Ft, slew rate, phase margin) implemented
  (previously returned 0).
- Parser robustness fixes unblocked clean runs on the standard input bundle.

---

## 6. Remaining work

1. **Sizing optimiser tuning (main item):** make the CP-SAT solver converge to
   acst's operating point (objective/constraints currently under-size the design);
   reconcile Ft and phase-margin models. Add the few still-missing emit fields
   (net voltages, capacitor dimensions, CMRR/PSRR).
2. **synthesis / toplibgen netlists:** implement the real per-topology netlist
   bodies (currently placeholders), then validate against acst run to completion.
3. **rulegen:** reconcile the one mis-leveled library item + per-item persistence.
4. **partitioning ergonomics:** derive input/output/bias nets from the recognized
   structure tree (as acst does) to drop the extra `--circuit-params` input.

---

## 7. How to reproduce

Exact per-mode commands (acst and pyckt) are listed in
[`comparison/COMPARISON_REPORT.md` §0](comparison/COMPARISON_REPORT.md). In short:

```bash
PYCKT=/home/jrad/pyckt/pyckt/.venv/bin/pyckt
# e.g. structure recognition in acst-compatible output:
$PYCKT structrec --circuit input.ckt --device-types deviceTypes.xcat \
   --mapping HSpiceMapping.xcat --supply-nets supplyNets.xcat \
   --output-format acst --output structrec_pyckt.xml

# validate all modes against the acst reference outputs:
cd /home/jrad/throwaway && python3 compare_acst.py
```
