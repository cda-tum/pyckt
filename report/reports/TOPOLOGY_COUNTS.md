# Topology library — per-category op-amp counts (issue #8)

Cross-tab of the generated topology library by stage count and
output family (the symmetrical one-stage family is acst's own
`symmetrical_op_amp` sub-family of `SingleOutputOpAmps`).

**Regenerate**: `.venv/bin/python scripts/report_topology_counts.py`

| | Single-ended | Symmetrical | Fully-differential | Complementary | total |
|---|---:|---:|---:|---:|---:|
| **1-stage** | 240 | 210 | 72 | 36 | 558 |
| **2-stage** | 2880 | 0 | 864 | 0 | 3744 |
| **total** | 3120 | 210 | 936 | 36 | 4302 |

Counts are *generated* topologies.  The single-ended enumeration
contains 30 one-stage variants (and their 360 two-stage multiples)
that are structural duplicates of other variants, so the library
collapses to **3912 distinct** topologies — exactly acst's reference
set, matched device-for-device (issue #20): `SingleOutputOpAmps`
2940 (= single-ended 210×13 + symmetrical 210),
`FullyDifferentialOpAmps` 936 (= 72×13), `ComplementaryOpAmps` 36
(one-stage only).
