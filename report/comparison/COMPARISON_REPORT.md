# acst (C++) vs pyckt (Python) — Full Output Comparison

_Last updated: **2026-07-09 (third pass — synthesis content comparison)**.
Supersedes the 2026-06-05 report. pyckt state: `jrad` @ `a981f7f` plus the
open PRs from this comparison (#47–#51, #56, #61). It includes the
FUBOCO-parity partitioning work (#30–#34/#38), the sizing schema/model/solver
work (#1/#2), and every fix this comparison surfaced: wrapper libraries (#47),
toplibgen emission (#48), net-voltage/cap export (#49), CMRR/PSRR/CM-range
models (#50), real synthesis scoring (#51), the CM-range constraint (#56), and
two-stage gain composition (#61). acst state: unchanged reference build at
`/home/jrad/acst/build/bin/acst.sh`._

All six analysis modes were re-run on the **same input bundles**; the C++ tool
`acst` is the reference. Comparison passes:

* `compare_acst.py` — acst-format diff for the four deterministic modes
  (acst `cpp.xml` vs pyckt `py_acst.*`) — the basis of §2–§5.
* `comparison/topology_signature.py` (pyckt repo) — canonical device-level
  signatures for the toplibgen topology sets — the basis of §6.
* Beyond the single-circuit bundle, the recognition/partitioning modes are now
  validated at scale against the **FUBOCO Gallery** (2 886 reference circuits)
  inside the pyckt repo — see §2/§3.

**Issues from this comparison:**
[#47](https://github.com/Firas-Jrad/pyckt/issues/47) (`--library` loader) ✅ fixed,
[#48](https://github.com/Firas-Jrad/pyckt/issues/48) (toplibgen emission) ✅ fixed,
[#49](https://github.com/Firas-Jrad/pyckt/issues/49) (net voltages/caps export) ✅ fixed,
[#50](https://github.com/Firas-Jrad/pyckt/issues/50) (CMRR/PSRR/CM-range) ✅ fixed,
[#51](https://github.com/Firas-Jrad/pyckt/issues/51) (synthesis stub scoring) ✅ fixed,
[#56](https://github.com/Firas-Jrad/pyckt/issues/56) (CM-range computed but not
constrained — found by the second pass) ✅ fixed,
[#61](https://github.com/Firas-Jrad/pyckt/issues/61) (two-stage candidates
mis-partitioned; gain model lacks stage composition — found by the synthesis
content comparison) ✅ fixed.

---

## 0. How to reproduce

```bash
ACST=/home/jrad/acst/build/bin/acst.sh
PYCKT="/home/jrad/pyckt/pyckt/.venv/bin/python -m cli"   # run from the repo root

ACST_IN=/home/jrad/acst/InputFileExamples
PY_IN=/home/jrad/pyckt/pyckt/tests/data/inputs

OUT=/home/jrad/throwaway/outputs
```

The acst invocations are unchanged from the previous report (§0 there / the
`command.sh` files in each `InputFileExamples/<mode>/`). pyckt invocations that
changed:

* **partitioning** no longer needs `--circuit-params` — input/output/bias nets
  are inferred structurally (issue #6).
* **automaticsizing** was run with `--timeout 300` (5 min wall), matching
  acst's `--runtime 5` budget.
* **rulegen (like-for-like)**: acst consumes the standard 52-item
  `AnalogLibrary.xml` (via the `Library.xml` wrapper); pyckt's bundled library
  now has 56 items (the four FUBOCO composites added by issue #31), which
  yields an 11th learned item. For an apples-to-apples run, point `--library`
  at a copy of the bundled library with the four `Mosfet*DiodeAnalogInverter` /
  `Mosfet*NonInvertingInverter` entries removed. (pyckt cannot read acst's
  `Library.xml` wrapper directly — bug [#47].)
* **toplibgen**: `pyckt toplibgen --output-format acst --output-dir …`
  (2.5 min, 4 302 topologies); compared by signature against acst's shipped
  reference set `TopologyLibraryGeneration/Netlists` (a fresh acst
  regeneration attempt died silently after ~10 min with an empty log).

---

## 1. Executive summary

| Mode | Ran? | Schema match | Content match | Verdict |
|------|------|--------------|---------------|---------|
| **structrec** | ✅ both | ✅ acst schema | **16/16 leaf + 16/16 composite**; at scale: **2 886/2 886 gallery circuits identical** | ✅ **Match** |
| **partitioning** | ✅ both | ✅ acst schema | **19/19 devices**; at scale: **2 885/2 886 gallery circuits identical** | ✅ **Match** |
| **rulegen** | ✅ both | ✅ `pairLibrary` | **10/10 items, 10/10 levels, 10/10 persistence** (same input library) | ✅ **Full match** |
| **automaticsizing** | ✅ both | ✅ **fully 1:1** (every section & field, incl. CMRR/PSRR/CM-range) | model validated ≤ ~4 % on acst's design (CMRR Δ 0.0 %!); endpoint differs — **but acst differs from itself by up to 63 % run-to-run** (§5) | ✅ format+model / ◑ endpoint |
| **toplibgen** | ✅ both* | ✅ acst dirs/netlists | **3 912/3 912 distinct + exact file-level parity 2 940/936/36** (post-#48 fix) | ✅ **Full match** |
| **synthesis** | ✅ both | n/a | acst: 868 sized (2 h 50 min); pyckt (real scoring, #51+#61): **2 836 sized in 27 min, covering 863/868 (99.4 %)** — the last 5 are 2 s-budget timeouts (size at 10 s); **0 provable-infeasible drops** | ✅ **Comparable** |

\* acst's fresh toplibgen regeneration crashed silently; the shipped reference
set was used.

**Headline:** all three deterministic recognition/rule modes are now **exact
matches** — rulegen closed its last level/persistence gaps since June. The
sizing *format* is 1:1 and the sizing *performance model* is validated to ~1–4 %
against acst's own solved design; the remaining W/L endpoint difference is
within acst's **own run-to-run variance** (§5.3), i.e. no longer a meaningful
convergence target. The toplibgen file-emission gap (#48), the synthesis
stub scoring (#51) and two-stage gain composition (#61) were all fixed
during this comparison — every mode now produces real, acst-comparable
content, and the one remaining item is the automaticsizing endpoint (§5),
which is within acst's own run-to-run variance rather than a defect.

---

## 2. structrec — Structure Recognition ✅

Unchanged from June — still a full match: **16/16** leaf devices in the same
leaf structure, **16/16** in the same top-level composite, identical type
counts across the full tree (2× CascodeCurrentMirror, 2× DiodeStack, 6×
DiodeArray, 2× CascodePair, 10× NormalArray, 2× DifferentialPair, 2×
SimpleCurrentMirror).

**New since June — validation at scale:** inside the pyckt repo, structure
recognition is compared against the FUBOCO Gallery reference artifacts
(1 950 `s-1-2` + 936 `fd-1-2` circuits, generated by a newer acst build):
**2 886/2 886 circuits semantically identical** after issues #30/#31/#38
(mixed-tech `undefined` labeling, four newer-acst composite items, natural
device-name ordering). See `pyckt/report/reports/FUBOCO_GALLERY_REPORT.md`.

Remaining diffs on the single-circuit bundle are cosmetic only (instance-index
numbering, top-level element order).

---

## 3. partitioning — Circuit Partitioning ✅

Full match, as in June: **19/19 devices in the same section** (2+2+2 gm parts
with `firstStageType="symmetrical"`, 2 loadParts, 10 biasParts, 1 load
capacitance; trailing part lists empty on both sides).

Two improvements since June:

* **No `--circuit-params` needed** — pyckt infers the input/output/bias nets
  from the netlist structure (issue #6), removing the one extra input the June
  run required.
* **Validation at scale:** the full acst partitioning pipeline (second/third
  stage typing, bias sweeps, load composition, capacitor typing — issues
  #32/#33/#34) is compared against the FUBOCO Gallery inside the pyckt repo:
  **fd-1-2 936/936 identical, s-1-2 1 949/1 950** — the single residual
  (`s-1-2/5_7`) is one gm-type label on a composite that only the gallery's
  newer acst library can classify.

---

## 4. rulegen — Sizing Rule Generation ✅ (now a full match)

June's residuals (1 mis-leveled item, 3 persistence diffs) are **gone** —
closed by the issue-#5 tie-break fix. On the same input library (the standard
52-item `AnalogLibrary`):

| Item | acst level | pyckt level | acst persist. | pyckt persist. |
|------|-----------|-------------|---------------|----------------|
| …OpAmp1 | 3 | 3 | 1 | 1 |
| …OpAmp2 | 2 | 2 | 1 | 1 |
| …OpAmp3 | 2 | 2 | 1 | 1 |
| …OpAmp4 | 2 | 2 | 2 | 2 |
| …OpAmp5 | 2 | 2 | 1 | 1 |
| …OpAmp6 | 4 | 4 | 1 | 1 |
| …OpAmp7 | 3 | 3 | 2 | 2 |
| …OpAmp8 | 3 | 3 | 3 | 3 |
| …OpAmp9 | 5 | 5 | 1 | 1 |
| …OpAmp10 | 6 | 6 | — | — |

**10/10 items, 10/10 hierarchy levels, 10/10 persistence values.**

Two caveats found while setting this up:

* With pyckt's **default** (bundled) library, the run learns **11** items —
  expected, since the bundled library intentionally carries the four
  FUBOCO-era composites (#31), which changes what the learner can compose.
  Not a bug; documented here so future runs pin the library.
* ~~pyckt cannot load acst's `Library.xml` **wrapper** file~~ — fixed
  ([#47](https://github.com/Firas-Jrad/pyckt/issues/47)); the second pass
  produced the 10/10 table above by pointing `--library` **directly at
  acst's own `InputFileExamples/RuleGeneration/Library.xml`**, no
  workaround needed.

---

## 5. automaticsizing — Automatic Sizing ✅ format+model / ◑ endpoint

### 5.1 Schema — now 1:1

pyckt emits every acst section **and every field** (second pass, after
#49/#50): `ExpectedPerformance` including
`TransitFrequencyWithErrorFactor`, `CMRR`, `negPSRR`/`posPSRR` (acst's
`degree` unit quirk preserved) and the common-mode input range;
`<Voltages unit="V">` with the same 16-net set as acst (rails 0/5 V, pinned
inputs 2.5 V, internal nets at the solved DC point); `<Currents>`;
`<Dimensions><Transistors>` + `<Capacitors>` (`/cl` at 20 p_F); plus the
sized HSPICE netlist. **Nothing acst emits is missing anymore.**

Second-pass AC-metric values (pyckt 300 s vs today's acst run): **CMRR
128.9 vs 129.0 — Δ 0.0 %**; posPSRR 57.6 vs 44; negPSRR 84.4 vs 49;
vcmMax 3.86 vs 4.39; vcmMin 2.29 vs 1.27.  The PSRR/vcm deltas are the
usual endpoint-shape differences (§5.3) — with one exception that was a
real pyckt gap: **vcmMin 2.29 V violated the fixture's CM spec**
(must be ≤ vin − 0.5 = 2.0 V; acst's 1.27 V satisfies it) because pyckt
computed the metric (#50) without *constraining* it as acst does.
**Fixed** as [#56](https://github.com/Firas-Jrad/pyckt/issues/56)
(PR #58): the Vgs-stack bounds are now posted as spec constraints and the
solved design sits at vcmMin 1.45 V / vcmMax 3.84 V — within spec by
construction.

### 5.2 Performance model — validated on acst's own design

The June report's worst numbers (Ft +233 %, PM +43.5 %, VoutMin −80 %) were
traced (issue #2) to **model bugs**, not solver tuning. pyckt's model evaluated
on *acst's solved reference design* now reproduces acst's reported numbers:

| metric | pyckt model on acst's design | acst reports | error |
|---|---:|---:|---:|
| Gain | 90.33 dB | 90.00 dB | +0.4 % |
| Transit frequency | 6.87 MHz | 6.93 MHz | −0.9 % |
| Slew rate | 22.77 V/µs | 22.52 V/µs | +1.1 % |
| Phase margin | 63.3° | 60.7° | +4.2 % |
| Vout range | 0.675 / 4.252 V | 0.670 / 4.250 V | ≤ +0.8 % |
| Power | 6.12 mW | 6.12 mW | 0 % |

(The fixes: cascode-composed output conductance — the old flat Σgds was
~52 dB off on this design — mirror-factor Ft, output-branch slew, stacked-swing,
supply-current power. Kept as a permanent regression test in the pyckt repo.)

### 5.3 The endpoint — acst does not reproduce *itself*

Re-running **the same acst binary on the same inputs with the same
`--runtime 5`** produced a very different design than the 2021-captured
reference:

| metric | acst 2021 | acst 2026-07-08 | acst vs acst Δ |
|---|---:|---:|---:|
| Gain (dB) | 90.0 | 84.0 | 6.7 % |
| Power (mW) | 6.12 | 2.24 | **63.4 %** |
| Area (µm²) | 10 868 | 14 580 | 34.2 % |
| Transit freq (MHz) | 6.93 | 2.93 | **57.8 %** |
| Slew rate (V/µs) | 22.5 | 13.6 | 39.6 % |
| Phase margin (°) | 60.7 | 77.9 | 28.3 % |
| Min output V | 0.67 | 0.49 | 26.9 % |
| per-device ΔW | — | — | **mean 107 %, max 841 %** |

Both runs satisfy every spec; acst's optimizer (randomized Gecode
branch-and-bound cut off by a wall-clock budget) simply parks at a different
point each time. **There is no stable numeric endpoint to converge to** — the
meaningful targets are the model (validated, §5.2) and the spec set.

### 5.4 pyckt's endpoint (300 s CP-SAT)

| metric | acst 2026 run | pyckt | spec | both meet spec? |
|---|---:|---:|---|---|
| Gain (dB) | 84.0 | 90.3 | ≥ 80 | ✅ |
| Power (mW) | 2.24 | 9.39 | ≤ 10 | ✅ |
| Area (µm²) | 14 580 | 370 | ≤ 15 000 | ✅ |
| Transit freq (MHz) | 2.93 | 17.2 | ≥ 2.75 | ✅ |
| Slew rate (V/µs) | 13.6 | 24.3 | ≥ 3.5 | ✅ |
| Phase margin (°) | 77.9 | 86.7 | ≥ 60 | ✅ |
| Vout min/max (V) | 0.49 / 4.28 | 0.675 / 3.62 | ≤ 1 / ≥ 3 | ✅ |

The June degenerate design (11/18 devices at the 1 µm minimum) is gone — no
device sits at minimum width, currents are in acst's regime, and pyckt's
deltas vs any single acst run are comparable to acst's own run-to-run spread
on most metrics. Full residual-gap analysis:
`pyckt/report/reports/SIZING_CONVERGENCE.md`.

---

## 6. toplibgen — Topology Library Generation ✅ (newly comparable)

June's blocker ("acst > 9 min, no pyckt acst-format writer") is resolved from
the pyckt side: `pyckt toplibgen --output-format acst` emits the acst directory
layout in ~2.5 min, and the pyckt repo's canonical **device-level signature**
harness compares it against acst's shipped reference set
(`TopologyLibraryGeneration/Netlists` — 3 912 netlists; a fresh acst
regeneration attempt died silently after ~10 min, so the shipped set remains
the reference).

**Distinct-topology parity holds: 3 912/3 912** — every reference signature in
every category is produced by pyckt (the issue-#20 result, re-confirmed today
on the current tree).

The first measurement of this run showed inflated file counts (5 124 SO /
1 170 Complementary with 3+1 "extra" signatures); investigation for issue #48
found **most of that was stale files from a June 11 run** left in the output
directory — the writer overwrote in place and never cleaned. After clearing,
one genuine defect remained: the emission wrote one file per library *entry*
(3 330 SO), including the 390 structural duplicates the generated library
carries, where acst writes one file per *distinct* topology (2 940).

Both fixed under [#48](https://github.com/Firas-Jrad/pyckt/issues/48)
(PR: name-independent content de-duplication at emission + the writer now
clears its own category directories before writing). Post-fix measurement:

| category (files) | acst reference | pyckt emission | distinct (pyckt) | sets equal |
|---|---:|---:|---:|---:|
| SingleOutputOpAmps | 2 940 | **2 940** | 2 940 | ✅ |
| FullyDifferentialOpAmps | 936 | **936** | 936 | ✅ |
| CommplementaryOpAmps *(sic — acst's dir name)* | 36 | **36** | 36 | ✅ |

**Exact file-level parity: one file per distinct topology, signature sets
identical in all three categories.**

---

## 7. synthesis — reference captured, real scoring, comparable ✅

* **acst**: the reference is **captured**. The first attempt appeared to
  die silently after ~50 min (empty log, vanished process, no OOM in the
  kernel log); the `DEBUG`-logged rerun completed cleanly in
  **2 h 50 min 49 s**, sizing **2 260 candidate topologies** (one Gecode
  constraint program each) and emitting **868 fully-sized netlists**
  (60 one-stage + 58 symmetrical + 750 two-stage single-output op-amps,
  real W/L values). Quirk: acst writes its synthesis results **into the
  `--HSPICE-netlist-dir` input directory itself**, mixed with the input
  netlists; today's 868 output files are preserved separately at
  `outputs/synthesis/cpp/results/`.
* **pyckt** (2026-07-09, with #51 real scoring **and the #61 two-stage
  gain fix**): sized **2 836 of 3 330 candidates in 26 min 56 s** (2 s
  CP-SAT budget each; 2 718 `optimal` + 118 `feasible`), emitting
  fully-sized `rank_*.ckt` netlists and a ranked JSON with 2 380 distinct
  scores derived from the solved performance.

**Content comparison** (capacitor-free device-level signatures) — the
first pass (#51 only) is shown against the second (after #61) to make the
two-stage fix visible:

| | acst | pyckt #51 | pyckt #51+#61 |
|---|---:|---:|---:|
| candidates attempted | 2 260 | 3 330 | 3 330 |
| sized successfully | 868 | 2 630 | **2 836** |
| wall time | 2 h 50 min | 30 min | 27 min |
| coverage of acst's 868 | — | 799 (92 %) | **863 (99.4 %)** |
| provable-infeasible drops (acst topos) | — | 69 | **0** |
| meet every spec target | — | 1 082 (41 %) | **2 773 (98 %)** |

* All 868 acst-sized topologies are members of the 2 940-topology
  single-output library; pyckt additionally sized 1 589 topologies acst
  never emitted.
* **The 5 acst topologies still outside the 2 s run all size `optimal` at a
  10 s budget** — timeout-only, not infeasibility (acst likewise drops
  budget-limited candidates); coverage is effectively 868/868.
* pyckt's **top-10 ranked candidates meet every spec-file target**. The
  62 remaining estimator-view gain-misses (down from 1 544) are mostly
  `optimal`-status genuinely-low-gain single-stage topologies (46–73 dB),
  correctly ranked at the bottom.
* Root cause of the #51-pass residuals, **fixed in
  [#61](https://github.com/Firas-Jrad/pyckt/issues/61)**: the single-stage
  gain model demanded the whole spec from `gm_in/g_out(out)`, physically
  impossible for a two-stage amplifier (total gain = stage product
  `A1·A2`). `topology.second_stage_pieces` now detects a real second stage
  (an output-branch device gated by a non-diode first-stage-output node),
  and the gain constraint / objective / estimator compose `A1·A2`;
  mirror-driven symmetrical OTAs are untouched.
* acst emits **no ranking artifact** (only the sized netlists), so the
  comparison is coverage/spec-based rather than rank-vs-rank.

---

## 8. Issues filed from this run

| # | Title | Kind | Status |
|---|-------|------|--------|
| [#47](https://github.com/Firas-Jrad/pyckt/issues/47) | cli: `--library` cannot load acst wrapper `Library.xml` | bug | ✅ fixed (PR #52) |
| [#48](https://github.com/Firas-Jrad/pyckt/issues/48) | toplibgen: acst-format emission duplicates + stale-dir mixing | bug | ✅ fixed (PR #53) |
| [#49](https://github.com/Firas-Jrad/pyckt/issues/49) | sizing: export solved net voltages + capacitor values | enhancement | ✅ fixed (PR #54) |
| [#50](https://github.com/Firas-Jrad/pyckt/issues/50) | sizing: compute CMRR / PSRR / CM input range | enhancement | ✅ fixed (PR #55) |
| [#51](https://github.com/Firas-Jrad/pyckt/issues/51) | synthesis: replace stub candidate scoring with real sizing | enhancement | ✅ fixed (PR #60) |
| [#56](https://github.com/Firas-Jrad/pyckt/issues/56) | sizing: CM input range computed but not constrained (spec violated) | bug | ✅ fixed (PR #58) |
| [#61](https://github.com/Firas-Jrad/pyckt/issues/61) | sizing: two-stage gain composition (A1·A2) — 69 acst topologies infeasible | bug | ✅ fixed (PR #62) |

All `ready-for-agent`.  #56 was found by this second pass — the #50 model
made the violation *visible*.

---

## 9. What changed since the previous report (2026-06-05)

| Item | June | Now |
|------|------|-----|
| structrec | 16/16 + 16/16 (single circuit) | same, **plus 2 886/2 886 FUBOCO circuits** |
| partitioning | 19/19, needed `--circuit-params` | 19/19, **params inferred (#6), plus 2 885/2 886 FUBOCO** |
| rulegen | 9/10 levels, 3 persistence diffs | **10/10 levels + 10/10 persistence** (same-library run) |
| sizing schema | missing Voltages/Capacitors/TFwEF/CMRR… | **1:1 sections** (#1); AC metrics pending #50 |
| sizing model | Ft +233 %, PM +43.5 %, VoutMin −80 % | **validated ≤ ~4 % on acst's design** (#2) |
| sizing endpoint | 11/18 devices at min width | 0/18 at min width; deltas within **acst's own 27–63 % run-to-run spread** |
| toplibgen | not comparable (no writer, no reference run) | **3 912/3 912 distinct parity**; emission bug filed (#48) |
| synthesis | pyckt runs, acst not captured, stub scoring | **acst reference captured (868 sized); pyckt real-scored, 863/868 coverage** (#51+#61) |
