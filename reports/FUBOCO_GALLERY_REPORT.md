# FUBOCO Gallery comparison — pyckt vs reference (issue #7)

Compares pyckt's structure recognition and partitioning (acst output format)
against the FUBOCO Gallery reference artefacts
(https://github.com/analog-ml/fuboco-gallery) for every circuit of the
`s-1-2` (1950 circuits) and `fd-1-2` (936 circuits) categories.  See
`scripts/compare_fuboco_gallery.py` for the methodology (semantic XML
comparison; ordinals/order/whitespace/rail-renaming normalised).

**Regenerate**:

```
.venv/bin/python scripts/compare_fuboco_gallery.py \
    --gallery <fuboco-gallery checkout> --report reports/FUBOCO_GALLERY_REPORT.md
```

## Verdict (updated as follow-up fixes land — this run: post PR #42, with #33)

**Structure recognition: COMPLETE parity — 1950/1950 (`s-1-2`) and 936/936
(`fd-1-2`) circuits identical.** Progression: 18/2 → 342/14 (#30) →
1714/718 (#31) → **all** (#38).

**Partitioning: every remaining divergence is now capacitor `load` /
`compensation` typing (#34)** — with a single exception (see below).  After
the load-classification port (#32) and the gm/second-stage typing port (#33),
`s-1-2` reduces to **150 fully-identical circuits and 1799 that differ only in
capacitor typing** (1 circuit, `5_7`, also carries one gm-label difference);
`fd-1-2` reduces to **936 circuits differing only in capacitor typing**.  Once
#34 lands, `fd-1-2` reaches full parity and `s-1-2` is down to the lone `5_7`.

| Root cause | Issue | Status |
|---|---|---|
| Mixed-tech composites report `p`/`n` instead of `undefined` | [#30](https://github.com/Firas-Jrad/pyckt/issues/30) | ✅ fixed (PR #37) |
| Four gallery composites missing from the bundled library | [#31](https://github.com/Firas-Jrad/pyckt/issues/31) | ✅ fixed (PR #39; refined in PR #40) |
| DP child ordering + cascoded-DP grouping | [#38](https://github.com/Firas-Jrad/pyckt/issues/38) | ✅ fixed (PR #40) |
| Load parts under-identified (land in `biasParts`) | [#32](https://github.com/Firas-Jrad/pyckt/issues/32) | ✅ fixed (PR #42) |
| gm typing: second/third-stage, `firstStageType`, FD `feedBack` grouping | [#33](https://github.com/Firas-Jrad/pyckt/issues/33) | ✅ fixed (this PR) |
| Capacitor `load`/`compensation` typing inverted | [#34](https://github.com/Firas-Jrad/pyckt/issues/34) | ☐ open — sole remaining blocker |

Notes:
- The gallery *netlists* all parse and recognise cleanly; the remaining
  divergences are exclusively partitioning capacitor typing (#34).
- The gallery was generated with a **newer acst recognition library** than
  the local snapshots.  One `s-1-2` circuit, `5_7`, labels a
  `MosfetNmosNonInvertingInverter` composite `primarySecondStage` where the
  gallery expects `thirdStage`.  This composite has no classifier in the local
  acst snapshot; the newer-acst rule that retypes it can't be reproduced
  without mis-retyping 216 other circuits, so it is left as a documented
  single-circuit residue (0.03 %) to revisit with #34.

<!-- The tables below are regenerated verbatim by scripts/compare_fuboco_gallery.py. -->

## `s-1-2` — 1950 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 1950 | 0 |
| partitioning (`functional_blocks.xml`) | 150 | 1800 |

**recurring diff patterns** (occurrences across all circuits; net names elided):

| n | artefact | pattern | example circuit |
|---:|---|---|---|
| 1800 | partitioning | `missing (in gallery, not pyckt): capacitances/capacitance {'type': 'compensation'} structures=['CapacitorArray']` | `1_1` |
| 1800 | partitioning | `extra (in pyckt, not gallery): capacitances/capacitance {'type': 'load'} structures=['CapacitorArray']` | `1_1` |
| 1 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'thirdStage'} structures=['MosfetNmosNonInvertingInverter']` | `5_7` |
| 1 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNmosNonInvertingInverter']` | `5_7` |

## `fd-1-2` — 936 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 936 | 0 |
| partitioning (`functional_blocks.xml`) | 0 | 936 |

**recurring diff patterns** (occurrences across all circuits; net names elided):

| n | artefact | pattern | example circuit |
|---:|---|---|---|
| 1872 | partitioning | `missing (in gallery, not pyckt): capacitances/capacitance {'type': 'load'} structures=['CapacitorArray']` | `1` |
| 1872 | partitioning | `extra (in pyckt, not gallery): capacitances/capacitance {'type': 'compensation'} structures=['CapacitorArray']` | `1` |
