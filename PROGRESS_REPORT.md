# pyckt — Progress Report

**Project:** Python re-implementation of **acst** (Analog Circuit Synthesis Tool, TU München)
**Author:** Firas
**Date:** 2026-07-01
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
| **rulegen** — sizing-rule generation | ✅ | **10/10 library items — level AND persistence exact match acst** | ✅ Done |
| **automaticsizing** — CP-SAT sizing | ✅ | schema + performance models match; W/L not yet converged | ◑ Functional, tuning |
| **synthesis** — topology synthesis | ✅ pipeline | ranked list (4 914 candidates); real `AcstNetlistWriter` netlists per candidate | ◑ Netlist done, solver stub |
| **toplibgen** — topology library gen | ✅ enumeration + acst-format emitter | 3 912 distinct topologies; real ACST-format netlists. **Full topology-set parity: 3912/3912 device-for-device** (2940/936/36 per category) — see §4.6 | ✅ Set parity reached (issue #20) |

**Headline:** all six modes run end-to-end. The three deterministic
*recognition* modes (structrec, partitioning, rulegen) now reproduce acst's
output **exactly** — rulegen's hierarchy levels and per-item persistence now
match the acst reference item-for-item (10/10). Sizing reproduces acst's
output *format* and *performance models*; the optimiser is not yet tuned to the
same operating point. Both **toplibgen** and **synthesis** now use
`AcstNetlistWriter` to emit real, parseable ACST-format `.ckt` netlists instead
of placeholder stubs. FullyDifferential topology counts match the acst benchmark
exactly; SingleOutput/Complementary counts still diverge (open item, see §6).

---

## 3. Implementation status

**Codebase:** ~17 500 lines of Python across 79 modules, **857 tests**.

**Package layout (flattened this period):** the analysis engines are now
top-level packages under `src/` — `core`, `ckt_io`, `sizing`, `synthesis`,
`utils`, `cli`, alongside `topogen`, `recognition`, `partitioning` — and
`pyckt/` keeps only the public API facade (`__init__.py` + `api.py`). (`ckt_io`
rather than `io`, to avoid shadowing the stdlib `io` module.)

| Package(s) | What it does |
|------------|--------------|
| `core` + `ckt_io` | netlist/XML parsing, device model, IO writers |
| `sizing` | CP-SAT sizing solver |
| `synthesis` | topology library + synthesis search |
| `topogen` | topology enumeration (HL2–HL5 factories) |
| `recognition` | structure recognition engine + library |
| `partitioning` | gm-path/stage partitioner |
| `cli` + `pyckt` | CLI dispatcher + typed public Python API |

**Two entry points:** every mode is reachable both from the `pyckt` **CLI** and
from a typed **Python API** (`pyckt.recognize`, `pyckt.partition`, `pyckt.size`,
`pyckt.generate_rules`, `pyckt.synthesize`, `pyckt.generate_topology_library`) —
each a thin, documented wrapper over the same analysis pipeline that returns the
mode's typed result object and writes to disk only when an output path is given
(see `src/pyckt/api.py`). `pyckt.synthesize()` returns a
`list[SynthesisCandidate]` (a dataclass with `rank`, `topology`, `sizing`,
`score` fields) rather than a raw `list[tuple]`.

**Documentation:** a Sphinx site (`docs/`, `autodoc` + `napoleon` + `furo`,
built via `pip install -e ".[docs]"` then `sphinx-build -b html docs
docs/_build/html`) renders the API and per-package reference from the in-source
docstrings.

**Cross-validation layer:** pyckt has an **acst-compatible output writer**
(`--output-format acst`) across all six modes. Each mode can emit XML/netlists
in acst's exact schema (element names, units, `/`-prefixed nets, `[instance]`
indices for the XML modes; `.suckt`/`.end` + `nmos`/`pmos` netlists for
toplibgen), so outputs can be diffed tag-for-tag, or counted category-for-
category, against the C++ reference instead of by eye. This was the key
enabler for the validation results below.

**Per-mode run scripts (new):** `scripts/run_{structrec,partitioning,rulegen,
toplibgen}.sh` each drive one mode standalone — pyckt in acst format, plus the
acst reference when its binary is present (toplibgen is pyckt-only; acst's
generator there is a multi-minute benchmark, not something to run on every
invocation). Scripts are repo-relative (derive `PYCKT`/`PY_IN`/`OUT` from their
own location), so they work right after a fresh clone with no host-path setup.
See [`scripts/SCRIPTS.md`](scripts/SCRIPTS.md).

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

### 4.3 rulegen — ✅ exact match
- Emits the same `pairLibrary` artifact (top-level library + per-item XML with
  full `pairConnection` / `characteristicConnection` / `recognitionRules`).
- **10/10** library items at the same hierarchy level with the same persistence
  value — exact match against the acst reference (`SymmetricalCascodeOpAmpLibrary.xml`).
- Root cause of the previous 1-item level mismatch (OpAmp5 at level 1 instead
  of level 2): greedy matching consumed DiodeArray's only shared-signal partner
  before the more-constrained pair was formed. Fixed by a most-constrained-first
  tie-break (`_pair_round` in `src/recognition/rule_learning.py`), mirroring
  acst's `PairLibraryItemCreator::build()` bucket/phase logic.
- Regression test: `tests/test_rule_learning.py::TestRuleLearner::test_levels_and_persistence_match_acst_reference`.
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

### 4.5 synthesis — ◑ real netlists done, solver stub pending
- Enumerates and ranks **4 914** candidate topologies (rank/score/gain/power/
  area/ft) →
  [`samples/synthesis/synthesis_ranking_pyckt.json`](samples/synthesis/synthesis_ranking_pyckt.json).
- The ranking, scoring and file-emission framework is complete. Each candidate
  now gets a **real `AcstNetlistWriter` `.ckt` netlist** (same writer as
  toplibgen) reflecting the topology's structural circuit — no longer a
  placeholder stub. The netlist is unsized (no W/L parameters): the
  `SynthesisEngine._size_topology()` solver is still a stub pending the real
  CP-SAT integration (the "automaticsizing" tuning item, see §6).
- When the topology library is loaded from a pre-built directory (metadata only,
  no circuit objects retained), the emitter gracefully falls back to a
  comment-only placeholder noting why, and logs a warning.
- acst's synthesis is a combinatorial generator that exceeds the short run
  budget (minutes), so a direct output diff is deferred until acst is run to
  completion offline.

### 4.6 toplibgen — ✅ full topology-set parity with acst (3912/3912)

- Enumerates **4 302** op-amp topologies (full HL2–HL5 factory sweep),
  collapsing to **3 912 structurally-distinct** circuits — **exactly acst's
  reference set, matched device-for-device with zero extras** (issue #20,
  PRs #22–#28), verified per category with the canonical signature harness
  ([`comparison/topology_signature.py`](comparison/topology_signature.py)):

  | Category | acst | pyckt distinct | Structural match |
  |----------|-----:|------:|:--:|
  | SingleOutputOpAmps | 2 940 | 2 940 | ✅ **2940/2940** |
  | FullyDifferentialOpAmps | 936 | 936 | ✅ **936/936** |
  | ComplementaryOpAmps | 36 | 36 | ✅ **36/36** |

- Per-category cross-tab (stage × output family; issue #8 — regenerate with
  `.venv/bin/python scripts/report_topology_counts.py`, full table in
  [`reports/TOPOLOGY_COUNTS.md`](reports/TOPOLOGY_COUNTS.md)):

  | | Single-ended | Symmetrical | Fully-differential | Complementary | total |
  |---|---:|---:|---:|---:|---:|
  | **1-stage** | 240 | 210 | 72 | 36 | 558 |
  | **2-stage** | 2 880 | 0 | 864 | 0 | 3 744 |
  | **total** | 3 120 | 210 | 936 | 36 | 4 302 |

  (Generated counts; 30 one-stage single-ended variants and their 360
  two-stage multiples are structural duplicates, giving the 3 912 distinct
  set. The symmetrical family is acst's one-stage-only `symmetrical_op_amp`
  sub-family of `SingleOutputOpAmps`.)

- `toplibgen --output-format acst` emits one ACST-format `.ckt` netlist per
  topology (`.suckt`/`.end`, `nmos`/`pmos` models, bulk column) into acst's
  three category directories. The full root-cause history (flatten
  union-find, composition ports, bias-completion reconciliation,
  improved-Wilson/cascode-GCC biases) is chronicled in
  [`comparison/TOPLIBGEN_PARITY_ANALYSIS.md`](comparison/TOPLIBGEN_PARITY_ANALYSIS.md).
- Driven by [`scripts/run_toplibgen.sh`](scripts/run_toplibgen.sh)
  (pyckt-only; acst's toplibgen run is a multi-minute benchmark, not exercised
  per-invocation). 23 new tests in `tests/test_toplibgen_acst.py`.

---

## 5. What changed recently (this reporting period)

Changes in this period are tracked as GitHub Issues and Pull Requests on
[`Firas-Jrad/pyckt`](https://github.com/Firas-Jrad/pyckt). Branches cut from
`jrad`, PRs target `jrad` (not `main`, which is the stale cda-tum snapshot).

**Issues closed this period (PRs merged into `jrad`):**

- **[#11](https://github.com/Firas-Jrad/pyckt/issues/11) — typed return for
  `synthesize()`** (PR #13) — introduced a `SynthesisCandidate` dataclass
  (`rank`, `topology`, `sizing`, `score`) and updated `pyckt.synthesize()` to
  return `list[SynthesisCandidate]` instead of a raw `list[tuple]`.
  `SynthesisCandidate` is exported from `pyckt` alongside the existing typed
  results. 4 new tests in `tests/test_api.py`.

- **[#10](https://github.com/Firas-Jrad/pyckt/issues/10) — docstring gaps in
  topogen HL2–HL5** (PR #12) — filled module-level and class-level docstrings
  for the 15 previously-bare `topogen` sub-packages and factory classes
  (`common/`, `hl2/`–`hl5/`). `sphinx-build -W` now passes clean (0 warnings)
  without `suppress_warnings`.

- **[#9](https://github.com/Firas-Jrad/pyckt/issues/9) — Sphinx duplicate-
  object warnings** (PR #14) — root cause: `undoc-members` + Napoleon's
  Attributes section double-documented bare dataclass field annotations (72 of
  77 warnings). Fix: removed `undoc-members` from `conf.py`. A second root
  cause (two distinct `Circuit` classes sharing the same short name) fixed via
  `:no-index:` on the topogen variant. Build now passes `sphinx-build -W`
  with zero warnings.

- **[#4](https://github.com/Firas-Jrad/pyckt/issues/4) — synthesis real
  netlist emitter** (PR #15) — `SynthesisAnalysis.write()` now uses
  `AcstNetlistWriter` to emit a real `.ckt` per ranked candidate, matching the
  treatment toplibgen already had. Graceful fallback (comment-only placeholder
  + warning log) when the library was loaded from a pre-built directory and
  carries no circuit objects. 4 new tests in `tests/test_synthesis.py`.

- **[#5](https://github.com/Firas-Jrad/pyckt/issues/5) — rulegen level/
  persistence mismatch** (PR #16) — reverse-engineered acst's
  `PairLibraryItemCreator::build()` bucket/phase logic; added a
  most-constrained-first tie-break to `_pair_round()` in
  `src/recognition/rule_learning.py`. Result: 10/10 items at the correct
  hierarchy level, all persistence values match the acst reference. Regression
  test pinned in `tests/test_rule_learning.py`.

**Earlier in the session (pre-Issues workflow):**

- **Package layout flattened** — the engines (`core`, `io`→`ckt_io`, `sizing`,
  `synthesis`, `utils`, `cli`) moved out of `src/pyckt/` to the `src/` top level
  alongside `topogen`/`recognition`/`partitioning`; `pyckt/` now holds only the
  public API facade. ~372 imports across 69 files rewritten; full suite still
  867-green. Addresses supervisor feedback §2.
- **Python API** (`src/pyckt/api.py`, re-exported from `pyckt/__init__.py`) —
  one typed function per mode, each a thin wrapper over the existing analysis
  lifecycle with optional file output. Addresses supervisor feedback §4.
- **Sphinx documentation** (`docs/`) — `autodoc` + `napoleon` + `furo`, one page
  per package plus a Python-API quick-start. Addresses supervisor feedback §3.
- **toplibgen acst-format emitter** — `AcstNetlistWriter`, `acst_category()` /
  `acst_name_prefix()`, `to_acst_directory()`. `toplibgen --output-format acst`
  writes real per-topology netlists; the full library now matches acst
  device-for-device in every category (3912/3912, issue #20 — §4.6).
- **Per-mode run scripts** — `scripts/run_{structrec,partitioning,rulegen,
  toplibgen}.sh` + `scripts/SCRIPTS.md`.
- **partitioning** re-implemented to acst's gm-path/stage semantics → 19/19.
- **structrec** composite grouping + symmetric-pin-label fixed → 16/16.
- **automaticsizing** performance models (Ft, slew rate, phase margin)
  implemented (previously returned 0).

---

## 6. Remaining work (current stopping point — pick up here)

Open GitHub Issues on [`Firas-Jrad/pyckt`](https://github.com/Firas-Jrad/pyckt):

**Ready for agent (self-contained, no decision needed):**

- **[#1](https://github.com/Firas-Jrad/pyckt/issues/1) — automaticsizing: missing
  XML emit fields** — net voltages, capacitor dimensions, CMRR/PSRR are not yet
  written to the output XML. Add the missing fields; verify schema against acst.
- **[#7](https://github.com/Firas-Jrad/pyckt/issues/7) — FUBOCO gallery
  comparison** — run pyckt's structrec and sizing against the `s-1-2` and
  `fd-1-2` reference circuits from `analog-ml/fuboco-gallery`; report exact
  diffs (same format as `COMPARISON_REPORT.md`).
- **[#8](https://github.com/Firas-Jrad/pyckt/issues/8) — per-category op-amp
  count table** — add a stage × output-type count table to this report (data
  already computed by `TopologyLibraryGenerator`; needs a small reporting
  script/notebook cell).

**Need your judgment call first (labeled `ready-for-human`):**

- **[#2](https://github.com/Firas-Jrad/pyckt/issues/2) — automaticsizing: CP-SAT
  solver convergence** — the solver doesn't yet reach acst's operating point
  (under-sizes most transistors). Needs a decision on the Ft/phase-margin model
  tuning approach before agent work resumes.
- **[#3](https://github.com/Firas-Jrad/pyckt/issues/3) — toplibgen: topology-set
  parity** — SingleOutputOpAmps (4 914 pyckt vs 2 940 acst) and
  ComplementaryOpAmps (1 170 vs 36) still diverge. Needs a decision on whether
  to reconcile the enumeration rules or document the residual gap.
- **[#6](https://github.com/Firas-Jrad/pyckt/issues/6) — partitioning ergonomics**
  — derive input/output/bias nets from the recognized structure tree (as acst
  does) so `--circuit-params` is no longer required. Needs a decision on the
  net-inference strategy.

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

# or, equivalently, via the standalone per-mode scripts (repo-relative):
cd /home/jrad/pyckt/pyckt
./scripts/run_structrec.sh      # also runs the acst reference if present
./scripts/run_toplibgen.sh      # pyckt-only — prints per-category counts

# validate all modes against the acst reference outputs:
cd /home/jrad/throwaway && python3 compare_acst.py
```
