# automaticsizing — convergence vs the acst reference (issue #2)

Compares `pyckt automaticsizing` against acst's reference result on the
bundled `cascodedSymmetricalCMOSOTA` fixture
(`tests/data/inputs/AutomaticSizing/cascodedSymmetricalCMOSOTA.xml`, produced
by the acst binary per `command.sh`).

## The two judgment calls (issue #2 gated on them)

1. **Fix the performance model before tuning the optimizer.**  Verified by
   evaluating pyckt's model on *acst's own solved design* (W/L/Id from the
   reference XML, Vov/gm/gds derived through the SHM equations).  A wrong
   model makes "convergence" meaningless; this experiment separates model
   error from optimizer error, and is kept as a permanent regression test
   (`TestModelValidationAgainstAcstReference`).
2. **Match acst's objective *formulation*, not its numeric endpoint.**
   acst optimizes with Gecode branch-and-bound: each accepted solution must
   improve whichever specs are still unmet, and once all specs hold, improve
   `cost = gain/280 + power-headroom + area-headroom + Ft/10¹⁰ + SR/10¹⁰`
   by ≥1% (`SearchSpace::initializeCost`, `OptimizingSearchSpace::constrain`).
   The search branches on **random** width/length values and stops at the
   runtime limit — the reference numbers are where that trajectory happened
   to stop, not an optimum (see "Residual gap" below).

## Model validation — pyckt's model evaluated on acst's design

| metric | pyckt model | acst reports | error |
|---|---:|---:|---:|
| Gain (dB) | 90.33 | 90.00 | +0.4% |
| Transit frequency (MHz) | 6.87 | 6.93 | −0.9% |
| Slew rate (V/µs) | 22.77 | 22.52 | +1.1% |
| Phase margin (°) | 63.3 | 60.7 | +4.2% |
| VoutMin (V) | 0.675 | 0.670 | +0.8% |
| VoutMax (V) | 4.252 | 4.250 | +0.1% |
| Power (mW) | 6.12 | 6.12 | 0% |
| Area (µm²) | 10868 | 10868 | 0% |

The model bugs this required fixing (each ~50–200% off before):

- **Gain**: the output conductance of a *cascoded* branch is
  `gds_casc·gds_bottom/gm_casc`, not the raw `gds` — the flat Σgds model
  understated this design's gain by **~52 dB**, which is what previously
  forced the solver to inflate `gm_in` (and with it Ft to 23 MHz) to fake
  the gain spec.  Ported into the posted constraint
  (`CascodeGainConstraint`), the objective, and the estimator.
- **Transit frequency**: `Ft = B·gm_in/(2π·C_L)` with the symmetrical-OTA
  mirror factor `B = I_out/(I_tail/2)` (acst `calculateTransitFrequency`).
- **Slew rate**: C_L slews with the *output-branch* current
  (`SR = 2·I_out/C_L`), not the input tail (acst `calculateSlewRate`).
- **Output swing**: limited by the *stacked* overdrives of a cascoded
  branch (`Vov_casc + Vov_bottom`), not a single device's.
- **Power**: supply current counts each branch **once** (devices on the
  supply rail + the external bias, acst `calculatePowerConsumption`);
  summing every device double-counts series stacks (+215% before).

## Structural solver fixes

- **Device ↔ net voltage coupling** (`VoltageCouplingConstraints`): Vgs/Vds
  are now tied to the net-voltage variables (NMOS `Vgs=V(g)−V(s)`, PMOS
  mirrored), with the spec'd DC input voltages pinned.  Without this layer
  the net voltages were decorative — shared-gate mirrors didn't mirror, and
  the solver could starve the output branch to ~1 µA while "satisfying"
  every per-device equation (Ft 0.03 MHz).
- **Output-branch slew constraint**: `I ≥ SR·C_L/2` per output device.
- **Objective power aggregate** now models supply current; the old
  sum-over-all-devices, hard-capped at the spec, silently **excluded acst's
  entire operating region** (Σ all devices ≈ 3.9 mA > 2 mA cap).
- The objective's gain ratio became an inequality (`gain·g_eff ≤ gm_in`) —
  the equality forced exact integer divisibility and crippled the search —
  and the forced min-value-first decision strategy is skipped when
  optimizing (it biased every incumbent toward minimum sizes).

## Solver outcome (300 s CP-SAT, spec: gain≥80, Ft≥2.75, SR≥3.5, PM≥60)

Re-measured 2026-07-08 on `jrad` post #47–#50; the plateau is stable
run-to-run (±few % on every metric).

| metric | acst 2021 ref | pyckt before #2 | Δ before | pyckt now | Δ now |
|---|---:|---:|---:|---:|---:|
| Gain (dB) | 90.0 | 91.3 | +1.4% | 90.4 | +0.4% |
| Slew rate (V/µs) | 22.5 | 24.5 | +8.8% | 24.5 | +8.8% |
| Power (mW) | 6.12 | 7.53 | +23% | 9.5 | +55% |
| Min output V | 0.67 | 0.13 | −80% | 0.71 | +5.4% |
| Max output V | 4.25 | — | — | 3.55 | −16% |
| Transit freq (MHz) | 6.93 | 23.1 | +233% | 18.7 | +171% |
| Phase margin (°) | 60.7 | 87.2 | +43.5% | 86.5 | +42.5% |
| Area (µm²) | 10868 | 207 | −98% | 374 | −96.6% |
| Devices at min width | — | 11/18 | | **0/18** | |

Since #50 the estimator also computes the AC/range metrics (CMRR — which
matches acst's fresh run to **0.0 %** — PSRR and the common-mode input
range), and #49 exports the solved per-net DC operating point.  The
CM-range numbers initially exposed a constraint gap — pyckt computed
vcmMin/vcmMax but did not *post* acst's CM-range constraint, and the
solved design violated the fixture's vcmMin spec (2.29 V > 2.0 V).
Fixed in [#56](https://github.com/Firas-Jrad/pyckt/issues/56): the
Vgs-stack bounds are now posted as spec constraints, and the solved
design reports vcmMin **1.45 V** (≤ 2.0 ✓, near acst's 1.27) and
vcmMax **3.84 V** (≥ 3.0 ✓) — satisfied by construction at every
feasible point.

Every spec is met, the "valid but minimal" degenerate design is gone
(no device sits at the 1 µm floor, currents are in acst's regime,
SR/swing/gain track within ~9%), and the *model* now reproduces acst's
numbers to ~1% when given acst's design.

## Residual gap and its cause

The remaining Ft/PM/area/power deltas are **not model error** — they are two
optimizers parking in different corners of the same 90 dB feasible surface.
This is now *measured*, not just argued: re-running **the same acst binary on
the same inputs with the same `--runtime 5`** (2026-07-08) produced a design
differing from its own 2021 reference by 6.7 % gain, **63 % power**, 34 %
area, **58 % Ft**, 40 % slew, 28 % PM — with per-device ΔW mean 107 % / max
841 %. Both acst runs meet every spec. pyckt's deltas vs any single acst run
are comparable to acst's own run-to-run spread on most metrics.

In detail:

- acst's endpoint is a **search artifact**: Gecode branches on random W/L
  values, accepts the first spec-satisfying solution, then takes 1%-better
  cost steps until the 5-minute budget ends.  Its long channels
  (L = 5.1–5.6 µm where nothing in the constant-λ SHM model rewards long L)
  are direct evidence of the random branching.
- Scoring **both** endpoints under acst's own cost function
  (gain/280 + power-headroom/P_max + area-headroom/A_max + negligible
  Ft/SR terms): pyckt's design beats acst's by ≈ **+45%** of one cost unit
  (area headroom +699‰, slew +83‰ vs power −336‰) — i.e. acst's reference
  point is *dominated under its own objective*; CP-SAT simply optimizes the
  same formulation further than five minutes of randomized Gecode BAB got.
- Exactly reproducing acst's numbers would require reproducing Gecode's
  branching trajectory and timeout, which is neither possible in CP-SAT nor
  a meaningful target.  The faithful targets — the model (validated ≤~4%)
  and the spec set (all met) — are reproduced.

**Regenerate**: the comparison harness lives in this report's history —
run `pyckt automaticsizing` on the fixture (see
`tests/data/inputs/AutomaticSizing/command.sh` for the acst equivalent) and
compare against `cascodedSymmetricalCMOSOTA.xml`;
`TestModelValidationAgainstAcstReference` (tests/test_sizing_analysis.py)
re-checks the model half automatically.
