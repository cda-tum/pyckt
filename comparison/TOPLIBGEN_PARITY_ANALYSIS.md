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

## 12. Issue #20 progress — enumeration aligning

Two verified increments (PR #21), suite green throughout:

1. **Cross-mirror bias fix** — the cross current mirror now senses the master
   reference's rail-connected node (ibias for a 1-transistor master, the bottom
   cascode node for a 2-transistor one).  Overlap **34 → 54**.
2. **Load-part validity filter** — ported acst's `create*LoadPartsMixed`
   validity check (`everyGateNet` + floating-gate policy).  pyckt kept every
   voltage/current-bias combination; acst drops the invalid ones.  Result:
   **simple one-stage first-stages 336 → exactly 210** (acst's count); generated
   total 5436 → 3753, no match regression.

Note: the current-bias/voltage-bias 4-transistor load parts do **not** need this
filter — applying it there over-shoots (SingleOutput 2418 < 2940), because those
feed the GCC loads that are already correct.

### Precise remaining decomposition (measured)

`SingleOutput` is now 3276 vs acst 2940; the 336 excess is **not** load parts —
it is the symmetrical/feedback folding:

```
pyckt single_output first-stages = simple 210 + symmetrical 30 + feedback 12 = 252
  x13 (1 one-stage + 12 two-stage) = 3276
acst SingleOutput 2940 = simple 210 x13 (2730) + symmetrical 210 (one-stage only)
```

So the remaining SingleOutput work is a **composition** change, not enumeration:

- **Symmetrical family** — acst emits a separate one-stage-only `symmetrical_op_amp`
  family (210, built by `OpAmps::createSymmetricalOpAmp`: symmetrical first-stage
  × filtered inverting 2nd-stage × complementary bias).  pyckt folds its 30
  symmetrical first-stages into single-output and two-stages them.  Needs the
  acst composition + its own category (−390 wrong, +210 right).
- **Feedback stages** must not be folded into single-output (they belong to FD):
  −156.
- **CascodeGCC load structure** (cases 9–12, still 0 matches) — pyckt builds a
  telescopic cascode; acst builds cascode-mirror loads.  Load-wiring re-port.

Plus (unchanged from §10): **FD** one-stage count (432 → 72) + FD two-stage;
**complementary** load composition.

## 13. Symmetrical family + inverting-stage fix (issue #20)

- **Inverting-stage bug**: `connectInstanceTerminalsNmosTransconductance` wired
  the *internal* `INNERTRANSCONDUCTANCE`/`INNERSTAGEBIAS` nodes for the
  single-transistor case, leaving the input gates unexposed (the PMOS case did
  it right).  Fixed — the prerequisite for composing the symmetrical 2nd stage.
- **Symmetrical composition** (`createSymmetricalOpAmp` / `createSymmetricalOpAmps`)
  builds acst's symmetrical OTA: differential first stage → two current mirrors,
  an inverting second stage on `out1`, and a complementary second stage (a copy
  of the 2nd-stage transconductance + a diode voltage bias) mirroring `out2`
  through `innercomp`.  Wired into the generator as a **separate one-stage-only
  `symmetrical_op_amp` family** (own naming/category via `TopologySpec.is_symmetrical`),
  and symmetrical stages are no longer folded into single-output.
- **Multi-case wiring** (simple 2-diode first-stage load): ported acst's
  size-keyed `connectInstanceTerminalsSymmetricalOpAmp` sub-cases — the
  two-transistor cascode transconductance (`INSOURCE`/`INOUTPUT`) and the
  one-/two-transistor complementary stage biases
  (`findComplementarySecondStageStageBiases`).  Fixed `_symmetrical_load_size`
  (was `//2`, mis-sizing the simple 2-diode load).  **Overlap 58 → 70**
  (symmetrical **16/210**, all simple-load).

### 13.1 The cascode-gate bias-completion fix (measured, **shipped**)

The tc_size == 2 symmetricals (simple-load, e.g. `symmetrical_op_amp24`) diverged
not in composition wiring but in **bias completion**.  Isolated by diffing pyckt
vs `symmetrical_op_amp24`:

- acst ties the cascode transconductor's **cascode gate** to a diode reference
  **plus an opposite-tech current-source leg** whose gate senses the `ibias`
  reference and whose source sits on the opposite rail (`MainBias_1` +
  `SecondStage1_StageBias_16`).  A diode reference alone carries **no bias
  current** — the leg is what drives it.
- pyckt's bias completion added the diode but **omitted the leg**, leaving the
  cascode gate undriven and structurally divergent.

This is exactly the second half of acst `addCurrentBiasesToCircuit`
(`OpAmps.cpp:1703–1786`): every voltage-bias reference *not* connected to `ibias`
gets a paired opposite-tech current bias.  pyckt already did this for the
cross-tech **source** reference; the fix extends it to the **output/cascode-gate**
references (`bias_completion.py`: track single-diode output refs, emit their legs).

**Result (measured, no regression, suite 874 green):**

| family | before | after |
|---|---|---|
| symmetrical (SingleOutput) | 16 | **32** |
| Complementary | 2 | **4** |
| **total signature overlap** | **70** | **88** |

### 13.2 What still blocked the cascode-*load* symmetricals (resolved)

The cascode-load composition wiring alone (acst `OpAmps.cpp:848–869`) matched 0
because three *upstream* divergences compounded (each isolated by diffing acst
netlists device-for-device):

1. **Missing GCC voltage-bias variant** (HL2 `vb.py`): acst's
   `createTwoTransistorCircuit` runs *both* of its branches, so a mixed
   normal+diode pair yields **two** variants — pyckt returned after the first,
   never building the gate-connected-cascode variant (source gate tied to the
   output node) that acst's four-transistor symmetrical loads are made of
   (`symmetrical_op_amp100`'s load).  Also, acst maps the `OUTSOURCE` terminal
   to the `IN` net on the variants that lack an own `OUTSOURCE` net; pyckt
   omitted the port entirely, silently danglings the load-part wiring.
2. **Missing load-part filter** (HL3 `lp.py`): acst drops four-transistor VB
   load parts whose floating gates sit on rail transistors (the Wilson-style
   variant); pyckt kept them, generating loads acst never builds.
3. **Port-name mismatch** (HL4 `non_inv_connections.py`): the symmetrical stage
   connected `OUTSOURCE{1,2}LOAD1` to load ports `out_outsource*_load1`, which
   don't exist (real names `out_source_load*`) — the connection dangled
   silently, leaving the second stage's transconductor gate floating.

With those fixed the cascode-load wiring was enabled and pyckt emits exactly
**210 unique symmetrical signatures**.

## 14. Improved-Wilson + cascode-GCC bias ports — symmetrical parity (issue #20)

Two remaining bias-completion ports closed the family:

- **Leg chaining** (`bias_completion.py`): a current leg of tech T must mirror
  a reference of its *own* tech.  When a master-tech reference needs a leg and
  the other tech has no rail reference, acst creates a fresh intermediate diode
  (`findReferenceVoltageBias`'s create-new branch) which then gets its own
  master-tech leg — the chained `MainBias_17/2/1` pattern.  Overlap 88 → 100.
- **Improved-Wilson mirror** (`connectCurrentBiasOfImprovedWilsonCurrentMirror`):
  a floating cascode gate whose (single) transistor stacks on a diode gets a
  two-transistor voltage bias — a diode on the gate node over a transistor
  sensing the stage's own diode node — and serves as the **ibias candidate**
  when no rail reference exists (`connectIbiasTerminal`'s 2-transistor
  fallback).  Reference: `symmetrical_op_amp134`.
- **Cascode-GCC diode** (`connectCascodeGCC`): the folded GCC pair's shared
  floating gate gets a diode riding on the differential pair's **tail node**,
  not the rail (`addOneTransistorVoltageBiasToCircuit`'s INNERGCC case).
  Reference: `one_stage_single_output_op_amp102`.  CascodeGCC one-stage cases
  9–12: 0 → **36/36**.

**Results (measured, suite 875 green):**

| milestone | total overlap |
|---|---|
| session start | 88 |
| leg chaining | 100 |
| GCC VB variant + load-part filter + port fix + cascode symmetrical | 223 |
| improved-Wilson port | 335 — **symmetrical 210/210, zero missing/extra** |
| cascode-GCC diode | **365** (SingleOutput 342, FD 12, Complementary 11) |

### 14.1 Next blocker — two-loadpart load composition collapse

One-stage simple cases 5–8/13–16 sit at ~half matched (162/252 one-stage).
Diffing a case-5 miss (`c5_6`): the **differential pair's drains collapse onto
one net** — both branches of a two-loadpart load (2-transistor mixed
loadPart1 + cascode loadPart2) merge, and duplicate diodes appear.  That is a
`createTwoLoadPartLoadsWithoutGCC`-family *composition wiring* bug (HL3
`l.py`), independent of bias completion.  Fixing it (and re-checking the
telescopic-cascode gate wiring against acst's cases 7–8 loads) is the next
piece; the two-stage family multiplies every one-stage gain ×12.

## 15. SingleOutput full parity — 2940/2940 (issue #20)

The §14.1 "two-loadpart collapse" piece grew into complete SingleOutput
reconciliation.  Every step measured against the acst netlist set:

| step | fix | total overlap |
|---|---|---|
| start | (post-§14) | 365 |
| CB load-part filters | acst's gate-net rule on `createFourTransistorLoadPartsCurrentBiases` (the diode-bottom mirror merges both fold nodes — the §14.1 collapse); diode-only + no-floating on `createTwoTransistorLoadPartsVoltageBiases`.  Also trims the library to acst's exact per-family counts. | — |
| fewer-VBs ibias rule | acst assigns ibias to the tech with *fewer* voltage biases (`OpAmps.cpp:1031`), input tech only on ties. One-stage 180/180 generated-all-match. | 384 |
| **two-stage composition** | pyckt never connected the first stage's output to the second stage — acst `OpAmps.cpp:709–727`: `OUT2 → OUTFIRSTSTAGE → IN[SOURCE]TRANSCONDUCTANCE` + the **compensation capacitor** `OUTFIRSTSTAGE ↔ OUT`.  Two-stage 0 → 2022/2160. | 2066 |
| odd loads + diode-wrapper checks | acst takes the full load × stage-bias cross-product (pyckt skipped odd-transistor loads, dropping all 3T mixed loads); three `isSingleDiodeTransistor` checks inspected the bias *wrapper* instead of the transistor.  pyckt hits acst's exact 2940 SingleOutput signature count. | 2788 |
| multi-Wilson bookkeeping | several same-tech Wilson refs per topology (list, not tech-keyed dict — dropped ones lost their legs); Wilson rail nodes are master-only sense references (acst `findReferenceVoltageBias` criteria 2/3 exclude the Wilson variant → fresh intermediate diode); floating gates processed in leaf order (acst's last-match ibias scan → the second stage's Wilson wins). | 2964 |

**SingleOutputOpAmps: 2940/2940 — zero missing, zero extra** (one-stage 210,
symmetrical 210, two-stage 2520).

### 15.1 Remaining families

- **Complementary 36/36 — resolved**: the collapse was a one-branch typo in
  `connectInstanceTerminalsOfComplementaryLoad` (pmos-first case): the second
  (nmos) load part's transistor-stack nets were wired to the `*LOADPMOS` stage
  nets already used by the first part, merging both load parts' inner nodes and
  dangling the pmos pair's outputs.  acst maps `LOAD2 → *LOADNMOS`
  (`NonInvertingStages.cpp:1303–1304`).  Full parity, zero missing/extra.
- **FullyDifferential 12/936**: FD **two-stage** is unported (acst pairs
  `secondStage1`/`secondStage2` per output, `OpAmps.cpp:732–780` — 864 of the
  924 misses); FD one-stage still misses 60.

## 16. FullyDifferential parity — the library is complete (issue #20)

- **Feedback-stage filter**: acst's gate-net validity check in
  `createFeedbackTransconductanceNonInvertingStages` (a pyckt TODO) drops the
  1-transistor-tail feedback variant — feedback stages hit acst's exact 2 per
  tech, FD one-stage count 108 → 72.
- **Per-structure CMFB target**: the common-mode feedback drives the load
  terminal picked by `connectedLoadInstanceTerminalToFeedbackStage`
  (`OpAmps.cpp:900–935`) — `INNERLOAD1`/`INNERSOURCELOAD1` (one-part loads),
  `INNERLOAD2`/`INNERSOURCELOAD2` (two-part, 2T first part), `INNERBIASGCC`
  (GCC loads).  pyckt always drove `INNERLOAD1`.  FD one-stage 12 → **72/72**.
- **FD two-stage composition**: one inverting second stage per output
  (`OUT1/OUT2FIRSTSTAGE`, transconductor gate by size, per-output compensation
  capacitors; two independent copies of the same inverting stage —
  `OpAmps.cpp:746–770` + `createFullyDifferentialTwoStageOpAmps`), wired into
  the generator.  FD **936/936**.

## FINAL SCOREBOARD — issue #20 acceptance criteria met

| Category | acst | pyckt generated | matched |
|---|---:|---:|---:|
| SingleOutputOpAmps | 2940 | 2940 | **2940/2940** |
| FullyDifferentialOpAmps | 936 | 936 | **936/936** |
| ComplementaryOpAmps | 36 | 36 | **36/36** |
| **total** | **3912** | **3912** | **3912/3912** |

Every topology acst emits, pyckt emits — device-for-device, per category, with
zero extras.  Verified with `comparison/topology_signature.py`; full pytest
suite green.
