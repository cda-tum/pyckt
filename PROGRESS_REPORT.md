# pyckt — Progress Report

**Project:** Python re-implementation of **acst** (Analog Circuit Synthesis Tool, TU München)
**Author:** Firas
**Date:** 2026-06-26
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
| **toplibgen** — topology library gen | ✅ enumeration + acst-format emitter | 7 020 topologies; real ACST-format netlists; FullyDifferential count exact match (936/936) | ◑ Emitter done, topology-set parity open |

**Headline:** all six modes run end-to-end. The three deterministic
*recognition* modes (structrec, partitioning, rulegen) now reproduce acst's
output essentially **exactly**. Sizing reproduces acst's output *format* and
*performance models*; the optimiser is not yet tuned to the same operating
point. **toplibgen** now has a real ACST-format netlist writer (`--output-format
acst`) instead of placeholder bodies — FullyDifferential topology counts match
the acst benchmark exactly; SingleOutput/Complementary counts still diverge
(open item, see §6). Synthesis still emits placeholder netlist bodies — that
mode's emitter is the next piece in this vein.

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
(see `src/pyckt/api.py`).

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

### 4.5 synthesis — ◑ framework complete, netlist bodies still placeholders
- Enumerates and ranks **4 914** candidate topologies (rank/score/gain/power/
  area/ft) →
  [`samples/synthesis/synthesis_ranking_pyckt.json`](samples/synthesis/synthesis_ranking_pyckt.json).
- The ranking, scoring and file-emission framework is complete; the
  **per-topology netlist bodies are still placeholders** (next phase — same
  treatment toplibgen just got, see below).
- acst's synthesis is a combinatorial generator that exceeds the short run
  budget (minutes), so a direct output diff is deferred until acst is run to
  completion offline.

### 4.6 toplibgen — ◑ acst-format netlists done, topology-set parity open
- Enumerates **7 020** op-amp topologies (up from the previously-reported
  1 725 — the full HL2–HL5 factory sweep, not a subset), all converting to a
  flat circuit without error.
- **New this period:** `toplibgen --output-format acst` — a real
  `AcstNetlistWriter` emits one ACST-format `.ckt` netlist per topology
  (`.suckt`/`.end`, `nmos`/`pmos` models, bulk column) into acst's three
  category directories, replacing the placeholder netlist bodies.
- Per-category counts vs the acst reference (`acst/InputFileExamples/
  TopologyLibraryGeneration/Netlists/`):

  | Category | acst | pyckt | Match? |
  |----------|-----:|------:|:--:|
  | FullyDifferentialOpAmps | 936 | 936 | ✅ exact |
  | SingleOutputOpAmps | 2 940 | 4 914 | ✗ |
  | ComplementaryOpAmps | 36 | 1 170 | ✗ |

  FullyDifferential is an **exact count match**. SingleOutput and
  Complementary diverge — the two generators don't yet enumerate the identical
  topology set (acst additionally distinguishes a two-stage op-amp's first/
  second-stage indices and a `symmetrical_op_amp` sub-family that pyckt's
  `TopologySpec` doesn't carry yet). Reconciling that enumeration is the
  remaining "topology-set parity" item — see §6.
- Driven by [`scripts/run_toplibgen.sh`](scripts/run_toplibgen.sh)
  (pyckt-only; acst's toplibgen run is a multi-minute benchmark, not exercised
  per-invocation). 23 new tests in `tests/test_toplibgen_acst.py`.

---

## 5. What changed recently (this reporting period)

- **Package layout flattened** — the engines (`core`, `io`→`ckt_io`, `sizing`,
  `synthesis`, `utils`, `cli`) moved out of `src/pyckt/` to the `src/` top level
  alongside `topogen`/`recognition`/`partitioning`; `pyckt/` now holds only the
  public API facade. ~372 imports across 69 files rewritten; full suite still
  857-green. Addresses supervisor feedback §2. Also added module docstrings to
  the previously-bare `topogen` HL2–HL5 / `common` sub-packages.
- **Python API** (`src/pyckt/api.py`, re-exported from `pyckt/__init__.py`) —
  one typed function per mode (`recognize` / `generate_rules` / `partition` /
  `size` / `synthesize` / `generate_topology_library`), each a thin wrapper over
  the existing analysis lifecycle with optional file output. 13 new tests in
  `tests/test_api.py`. Addresses supervisor feedback §4.
- **Sphinx documentation** (`docs/`) — `autodoc` + `napoleon` + `furo`, one page
  per package plus a Python-API quick-start; `docs` extra added to
  `pyproject.toml`. Addresses supervisor feedback §3.
- **toplibgen acst-format emitter** — new `AcstNetlistWriter`
  (`src/pyckt/io/hspice_writer.py`), `TopologySpec.acst_category()` /
  `.acst_name_prefix()`, and `TopologyLibrary.to_acst_directory()`
  (`src/pyckt/synthesis/library.py`). `toplibgen --output-format acst` now
  writes real per-topology netlists into acst's `SingleOutputOpAmps` /
  `FullyDifferentialOpAmps` / `ComplementaryOpAmps` layout instead of
  placeholder stubs. FullyDifferential count now matches acst exactly (936/936).
- **Per-mode run scripts** added (`scripts/run_{structrec,partitioning,rulegen,
  toplibgen}.sh` + `scripts/SCRIPTS.md`) — each mode runnable standalone,
  repo-relative, pyckt-only where the acst reference is too slow to run
  routinely (toplibgen).
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

## 6. Remaining work (current stopping point — pick up here)

1. **Sizing optimiser tuning (main item):** make the CP-SAT solver converge to
   acst's operating point (objective/constraints currently under-size the design);
   reconcile Ft and phase-margin models. Add the few still-missing emit fields
   (net voltages, capacitor dimensions, CMRR/PSRR).
2. **toplibgen topology-set parity (next, in progress):** pyckt's
   SingleOutputOpAmps (4 914 vs acst 2 940) and ComplementaryOpAmps (1 170 vs
   acst 36) counts don't match the benchmark — only FullyDifferential does
   (936/936). Define a name-independent topology signature and reconcile the
   generation rules (cascode variants, the `symmetrical_op_amp` sub-family,
   stage-index naming) until the sets align, or document the residual gap if
   exact parity proves infeasible. See `scripts/SCRIPTS.md` and the
   `outputs/toplibgen/py_acst/` counts for the measurable baseline.
3. **synthesis netlist bodies:** still placeholders — give it the same
   `AcstNetlistWriter`-based treatment toplibgen just got.
4. **rulegen:** reconcile the one mis-leveled library item + per-item persistence.
5. **partitioning ergonomics:** derive input/output/bias nets from the recognized
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

# or, equivalently, via the standalone per-mode scripts (repo-relative):
cd /home/jrad/pyckt/pyckt
./scripts/run_structrec.sh      # also runs the acst reference if present
./scripts/run_toplibgen.sh      # pyckt-only — prints per-category counts

# validate all modes against the acst reference outputs:
cd /home/jrad/throwaway && python3 compare_acst.py
```
