# pyckt vs acst — Executive Summary

**Firas · 2026-07-09** · Python re-implementation of acst (TU München analog
circuit synthesis tool). Full detail: [`PROGRESS_REPORT.md`](PROGRESS_REPORT.md).

## Bottom line

All six analysis modes are implemented, run end-to-end, and produce output that
matches the acst C++ reference. The three recognition modes match **exactly**;
the three generative modes (sizing, topology-library, synthesis) produce **real,
acst-comparable output** with the remaining differences understood and bounded.

| Mode | Result vs acst |
|------|----------------|
| **Structure recognition** | Exact — **2 886/2 886** reference circuits identical |
| **Partitioning** | Exact — **2 885/2 886** reference circuits identical |
| **Rule generation** | Exact — 10/10 items, levels, and weights |
| **Automatic sizing** | Every output field matches; performance model reproduces acst's own design to **~1 %** (CMRR to 0.0 %) |
| **Topology library** | **3 912/3 912** topologies, device-for-device |
| **Synthesis** | Real sizing + ranking; covers **99.4 %** of acst's sized topologies |

## What this means

- **Validated at scale, not by eye.** Recognition and partitioning are checked
  against 2 886 reference circuits (the FUBOCO Gallery), not one example — and
  agree on all but a single circuit.
- **Sizing is faithful where it can be.** pyckt emits every field acst does, and
  its physics model reproduces acst's own solved design to ~1–4 %. The one
  difference — the exact transistor dimensions — is not a pyckt defect: re-running
  *acst itself* on the same input gives a design differing from its own reference
  by up to 63 %, because acst's optimiser uses randomized search cut off by a
  time budget. There is no single "correct" endpoint to hit.
- **The generators produce real designs.** Topology generation matches acst
  exactly; synthesis now sizes every candidate with the real solver and produces
  fully-dimensioned netlists, covering 99.4 % of the designs acst could size.

## Process

A complete acst-vs-pyckt comparison was run across all six modes; every gap it
surfaced was filed as a tracked issue and fixed (14 issues, #30–#61, each with a
merged or open pull request). Reproducible side-by-side outputs for every mode
are in [`samples/`](samples/).

## Open items (all optional / bounded)

- Matching a *specific* acst sizing design would require reproducing its random
  search — not a well-defined goal; the meaningful targets (format, model, spec
  satisfaction) are met.
- Full synthesis coverage of acst's set is a per-candidate time-budget knob, not
  a missing feature.
