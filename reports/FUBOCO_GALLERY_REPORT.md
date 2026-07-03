# FUBOCO Gallery comparison — pyckt vs reference (issue #7)

Compares pyckt's structure recognition and partitioning (acst output format)
against the FUBOCO Gallery reference artefacts
(https://github.com/analog-ml/fuboco-gallery) for every circuit of the
`s-1-2` (1950 circuits) and `fd-1-2` (936 circuits) categories.

Per circuit the gallery ships the acst-generated `netlist.ckt`,
`subcircuits.xml` (structure recognition) and `functional_blocks.xml`
(partitioning).  pyckt parses the same netlist, runs both analyses, and the
XMLs are compared semantically (structure ordinals, element order,
whitespace, and acst's rail renaming `sourceNmos/sourcePmos → gnd!/vdd!`
normalised away).

**Regenerate**:

```
.venv/bin/python scripts/compare_fuboco_gallery.py \
    --gallery <fuboco-gallery checkout> --report reports/FUBOCO_GALLERY_REPORT.md
```

## Verdict

Not identical.  Bottom line: **s-1-2**: 18/1950 structrec identical, 1/1950
partitioning identical; **fd-1-2**: 2/936 and 0/936.  The diffs are highly
systematic — five root causes explain the entire pattern table below, each
filed as its own follow-up issue:

| # | Root cause | Scope | Issue |
|---|---|---|---|
| 1 | Mixed-tech composite structures report `p`/`n` where acst reports `techType="undefined"` (same trees otherwise) | ~4000 paired structrec entries | [#30](https://github.com/Firas-Jrad/pyckt/issues/30) |
| 2 | `MosfetNmos/PmosDiodeAnalogInverter` (rail-pinned diode inverters) never recognised by pyckt | ~4800 structrec entries | [#31](https://github.com/Firas-Jrad/pyckt/issues/31) |
| 3 | Load parts under-identified — structures acst puts in `loadParts` land in pyckt's `biasParts` | largest partitioning bucket (~14000 entries) | [#32](https://github.com/Firas-Jrad/pyckt/issues/32) |
| 4 | gm typing: FD feedback pairs not grouped as `feedBack`, `primarySecondStage` missing, `firstStageType` stuck at `simple` | all two-stage + all FD circuits | [#33](https://github.com/Firas-Jrad/pyckt/issues/33) |
| 5 | Capacitor typing inverted: two-stage compensation caps typed `load`; FD load caps typed `compensation` | 1800 + 1872 entries | [#34](https://github.com/Firas-Jrad/pyckt/issues/34) |

Notes:
- The gallery *netlists* parse and recognise cleanly (no errors in 2886
  circuits); the divergences are in recognition composites and partitioning
  classification, not parsing.
- `s-1-2`/`fd-1-2` naming: per the gallery README these are whole categories
  ("single-output op-amps, 1- and 2-stage" / "fully-differential, 1- and
  2-stage"), not single variants; `fd-1-2` holds exactly 936 circuits — the
  same count as acst's (and now pyckt's) FD family.

## `s-1-2` — 1950 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 18 | 1932 |
| partitioning (`functional_blocks.xml`) | 1 | 1949 |

**recurring diff patterns** (occurrences across all circuits; net names elided):

| n | artefact | pattern | example circuit |
|---:|---|---|---|
| 5418 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetNormalArray']` | `1` |
| 2351 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetDiodeArray']` | `1` |
| 1800 | partitioning | `missing (in gallery, not pyckt): capacitances/capacitance {'type': 'compensation'} structures=['CapacitorArray']` | `1_1` |
| 1800 | partitioning | `extra (in pyckt, not gallery): capacitances/capacitance {'type': 'load'} structures=['CapacitorArray']` | `1_1` |
| 1352 | structrec | `missing (in gallery, not pyckt): structure MosfetPmosDiodeAnalogInverter [undefined] devices=[]` | `1_3` |
| 1350 | structrec | `missing (in gallery, not pyckt): structure MosfetNmosDiodeAnalogInverter [undefined] devices=[]` | `1` |
| 1250 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetMixedCascodePair1']` | `1_5` |
| 1170 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray']` | `3` |
| 977 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'firstStageType': 'simple', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 892 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetCascodePair']` | `1_2` |
| 780 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetDiodeArray', 'MosfetNormalArray', 'MosfetNormalArray']` | `2` |
| 650 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetDiodeArray', 'MosfetNormalArray']` | `12` |
| 650 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetDiodeArray', 'MosfetMixedCascodePair2', 'MosfetNormalArray']` | `12` |
| 612 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodedAnalogInverter [undefined] devices=[]` | `1_4` |
| 612 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodedAnalogInverter [p] devices=[]` | `1_4` |
| 600 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetMixedCascodePair2']` | `1_5` |
| 550 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNormalArray']` | `1_1` |
| 542 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetCascodePair']` | `1_2` |
| 456 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodedNMOSAnalogInverter [undefined] devices=[]` | `1_2` |
| 456 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodedNMOSAnalogInverter [p] devices=[]` | `1_2` |
| 456 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodedPMOSAnalogInverter [undefined] devices=[]` | `1_3` |
| 456 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodedPMOSAnalogInverter [p] devices=[]` | `1_3` |
| 439 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'telescopic', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 439 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `1` |
| 390 | structrec | `missing (in gallery, not pyckt): structure MosfetFoldedCascodeDifferentialPair [undefined] devices=[]` | `31` |
| 390 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'foldedCascode', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `31` |
| 390 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `31` |
| 378 | structrec | `extra (in pyckt, not gallery): structure MosfetAnalogInverter [p] devices=[]` | `1_1` |
| 352 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `11` |
| 352 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetCascodePair', 'MosfetNormalArray', 'MosfetNormalArray']` | `11` |
| 241 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodeAnalogInverterPmosDiodeTransistor [undefined] devices=[]` | `1_6` |
| 241 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodeAnalogInverterPmosDiodeTransistor [p] devices=[]` | `1_6` |
| 240 | partitioning | `extra (in pyckt, not gallery): loadParts/loadPart {} structures=['MosfetCascodePair', 'MosfetCascodePair', 'MosfetNormalArray', 'MosfetNormalArray']` | `92` |
| 234 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetDiodeArray', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray']` | `5` |
| 231 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodeAnalogInverterNmosDiodeTransistor [undefined] devices=[]` | `1_12` |
| 231 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodeAnalogInverterNmosDiodeTransistor [p] devices=[]` | `1_12` |
| 192 | structrec | `extra (in pyckt, not gallery): structure MosfetFoldedCascodeDifferentialPair [p] devices=[]` | `31_2` |
| 192 | structrec | `extra (in pyckt, not gallery): structure MosfetFoldedCascodeDifferentialPair [n] devices=[]` | `36_1` |
| 189 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodePMOSAnalogInverterOneDiodeTransistor [undefined] devices=[]` | `1_5` |
| 189 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodePMOSAnalogInverterOneDiodeTransistor [p] devices=[]` | `1_5` |

## `fd-1-2` — 936 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 2 | 934 |
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
| 1069 | structrec | `missing (in gallery, not pyckt): structure MosfetNmosDiodeAnalogInverter [undefined] devices=[]` | `1_2` |
| 1069 | structrec | `missing (in gallery, not pyckt): structure MosfetPmosDiodeAnalogInverter [undefined] devices=[]` | `1_3` |
| 1044 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetCascodePair']` | `1_2` |
| 936 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'feedBack'} structures=['MosfetDifferentialPair', 'MosfetDifferentialPair']` | `1` |
| 936 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'firstStageType': 'simple', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 888 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetMixedCascodePair1']` | `1_5` |
| 864 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNormalArray']` | `1_1` |
| 864 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetCascodePair']` | `1_2` |
| 780 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray', 'MosfetNormalArray']` | `3` |
| 624 | partitioning | `missing (in gallery, not pyckt): loadParts/loadPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `5` |
| 624 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetCascodePair']` | `5` |
| 600 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodedAnalogInverter [undefined] devices=[]` | `1_4` |
| 600 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodedAnalogInverter [p] devices=[]` | `1_4` |
| 576 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetMixedCascodePair2']` | `1_5` |
| 444 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodedNMOSAnalogInverter [undefined] devices=[]` | `1_2` |
| 444 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodedNMOSAnalogInverter [p] devices=[]` | `1_2` |
| 444 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodedPMOSAnalogInverter [undefined] devices=[]` | `1_3` |
| 444 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodedPMOSAnalogInverter [p] devices=[]` | `1_3` |
| 400 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetNormalArray', 'MosfetNormalArray']` | `26` |
| 400 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetCascodePair', 'MosfetNormalArray', 'MosfetNormalArray']` | `26` |
| 312 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'simple', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `1` |
| 312 | structrec | `missing (in gallery, not pyckt): structure MosfetFoldedCascodeDifferentialPair [undefined] devices=[]` | `5` |
| 312 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'foldedCascode', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `5` |
| 312 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'firstStageType': 'telescopic', 'type': 'firstStage'} structures=['MosfetDifferentialPair']` | `9` |
| 312 | partitioning | `missing (in gallery, not pyckt): biasParts/biasPart {} structures=['MosfetDiodeArray', 'MosfetNormalArray']` | `27` |
| 312 | partitioning | `extra (in pyckt, not gallery): biasParts/biasPart {} structures=['MosfetDiodeArray', 'MosfetMixedCascodePair2', 'MosfetNormalArray']` | `27` |
| 288 | structrec | `extra (in pyckt, not gallery): structure MosfetAnalogInverter [p] devices=[]` | `1_1` |
| 208 | structrec | `missing (in gallery, not pyckt): structure MosfetAnalogInverter [undefined] devices=[]` | `1_1` |
| 156 | structrec | `extra (in pyckt, not gallery): structure MosfetFoldedCascodeDifferentialPair [p] devices=[]` | `5` |
| 156 | structrec | `extra (in pyckt, not gallery): structure MosfetFoldedCascodeDifferentialPair [n] devices=[]` | `17` |
| 144 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodePMOSAnalogInverterOneDiodeTransistor [undefined] devices=[]` | `1_5` |
| 144 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodePMOSAnalogInverterOneDiodeTransistor [p] devices=[]` | `1_5` |
| 144 | structrec | `missing (in gallery, not pyckt): structure MosfetCascodeAnalogInverterPmosDiodeTransistor [undefined] devices=[]` | `1_6` |
| 144 | structrec | `extra (in pyckt, not gallery): structure MosfetCascodeAnalogInverterPmosDiodeTransistor [p] devices=[]` | `1_6` |

