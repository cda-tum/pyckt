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

## Verdict (updated as follow-up fixes land — this run: post PR #40)

**Structure recognition: COMPLETE parity — 1950/1950 (`s-1-2`) and 936/936
(`fd-1-2`) circuits identical**, all four issue-#31 composites verified
recognised on their reference circuits.  Progression: 18/2 → 342/14 (#30) →
1714/718 (#31) → **all** (#38).  Every remaining diff below is partitioning.

| Root cause | Issue | Status |
|---|---|---|
| Mixed-tech composites report `p`/`n` instead of `undefined` | [#30](https://github.com/Firas-Jrad/pyckt/issues/30) | ✅ fixed (PR #37) |
| Four gallery composites missing from the bundled library | [#31](https://github.com/Firas-Jrad/pyckt/issues/31) | ✅ fixed (PR #39; ordering/rules refined in PR #40) |
| DP child ordering + cascoded-DP grouping | [#38](https://github.com/Firas-Jrad/pyckt/issues/38) | ✅ fixed (PR #40) |
| Load parts under-identified (land in `biasParts`) | [#32](https://github.com/Firas-Jrad/pyckt/issues/32) | ☐ open |
| gm typing: FD `feedBack` grouping, `primarySecondStage`, `firstStageType` | [#33](https://github.com/Firas-Jrad/pyckt/issues/33) | ☐ open |
| Capacitor `load`/`compensation` typing inverted | [#34](https://github.com/Firas-Jrad/pyckt/issues/34) | ☐ open |

Notes:
- The gallery *netlists* all parse and recognise cleanly; the remaining
  divergences are exclusively partitioning classification (#32–#34).
- The gallery was generated with a **newer acst recognition library** than
  the local snapshots; the four issue-#31 structures were reconstructed from
  the gallery's own reference trees.

## `s-1-2` — 1950 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 1950 | 0 |
| partitioning (`functional_blocks.xml`) | 3 | 1947 |

**recurring diff patterns** (occurrences across all circuits; net names elided):

| n | artefact | pattern | example circuit |
|---:|---|---|---|
| 5418 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetNormalArray']` | `1` |
| 2351 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetDiodeArray']` | `1` |
| 1800 | partitioning | `missing (in gallery, not pyckt): capacitances/capacitance {'type': 'compensation'} structures=['CapacitorArray']` | `1_1` |
| 1800 | partitioning | `extra (in pyckt, not gallery): capacitances/capacitance {'type': 'load'} structures=['CapacitorArray']` | `1_1` |
| 1250 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetMixedCascodePair1']` | `1_5` |
| 1170 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray']` | `3` |
| 892 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetCascodePair']` | `1_2` |
| 829 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'firstStageType': 'simple', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 780 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetDiodeArray', 'MosfetNormalArray', 'MosfetNormalArray']` | `2` |
| 650 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetDiodeArray', 'MosfetNormalArray']` | `12` |
| 650 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetDiodeArray', 'MosfetMixedCascodePair2', 'MosfetNormalArray']` | `12` |
| 600 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetMixedCascodePair2']` | `1_5` |
| 550 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNormalArray']` | `1_1` |
| 542 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetCascodePair']` | `1_2` |
| 439 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'telescopic', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 439 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `1` |
| 390 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'foldedCascode', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `31` |
| 390 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `31` |
| 352 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `11` |
| 352 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetCascodePair', 'MosfetNormalArray', 'MosfetNormalArray']` | `11` |
| 240 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetCascodePair', 'MosfetCascodePair', 'MosfetNormalArray', 'MosfetNormalArray']` | `92` |
| 234 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray']` | `5` |
| 169 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetNormalArray']` | `1` |
| 169 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetDiodeStack']` | `2` |
| 169 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetVoltageReference2']` | `3` |
| 156 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetVoltageReference1']` | `35` |
| 156 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetCascodePair', 'MosfetDiodeArray', 'MosfetDiodeArray', 'MosfetDiodeStack', 'MosfetNormalArray', 'MosfetNormalArray']` | `93` |
| 156 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetCascodePair', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetVoltageReference2']` | `95` |
| 156 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetDiodeArray', 'MosfetMixedCascodePair1', 'MosfetMixedCascodePair2', 'MosfetNormalArray', 'MosfetNormalArray']` | `97` |
| 152 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetDiodeArray']` | `31_3` |
| 150 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetCascodePair', 'MosfetNormalArray', 'MosfetNormalArray']` | `92_2` |
| 119 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetPmosNonInvertingInverter']` | `6_1` |
| 115 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNmosNonInvertingInverter']` | `3_7` |
| 78 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetNormalArray']` | `5` |
| 68 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetMixedCascodePair1', 'MosfetMixedCascodePair2', 'MosfetNormalArray']` | `4_10` |
| 65 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetCascodePair', 'MosfetDiodeArray', 'MosfetDiodeStack', 'MosfetNormalArray']` | `7` |
| 65 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetCascodePair', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetVoltageReference2']` | `8` |
| 42 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetCascodePair']` | `4_10` |
| 30 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'thirdStage'} structures=['MosfetCascodePair']` | `91_2` |
| 22 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'thirdStage'} structures=['MosfetNormalArray']` | `91_1` |

## `fd-1-2` — 936 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 936 | 0 |
| partitioning (`functional_blocks.xml`) | 0 | 936 |

**recurring diff patterns** (occurrences across all circuits; net names elided):

| n | artefact | pattern | example circuit |
|---:|---|---|---|
| 4468 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetNormalArray']` | `1_1` |
| 2340 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `1` |
| 1872 | partitioning | `missing (in gallery, not pyckt): capacitances/capacitance {'type': 'load'} structures=['CapacitorArray']` | `1` |
| 1872 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 1872 | partitioning | `extra (in pyckt, not gallery): capacitances/capacitance {'type': 'compensation'} structures=['CapacitorArray']` | `1` |
| 1464 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetDiodeArray']` | `1_5` |
| 1044 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetCascodePair']` | `1_2` |
| 936 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'feedBack'} structures=['MosfetDifferentialPair', 'MosfetDifferentialPair']` | `1` |
| 936 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'firstStageType': 'simple', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 888 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetMixedCascodePair1']` | `1_5` |
| 864 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNormalArray']` | `1_1` |
| 864 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetCascodePair']` | `1_2` |
| 780 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray']` | `3` |
| 624 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `5` |
| 624 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetCascodePair']` | `5` |
| 576 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetMixedCascodePair2']` | `1_5` |
| 400 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `26` |
| 400 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetCascodePair', 'MosfetNormalArray', 'MosfetNormalArray']` | `26` |
| 312 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'simple', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 312 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'foldedCascode', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `5` |
| 312 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'telescopic', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `9` |
| 312 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetDiodeArray', 'MosfetNormalArray']` | `27` |
| 312 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetDiodeArray', 'MosfetMixedCascodePair2', 'MosfetNormalArray']` | `27` |
| 132 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'type': 'thirdStage'} structures=['MosfetCascodePair']` | `5_2` |
| 84 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'type': 'thirdStage'} structures=['MosfetNormalArray']` | `5_8` |
| 20 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNmosNonInvertingInverter']` | `1_7` |
| 20 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetPmosNonInvertingInverter']` | `13_1` |

