# toplibgen topology-set parity — divergence analysis (issue #3)

**Goal:** make `pyckt toplibgen --output-format acst` enumerate the *same
topology set* acst does, per category:

| Category | acst | pyckt (before) |
|---|---:|---:|
| FullyDifferentialOpAmps | 936 | 936 ✅ |
| SingleOutputOpAmps | 2940 | 4914 ✗ |
| ComplementaryOpAmps | 36 | 1170 ✗ |

This document is the reverse-engineering the issue reserved for a human: it
pins down *exactly* which acst generation rules pyckt does not (yet) reproduce,
established by reading acst's C++ source against pyckt's port.

## 1. acst's master enumeration (`TopologyLibraryGeneration::createOpAmps`)

`Synthesis/src/TopologyLibraryGeneration.cpp` runs one loop per category
(`isComplementary` / `isFullyDifferential` / else = single-output), incrementing
`caseNumber` until the factory returns empty:

```
for each caseNumber:
    if complementary:      oneStage = createComplementaryOpAmps(case)
    elif fullyDiff:        oneStage = createFullyDifferentialOneStageOpAmps(case)
    else:                  oneStage = createSimpleOneStageOpAmps(case)
                           symmetrical = createSymmetricalOpAmps(case)

    for op in oneStage:
        write(op)                                    # one-stage netlist
        if NOT complementary:                        # ← key rule
            twoStage = createSimple/FDTwoStageOpAmps(op)   # 12 inverting 2nd stages
            for t in twoStage: write(t, op.id)       # two-stage netlist "_<opId>_"

    for s in symmetrical:                            # single-output branch only
        write(s)                                     # one-stage ONLY, no two-stage
```

### Structural rules this encodes (all confirmed from source)

1. **Complementary op-amps are one-stage ONLY** — the `if(!isComplementary)`
   guard skips two-stage expansion entirely. acst: 36 one-stage, 0 two-stage.
2. **Symmetrical op-amps are one-stage ONLY** and form their own family
   (`symmetrical_op_amp<N>`), written *without* two-stage expansion, but still
   filed under `SingleOutputOpAmps/`.
3. **Simple single-output & fully-differential get 12 two-stage variants each**
   (`getInvertingStages()` has 12 members), plus their one-stage form → ×13.
4. Two-stage file naming is `<prefix>_<oneStageId>_<twoStageIdx>` — the
   `_<oneStageId>_` infix pyckt's `AcstNetlistWriter` path does not emit.

## 2. Target one-stage counts (drive everything, since two-stage = one-stage × 12)

| Family | acst one-stage count | derivation |
|---|---:|---|
| simple single-output | 210 | 210 + 210×12 = 2730 |
| symmetrical | 210 | one-stage only = 210 |
| **SingleOutput total** | | 2730 + 210 = **2940** ✅ |
| fully-differential | 72 | 72 + 72×12 = **936** ✅ |
| complementary | 36 | one-stage only = **36** ✅ |

## 3. Where pyckt diverges

pyckt's `src/synthesis/generator.py` currently gives **every** first-stage a
1-stage form plus 12 two-stage forms (×13) regardless of category, and folds
"symmetrical" in as a plain single-output first stage. That produces:

| Family | pyckt one-stage | acst one-stage | ×13 applied? |
|---|---:|---:|---|
| simple (cases 1–16) | 336 | 210 | yes (should: yes) |
| symmetrical (cases 1–8) | 30 first-stages | 210 op-amps | yes (should: **no**, one-stage only, and via HL5 composition) |
| complementary (cases 1–2) | 90 | 36 | yes (should: **no**) |
| fully-differential | 72 | 72 | yes ✅ |
| feedback (folded into simple) | 12 | — | — |

Two independent problems:

### 3a. Orchestration / structural rules (generator.py)
- pyckt two-stages complementary and symmetrical; acst does not.
- pyckt has no separate `symmetrical_op_amp` family or the acst HL5 symmetrical
  composition (`OpAmps::createSymmetricalOpAmps`: first-stage × filtered
  inverting-2nd-stage × complementary-second-stage-bias, with the
  `transconductance.size ≥ 0.5·load.size` filter). It treats the 30 symmetrical
  *first stages* as ordinary single-output stages.

### 3b. HL3/HL4 enumeration cardinalities
Even with correct orchestration, the *first-stage* counts differ because the
HL3 load/bias factories and the HL4 `createSimpleTransconductanceNonInvertingStages`
compatibility filter enumerate different numbers than acst:
- simple first-stages: pyckt 336 vs acst 210.
- complementary first-stages: pyckt 90 vs acst 36.
- (FD happens to match at 72.)

pyckt's HL4 `createSimpleNonInvertingStages` dispatch is a faithful 1:1 port of
acst's 16-case switch (same load/bias factory calls per case). So the gap is in
the **HL3 factory cardinalities** (`LoadManager` / `StageBiasManager` in
`src/topogen/HL3/l.py`, `sb.py`) and/or the HL4 load-bias compatibility filter,
not the case wiring. Example measured cardinalities (pyckt):
`createSimpleMixedLoadNmos` = 12, `getOneTransistorStageBiasesPmos` = 1,
`getTwoTransistorStageBiasesPmos` = 2; case-1 yields 8 (filter drops 4 of 12).

## 4. Plan to reach exact parity (staged, each independently verifiable)

**Stage 1 — structural rules (generator.py + HL5):** mirror acst's `createOpAmps`
exactly. Complementary & symmetrical become one-stage-only; add the `symmetrical_op_amp`
family via a real HL5 symmetrical composition; only simple/FD get the 12 two-stage
variants; emit the `_<oneStageId>_` two-stage naming infix. Verifiable against the
per-family *structure* even before counts converge.

**Stage 2 — HL3/HL4 cardinality reconciliation:** compare each HL3 load/bias
factory and the HL4 compatibility filter against acst method-by-method until
simple first-stages = 210 and complementary = 36, guarding FD = 72 throughout.

**Stage 3 — canonical signature comparison:** recognise each generated flat
circuit (reuse `recognition.recognizer`) into a name-independent device-role
signature, and assert pyckt's signature multiset equals acst's reference set —
proving true set parity, not just equal counts.

**Verification target:** 2940 / 936 / 36 exactly, per category, plus a
signature-set match, with the existing suite still green.

## 5. CRITICAL FINDING — the netlists are structurally broken (blocks parity)

Building the canonical-signature harness (`comparison/topology_signature.py`)
and running it against both sets surfaced a far more fundamental problem than
count divergence:

| Category | acst distinct sigs | pyckt distinct sigs | common |
|---|---:|---:|---:|
| SingleOutput | 2940 | **3** | **0** |
| FullyDifferential | 936 | **1** | **0** |
| Complementary | 36 | **1** | **0** |
| **global** | 3912 | 3 | **0** |

pyckt emits 7020 files but only **3 structurally-distinct topologies**, and
**none** of them matches any acst topology — *including FullyDifferential,
where the file count matches 936/936 exactly.* That "936/936 match" is therefore
a coincidence of enumeration cardinality, **not** structural fidelity.

**Root cause:** pyckt's generated flat circuits are hollow. A converted MOSFET
carries **one** terminal instead of four:

```
pyckt   one_stage_single_output_op_amp100.ckt:
    M1 in1 pmos                         ← only the gate net; no drain/source/bulk
    M3 source_nmos source_nmos nmos     ← two nets; missing gate/drain
acst    one_stage_single_output_op_amp1.ckt:
    m_..._Transconductor_4 FirstStageYout1 in1 FirstStageYsourceTransconductance
                           FirstStageYsourceTransconductance pmos   ← fully wired
```

The hierarchical HL4/HL5 objects *do* carry connectivity (a `NonInvertingStage`
has 3 sub-instances, 9 ports, 9 connections), but
`topogen.common.circuit.Circuit.flatten()` / `synthesis.converter.TopologyConverter`
does **not** recursively resolve those instance-port connections down to leaf
transistor terminals.  The `AcstNetlistWriter` then faithfully writes transistors
that have almost no pins connected (it skips missing pins by design).

**Consequence for issue #3:** exact topology-set parity is *blocked* on fixing
the hierarchical→flat flattening (pyckt's equivalent of acst's
`Core::FlatCircuitRecursion`).  Reconciling enumeration counts (§3–4) is moot
until the generated circuits are structurally valid — matching counts of
structurally-broken netlists is not parity.  This is a larger, more fundamental
fix than the enumeration reconciliation the issue anticipated, and it should be
its own work item (the converter/flatten bug) that #3's set-parity check then
sits on top of.

The signature harness added here is the tool that will verify real parity once
the flattening is fixed: `signatures_in_dir(acst_cat) == signatures_in_dir(pyckt_cat)`.

## 6. Fix 1 — `Circuit.flatten()` rewritten as union-find (DONE)

`topogen.common.circuit.Circuit.flatten()` now resolves nets with a union-find
over **every** connection in the hierarchy (parent-port ↔ child-port), instead
of only propagating the root's own ports downward.  Each equivalence class is
one net; classes containing a top-level net keep that boundary name, the rest
get fresh internal names; diode transistors get gate tied to drain.  Pre-set
leaf net attributes are honoured (seeded into the union-find) so hand-wired test
circuits keep working.

Result — generated MOSFETs are now fully wired (drain/gate/source/bulk), and
structural diversity explodes:

| Category | distinct sigs before | distinct sigs after |
|---|---:|---:|
| SingleOutput | 3 | 2970 |
| FullyDifferential | 1 | 648 |
| Complementary | 1 | 702 |

Full suite green (869 passed).  Regression tests added:
`test_convert_transistors_are_fully_wired`,
`test_convert_produces_multiple_distinct_structures`.

## 7. Remaining gap to structural parity (`common` still 0) — next layer

The generated one-stage netlist is now well-formed but still differs from acst
by the **OpAmp-level composition** that pyckt's `createSimpleOpAmp` omits.
Comparing pyckt's case-1 first stage to `one_stage_single_output_op_amp1.ckt`:

| acst has | pyckt has |
|---|---|
| load **Capacitor** (`out`→`sourceNmos`) | — |
| compensation capacitor (two-stage) | — |
| **MainBias** + full bias network wiring every floating gate to `ibias` | dangling internal net on stage-bias gate |

acst builds these in `OpAmps::createSimpleOpAmp` via
`connectInstanceTerminalsCapacitors` (load/compensation caps) and
`buildAndConnectedBias` (`OpAmps.cpp:975`) — the latter finds every gate
terminal not already driven by a drain and synthesises the bias network
(main bias, improved-Wilson / cascode-GCC current biases, voltage biases).
Porting that HL5 composition is Fix 2; enumeration-count reconciliation (§3–4)
is Fix 3, on top of it.  The signature harness verifies each step.

### 7.1 Fix 2 is bigger than "port one function" — findings

Starting Fix 2 showed the composition gaps are **pervasive**, not confined to a
bias network.  In pyckt's simplest generated op-amp the floating gate inventory
is:

```
gate nets:  in1, in2, net_2, net_3
drain nets: net_0, net_1, out
floating (gate not driven by a drain): net_2, net_3
```

* `net_3` = tail stage-bias gate → acst wires it to `ibias` and adds the
  diode-connected **MainBias** reference (a mirror of the stage-bias stack).
* `net_2` = **current-mirror load** gate.  acst's load reference is
  diode-connected (gate = its own reference drain = `FirstStageYout1`), so this
  gate is *not* floating in acst.  In pyckt the load exposes `InnerLoad1`
  (mirror gate) and `out1` (reference drain) as separate first-stage ports and
  **never connects them** — the diode is missing.

So exact device-for-device parity needs three composition pieces, each present
across the HL2–HL5 cells and case-dependent (simple / cascode / folded-GCC):

1. **Current-mirror diode connections** — tie each mirror's reference gate to
   its reference drain (missing in pyckt's load/stage composition).
2. **Bias network** — `buildAndConnectedBias`: main bias + Wilson/cascode-GCC
   current biases + voltage biases wiring every remaining floating gate to
   `ibias` (~1200 LOC of dense C++ in acst, plus its `CurrentBiases`/
   `VoltageBiases` cell libraries that pyckt lacks).
3. **Load / compensation capacitors** — `connectInstanceTerminalsCapacitors`.

This is a substantial, multi-part model-completion effort — realistically its
own multi-PR project — rather than a single function port.  Fix 1 (flatten) is
its prerequisite and stands on its own.  The signature harness remains the
oracle: after each composition piece lands, `common` signatures should climb
from 0 toward the full 2940 / 936 / 36.

## 8. Composition fixes landed — signature overlap climbing

Each fix is verified device-for-device against acst via the signature harness:

| Fix | What | acst matches (common signatures) |
|---|---|---:|
| 2a | current-mirror load diode connections | prerequisite |
| 2b | simple diode voltage-bias network | 0 → 6 (SingleOutput) |
| 2c | load capacitor(s) | 6 full-signature |
| 2b+ | two-transistor cascode voltage bias | 6 → 12 |
| 2d | FD composition (feedback stage) + sub-instance de-aliasing | +4 FD → 16 |
| 2-x | complementary cross-mirror current bias (both-tech references) | +18 SingleOutput → **34 total** |

**Fix 2d notes.** pyckt's fully-differential op-amps were structurally
single-output-shaped: the generator composed FD first stages with the
single-output `createSimpleOpAmp` and never built acst's common-mode feedback
stage.  Two problems were fixed:

1. **Sub-instance aliasing** — the FD `cb+cb` load built both differential
   branches from *one* shared `CurrentBias` object, so the union-find flatten
   (keyed by object identity) collapsed `out1`/`out2` onto a single net.
   `createTransistorStack` now deep-copies its bias cell, so each branch owns
   independent transistors.
2. **FD composition** — new `createFullyDifferentialOpAmp` wires the first
   stage's differential outputs `out1`/`out2`, a common-mode feedback stage
   (sensing `out1`/`out2`, referencing `vref`), and drives the first-stage
   mirror-load gate from the feedback output (acst
   `connectInstanceTerminalsFullyDifferentialOpAmp` +
   `connectedLoadInstanceTerminalToFeedbackStage`).  The generator pairs each FD
   first stage with the matching-tech feedback stages.

The simplest FD op-amp now matches acst's `one_stage_fully_differential_op_amp`
device-for-device.

## 9. Bias network is complete — remaining gap is enumeration (Fix 3)

Measured after the composition fixes: **0 / 4914** single-output op-amps have
any floating (unbiased) gate — every generated op-amp already carries a
complete, valid bias network, and for the topologies acst also generates it
matches acst device-for-device (34 total).  So there is **no remaining bias
work** ("Wilson / cascode-GCC bias") for single-output: the earlier hypothesis
that cascode topologies needed more bias paths was wrong.  The remaining
single-output mismatch is entirely **enumeration divergence** — pyckt generates
*different cascode topologies* than acst (e.g. pyckt's 9-transistor case is a
telescopic cascode: pmos cascode + nmos mirror; acst's 9-transistor topologies
are cascode-current-mirror loads).  Confirmed case-by-case: single-output cases
1–6, 13–14 match; 7–12, 15–16 are structurally different topologies, not
different biasing of the same one.

## 10. Fix 3 — enumeration reconciliation (in progress)

**Landed:** complementary op-amps are now one-stage only (acst rule) —
Complementary 1170 → 90 (toward 36); generated total 6516 → 5436.

**Remaining — deep HL3 cardinality port (the dominant blocker).** pyckt's
HL3 `LoadPart` / `StageBias` / feedback factories enumerate *different-sized
sets* than acst's, so pyckt generates different topologies, not just more.
Measured divergences:

| Family | pyckt | acst | where |
|---|---:|---:|---|
| simple one-stage first-stages | 336 | 210 | HL3 load/bias cardinalities per case |
| complementary first-stages | 90 | 36 | HL3 four-transistor-mixed load parts |
| FD one-stage | 432 (72 fs × 6 fb) | 72 (~36 fs × 2 fb) | FD first-stage **and** feedback-stage counts both over-generate |

acst's per-family `create*NonInvertingStages` **structure** is a faithful port
already (same case switch, same load-group composition); the gap is the HL3
`LoadParts.cpp` / `StageBias` / `CurrentBias` / feedback enumeration
**cardinalities** (e.g. acst's feedback stage applies a
`everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType`
filter and yields ~2 per tech vs pyckt's 6).  Reconciling requires porting
those HL2/HL3 factory counts factory-by-factory against acst — a large,
methodical effort, and the last blocker before the already-correct
compositions count as matches.

**Also remaining (composition, orthogonal to enumeration):**
- **FD two-stage** (`createFullyDifferentialTwoStageOpAmps`).
- **Complementary load composition** — bias now matches acst, but the
  complementary *load* still differs (pyckt's mixed load vs acst's `Load_2–9`).
- **Symmetrical op-amp family** (its own one-stage composition).

### 10.1 The HL3 gap is structural, not count-matching (measured)

Audited the HL2/HL3 factories bottom-up:

- **Fixed two real latent bugs**: the two-transistor PMOS `VoltageBias` and
  both two-transistor `CurrentBias` factories cached a `chain()` iterator that
  the first consumer exhausted (later callers saw 0).  Materialised to lists.
  (Single-pass generation was unchanged — the loads are built once at init —
  but repeated factory access was wrong.)
- **Where the counts *do* line up**: mixed load-parts (12 = 2+4+6),
  current-bias load-parts (3), the two-load-part mixed-current-bias loads
  (12 × 3 = 36) all match acst's factory cardinalities.

**But the sets don't**: of acst's **210** simple one-stage op-amps, pyckt
generates only **30** (14 %).  pyckt's simple first-stage set is *not* a
superset of acst's — it builds *structurally different* loads (e.g. telescopic
cascode vs cascode-current-mirror) for ~85 % of topologies.  So the remaining
enumeration work is **not** count-trimming or a filter; it is a faithful
structural re-port of acst's HL3 load construction (`Loads.cpp` /
`LoadParts.cpp` cascode/GCC/four-transistor wiring) so pyckt builds acst's
*exact* loads.  That is a large, methodical, multi-part effort — the remaining
body of issue #3 — and it is the single blocker between the (verified-correct)
composition/bias pipeline and full 2940 / 936 / 36 parity.

## 11. Issue #20 progress — bias fix + per-case load-family map

Per-case match diagnostic (simple single-output, one-stage) pinpoints where the
remaining gap is. A cross-mirror bias fix (the cross current mirror must sense
the master reference's *rail-connected* node — ibias for a single-diode master,
the bottom cascode node for a two-transistor one) unlocked the
two-transistor-stage-bias cascode cases: **overlap 34 → 54** (SingleOutput
30 → 48, Complementary 0 → 2).

Current per-case match rate (simple one-stage):

| case | family | match |
|---|---|---|
| 1–2 | MixedLoad | 4/8 |
| 3–4 | MixedLoad + 2T-bias | 4/16 |
| 5–6 | FoldedGCC | 4/16 |
| 7–8 | FoldedGCC + 2T-bias | 4/32 |
| 9–12 | CascodeGCC | **0** |
| 13–14 | MixedCurrentBias | 8/24 |
| 15–16 | MixedCurrentBias + 2T-bias | 8/48 |

The remaining non-matches are now confirmed **load-structure** divergences, not
bias: e.g. CascodeGCC (cases 9–12) — pyckt builds a *telescopic cascode* (cascode
on the signal path) where acst's 9-transistor topologies are *cascode-mirror
loads* (cascode inside the load, simple diff pair).  The partial cases' misses
are likewise the complex (3–4-transistor) mixed-load variants whose wiring
differs from acst's.  Next: re-port the HL3 load construction family-by-family
(`createLoadsTwoLoadParts*` in `src/topogen/HL3/l.py` / `lp.py`) against acst's
`Loads.cpp` / `LoadParts.cpp`, verifying each with the per-case diagnostic.
