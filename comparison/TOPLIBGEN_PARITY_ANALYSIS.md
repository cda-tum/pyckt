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
