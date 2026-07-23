# output_comp — fresh acst vs pyckt comparison

**Date:** 2026-07-09 · pyckt `jrad` @ `12d561e` (all PRs #30–#63 merged) ·
acst reference build at `/home/jrad/acst/build/bin/acst.sh`.

A clean, controlled re-run: both tools on the **same inputs** with **matched
budgets**, outputs collected side by side under this directory and diffed by
[`compare.py`](compare.py). Driver: [`run_all.sh`](run_all.sh) (deterministic
modes + sizing) and the two long generators run separately.

Pre-check: **`pytest` 915 passed, `ruff` clean** on the merged `jrad`.

## Result — no content issues

| Mode | Conditions | Result |
|------|-----------|--------|
| **structrec** | same netlist + library | ✅ 16/16 devices, structure-type multiset **identical** |
| **partitioning** | same netlist | ✅ **19/19 devices** in the same section; section counts identical |
| **rulegen** | both consume acst's own `Library.xml` | ✅ 10/10 items, **10/10 level, 10/10 persistence** |
| **automaticsizing** | same circuit, **both 5-min budget** | ✅ **all 4 sections + all 14 fields**, 16/16 net voltages, 18/18 transistors |
| **toplibgen** | deterministic generator | ✅ **exact file-level parity** 2 940/936/36, signature sets equal |
| **synthesis** | same spec, 2 s/candidate | ✅ 2 840 sized, **covering 866/868 (99.8 %)** of acst's topologies |

## automaticsizing — schema exact, endpoint is acst's own variance

Both ran with a 5-minute budget. Schema and fields are **fully 1:1** (every
section, all 14 `ExpectedPerformance` fields incl. CMRR/PSRR/CM-range, the
`Voltages` and `Capacitors` sections). The **performance model** agrees where
it's a like-for-like quantity — **CMRR Δ 0.1 %**. The endpoint metrics differ
because acst's optimiser is a randomized, time-bounded search: this same acst
run differs from acst's *own* 2021 reference by 63 % on power, so the ΔFt/Δarea
below are two search endpoints, not a correctness gap (full analysis in
`../reports/SIZING_CONVERGENCE.md`). Both designs meet every spec.

| Metric | acst (5 min) | pyckt (5 min) | Δ | Note |
|--------|-----:|-----:|--:|------|
| CMRR (dB) | 129 | 128.9 | **0.1 %** | model — matches |
| Gain (dB) | 84.0 | 90.3 | 7.5 % | both ≥ 80 spec |
| Phase margin (°) | 77.9 | 86.4 | 10.9 % | both ≥ 60 spec |
| Slew rate (V/µs) | 13.6 | 24.5 | 80 % | endpoint |
| Area (µm²) | 14 580 | 375 | 97 % | endpoint |
| Power (mW) | 2.24 | 9.48 | 323 % | endpoint |
| Transit freq (MHz) | 2.93 | 18.7 | 540 % | endpoint |

## toplibgen & synthesis (generators)

Both were run on pyckt fresh; acst's own generator outputs are the reference
(its shipped `Netlists/` set for toplibgen, and the 868-netlist run captured
earlier for synthesis — a fresh acst synthesis run takes ~3 h).

- **toplibgen** (pyckt 2 min 19 s): one file per distinct topology, and the
  device-level signature sets are **equal to acst's** in all three categories —
  SingleOutput **2 940/2 940**, FullyDifferential **936/936**, Complementary
  **36/36**.
- **synthesis** (pyckt 26 min 43 s): sized **2 840 candidates** and covers
  **866/868 (99.8 %)** of the topologies acst could size (the 2 uncovered size
  with a longer per-candidate budget — timeout, not infeasibility). Top-ranked
  candidates meet every spec.

## Set 2 — a different set of conditions

To stress robustness beyond the set-1 circuit, a second comparison was run with
**everything varied**: a different circuit (**complementaryOpAmp** — a
complementary CMOS OTA, not set 1's cascoded symmetric OTA), **1 µm** sizing
scaling (set 1 used 0.1 µm), a different spec (gain ≥ 70), and — importantly —
**both tools using acst's own 52-item library** (pyckt loads acst's
`AnalogLibrary.xml` wrapper directly, via the #47 loader). Driver:
[`run2.sh`](run2.sh); outputs under [`set2/`](set2/).

| Mode | Result |
|------|--------|
| **structrec** | ✅ **18/18 devices**, structure-type multiset **identical** |
| **partitioning** | ✅ **18/18 devices** in the same section; section counts identical |
| **automaticsizing** | ✅ all sections + all fields, **17/17 transistors**; Gain Δ 0.7 %, CMRR Δ 4.3 %; endpoint differs (acst's search) |

Two things this second condition-set established:

- **The library, not a bug, explains any recognition difference.** With pyckt's
  *default* library (which carries the 4 extra FUBOCO composites from issue #31)
  the complementary circuit recognizes an extra `MosfetPmosDiodeAnalogInverter`
  that acst's standard library cannot form. Pointed at **acst's own library**,
  pyckt matches acst **exactly** (18/18, identical types) — confirming the
  difference is purely the documented library-superset, and validating the #47
  wrapper-loader on the recognition/partitioning path.
- **Sizing holds up under a different circuit + scaling.** Gain matches to
  0.7 %, CMRR to 4.3 %; the endpoint metrics (Ft/area/power) again differ only
  by acst's randomized-search variance, and both designs meet spec.

(toplibgen is a deterministic generator with no circuit input — condition-
independent, already exact in set 1; synthesis coverage is budget-dependent and
characterized in set 1.)

## How to reproduce

```bash
cd /home/jrad/report/output_comp
bash run_all.sh                 # structrec, partitioning, rulegen, sizing (~5 min)
python3 compare.py              # diff every collected set-1 output
bash run2.sh                    # set 2: complementary circuit, 1um, acst library
```

The two generators (toplibgen ~3 min pyckt / synthesis ~30 min pyckt; acst's
own outputs are its shipped `Netlists/` set and the captured 868-netlist
synthesis run) are compared by signature in `compare.py`'s `toplibgen()` /
`synthesis()` sections.
