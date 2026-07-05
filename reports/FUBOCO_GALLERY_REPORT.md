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

## Verdict (this run: post #34 — capacitor typing)

**Effectively complete gallery parity.**

- **Structure recognition: 1950/1950 (`s-1-2`) + 936/936 (`fd-1-2`) identical.**
- **Partitioning: `fd-1-2` 936/936 identical; `s-1-2` 1949/1950 identical.**

The whole 2886-circuit gallery now matches except a single `s-1-2` circuit
(`5_7`) that carries one gm-label difference (see below).  The follow-up
issues spawned from #7 are all resolved:

| Root cause | Issue | Status |
|---|---|---|
| Mixed-tech composites report `p`/`n` instead of `undefined` | [#30](https://github.com/Firas-Jrad/pyckt/issues/30) | ✅ fixed (PR #37) |
| Four gallery composites missing from the bundled library | [#31](https://github.com/Firas-Jrad/pyckt/issues/31) | ✅ fixed (PR #39; refined in PR #40) |
| DP child ordering + cascoded-DP grouping | [#38](https://github.com/Firas-Jrad/pyckt/issues/38) | ✅ fixed (PR #40) |
| Load parts under-identified (land in `biasParts`) | [#32](https://github.com/Firas-Jrad/pyckt/issues/32) | ✅ fixed (PR #42) |
| gm typing: second/third-stage, `firstStageType`, FD `feedBack` | [#33](https://github.com/Firas-Jrad/pyckt/issues/33) | ✅ fixed (PR #43) |
| Capacitor `load`/`compensation` typing inverted | [#34](https://github.com/Firas-Jrad/pyckt/issues/34) | ✅ fixed (this PR) |

Progression — structrec: 18/2 → 342/14 (#30) → 1714/718 (#31) → **all**
(#38).  Partitioning identical (`s-1-2`/`fd-1-2`): 3/0 → 150/0 (#33) →
**1949/936** (#34).

Notes:
- The gallery was generated with a **newer acst recognition library** than the
  local snapshots.  The lone `5_7` residue labels a
  `MosfetNmosNonInvertingInverter` composite `primarySecondStage` where the
  gallery expects `thirdStage`; that composite has no classifier in the local
  acst snapshot, and the newer-acst rule that retypes it mis-retypes 216 other
  circuits, so it is documented rather than forced.

<!-- The tables below are regenerated verbatim by scripts/compare_fuboco_gallery.py. -->

## `s-1-2` — 1950 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 1950 | 0 |
| partitioning (`functional_blocks.xml`) | 1949 | 1 |

**recurring diff patterns** (occurrences across all circuits; net names elided):

| n | artefact | pattern | example circuit |
|---:|---|---|---|
| 1 | partitioning | `missing (in gallery, not pyckt): gmParts/gmPart {'type': 'thirdStage'} structures=['MosfetNmosNonInvertingInverter']` | `5_7` |
| 1 | partitioning | `extra (in pyckt, not gallery): gmParts/gmPart {'type': 'primarySecondStage'} structures=['MosfetNmosNonInvertingInverter']` | `5_7` |

## `fd-1-2` — 936 circuits

| artefact | identical | differing |
|---|---:|---:|
| structure recognition (`subcircuits.xml`) | 936 | 0 |
| partitioning (`functional_blocks.xml`) | 936 | 0 |
