# FUBOCO Gallery comparison — pyckt vs reference (issue #7)

Compares pyckt's structure recognition and partitioning (acst output format)
against the FUBOCO Gallery reference artefacts
(https://github.com/analog-ml/fuboco-gallery) for every circuit of the
`s-1-2` (1950 circuits) and `fd-1-2` (936 circuits) categories.  See the
first section of `scripts/compare_fuboco_gallery.py` for the methodology
(semantic XML comparison; ordinals/order/whitespace/rail-renaming
normalised).

**Regenerate**:

```
.venv/bin/python scripts/compare_fuboco_gallery.py \
    --gallery <fuboco-gallery checkout> --report reports/FUBOCO_GALLERY_REPORT.md
```

## Verdict (updated as follow-up fixes land)

| Root cause | Issue | Status |
|---|---|---|
| Mixed-tech composites report `p`/`n` instead of `undefined` | [#30](https://github.com/Firas-Jrad/pyckt/issues/30) | ✅ fixed (PR #37) |
| `MosfetNmos/PmosDiodeAnalogInverter` + `MosfetNmos/PmosNonInvertingInverter` missing from the bundled library | [#31](https://github.com/Firas-Jrad/pyckt/issues/31) | ✅ fixed (4 library items added) |
| Residual DP diffs: cascoded-DP grouping in GCC circuits, `Input1/Input2` order | [#38](https://github.com/Firas-Jrad/pyckt/issues/38) | ☐ open |
| Load parts under-identified (land in `biasParts`) | [#32](https://github.com/Firas-Jrad/pyckt/issues/32) | ☐ open |
| gm typing: FD `feedBack` grouping, `primarySecondStage`, `firstStageType` | [#33](https://github.com/Firas-Jrad/pyckt/issues/33) | ☐ open |
| Capacitor `load`/`compensation` typing inverted | [#34](https://github.com/Firas-Jrad/pyckt/issues/34) | ☐ open |

Structure-recognition identical circuits: **s-1-2 18 → 342 (#30) → 1714
(#31) of 1950**; **fd-1-2 2 → 14 → 718 of 936**.  Partitioning is still
blocked on #32–#34.

Notes:
- The gallery *netlists* all parse and recognise cleanly; divergences are in
  recognition composites and partitioning classification, not parsing.
- `s-1-2`/`fd-1-2` are whole categories (1-and-2-stage single-output /
  fully-differential per the gallery README), not single variants; `fd-1-2`
  holds exactly 936 circuits — the same count as acst's (and pyckt's) FD
  family.
- The gallery was generated with a **newer acst recognition library** than
  the snapshot bundled in pyckt/the local acst checkout: the four issue-#31
  structures exist in neither of the local libraries and were reconstructed
  from the gallery's own reference trees.

## `s-1-2` — 1950 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 1714 | 236 |
| partitioning (`functional_blocks.xml`) | 1 | 1949 |

**recurring diff patterns** (occurrences across all circuits; net names elided):

| n | artefact | pattern | example circuit |
|---:|---|---|---|
| 5418 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetNormalArray']` | `1` |
| 2351 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetDiodeArray']` | `1` |
| 1800 | partitioning | `missing (in gallery, not pyckt): capacitances/capacitance {'type': 'compensation'} structures=['CapacitorArray']` | `1_1` |
| 1800 | partitioning | `extra (in pyckt, not gallery): capacitances/capacitance {'type': 'load'} structures=['CapacitorArray']` | `1_1` |
| 1250 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetMixedCascodePair1']` | `1_5` |
| 1170 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray']` | `3` |
| 977 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'firstStageType': 'simple', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 892 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetCascodePair']` | `1_2` |
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
| 148 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'simple', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `5_4` |
| 119 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetPmosNonInvertingInverter']` | `6_1` |
| 115 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNmosNonInvertingInverter']` | `3_7` |
| 97 | structrec | `extra (in pyckt, not gallery): structure MosfetDifferentialPair [n] devices=[]` | `7_11` |
| 93 | structrec | `extra (in pyckt, not gallery): structure MosfetDifferentialPair [p] devices=[]` | `1_2` |
| 79 | structrec | `missing (in gallery, not pyckt): structure MosfetDifferentialPair [n] devices=[]` | `7_11` |
| 78 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetNormalArray']` | `5` |
| 69 | structrec | `missing (in gallery, not pyckt): structure MosfetDifferentialPair [p] devices=[]` | `5_4` |
| 68 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetMixedCascodePair1', 'MosfetMixedCascodePair2', 'MosfetNormalArray']` | `4_10` |

## `fd-1-2` — 936 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 718 | 218 |
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
| 109 | structrec | `missing (in gallery, not pyckt): structure MosfetDifferentialPair [p] devices=[]` | `1_3` |
| 109 | structrec | `extra (in pyckt, not gallery): structure MosfetDifferentialPair [p] devices=[]` | `1_3` |
| 109 | structrec | `missing (in gallery, not pyckt): structure MosfetDifferentialPair [n] devices=[]` | `13_2` |
| 109 | structrec | `extra (in pyckt, not gallery): structure MosfetDifferentialPair [n] devices=[]` | `13_2` |
| 84 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'type': 'thirdStage'} structures=['MosfetNormalArray']` | `5_8` |
| 20 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNmosNonInvertingInverter']` | `1_7` |
| 20 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetPmosNonInvertingInverter']` | `13_1` |

