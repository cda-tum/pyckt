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
