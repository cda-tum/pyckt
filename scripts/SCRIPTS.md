# Per-mode run scripts — inputs & outputs

Four standalone scripts run the analysis modes individually. The three
deterministic recognition modes run **pyckt** (in acst-compatible format) and,
when the acst binary is present, the **acst reference** for the same input.
`run_toplibgen.sh` is **pyckt-only** (acst is a benchmark and is not run there).

Each script auto-detects the repo root from its own location, so they work
from any working directory without configuration.

```bash
cd pyckt          # the repo root
./scripts/run_structrec.sh
./scripts/run_partitioning.sh
./scripts/run_rulegen.sh
./scripts/run_toplibgen.sh
```

All paths are environment-overridable: `PYCKT`, `ACST`, `PY_IN`, `PY_DATA`,
`ACST_IN`, `ACST_LIB`, `OUT` (and `NAME` for rulegen). If the acst binary is not
found, the script still runs pyckt and just skips the reference.

---

## `run_structrec.sh` — Structure Recognition

Recognises the analog structures (current mirrors, diff pairs, cascodes, …) in a
flat transistor netlist.

**Required inputs** (`$PY_IN/StructureRecognition/` for pyckt,
`$ACST_IN/StructureRecognition/` for acst):

| File | Role |
|------|------|
| `input.ckt` | flat transistor netlist to recognise |
| `deviceTypes.xcat` | device-type definitions (pins, tech) |
| `HSpiceMapping.xcat` | how to read each netlist device line |
| `supplyNets.xcat` | which nets are VDD / GND |
| `AnalogLibrary.xml` (`$ACST_LIB`) | recognition library (templates + dominance) — pyckt falls back to its bundled copy |

**Generated outputs** (default under `output/structrec/`):

| File | What |
|------|------|
| `$OUT/py/py_acst.xml` | pyckt result — `<acst_results>/<structure_recognition_results>` |
| `$OUT/cpp/cpp.xml` | acst reference (same schema) |

---

## `run_partitioning.sh` — Circuit Partitioning

Classifies the recognised structures into op-amp parts (gm path, load, bias,
capacitance).

**Required inputs** (`$PY_IN/Partitioning/`, `$ACST_IN/Partitioning/`):

| File | Role |
|------|------|
| `cascodedSymmetricalCMOSOTA.hspice` | the op-amp netlist |
| `deviceTypes.xcat`, `HSpiceMapping.xcat`, `supplyNets.xcat` | parsing config (as above) |
| `AnalogLibrary.xml` (`$ACST_LIB`) | recognition library |

Like acst, pyckt derives the input/output/bias/supply net roles from the
circuit structure — no `CircuitParameterAndSpecifications.xml` is needed
(`--circuit-params` remains available as an optional override).

**Generated outputs** (default under `output/partitioning/`):

| File | What |
|------|------|
| `$OUT/py/py_acst.xml` | pyckt — `<acst_results>/<circuit_partitioning_results>` (gmParts / loadParts / biasParts / capacitances / …) |
| `$OUT/cpp/cpp.xml` | acst reference (same schema) |

---

## `run_rulegen.sh` — Recognition-rule generation

Learns a **recognition library**: bottom-up pairs the recognised structures into
new named composite items (`<Name>1..N`) until the whole op-amp is one learned
structure. (This is acst's `rulegen`; it is *not* sizing-rule generation.)

**Required inputs** (`$PY_IN/RuleGeneration/`, `$ACST_IN/RuleGeneration/`):

| File | Role |
|------|------|
| `cascodedSymmetricalCMOSOTA.hspice` | the op-amp to learn |
| `deviceTypes.xcat`, `HSpiceMapping.xcat`, `supplyNets.xcat` | parsing config |
| `AnalogLibrary.xml` (`$ACST_LIB`) / `RuleGeneration/Library.xml` | base recognition library (pyckt uses `$ACST_LIB`; acst uses the bundle's `Library.xml`) |
| `--structure-name` / `$NAME` | base name for the learned items (default `SymmetricalCascodeOpAmp`) |

Passing `--library "$ACST_LIB"` is deliberate: it points pyckt at acst's own
52-item library so both tools learn from the *same* base. pyckt's bundled
default library carries four extra composites (issue #31), which would yield an
11th learned item — the `$ACST_LIB` default keeps the comparison like-for-like.
`--library` accepts either a directory or acst's wrapper-file form directly
(issue #47).

**Generated outputs** (default under `output/rulegen/`):

| File | What |
|------|------|
| `$OUT/py_acst/<Name>Library.xml` | pyckt — `<pairLibrary>` index (item files + hierarchy levels + persistence) |
| `$OUT/py_acst/Items/<Name>N.xml` | pyckt — one learned `<pairLibraryItem>` per composite (10 for this op-amp) |
| `$OUT/cpp/<Name>Library.xml` + `Items/` | acst reference (copied from `$ACST_IN/RuleGeneration/<Name>/`, since acst writes next to its input library, not via `--output-file`) |

pyckt matches acst **item-for-item**: 10/10 learned items at the same hierarchy
level and the same per-item persistence (issue #5).

---

## `run_toplibgen.sh` — Topology-library generation (pyckt-only)

Enumerates **every** op-amp topology and writes one `.ckt` netlist per topology
in ACST's topology-library format (`.suckt`/`.end`, `nmos`/`pmos` models, no
sizing). This is pyckt's `toplibgen` with `--output-format acst`; acst is a
benchmark and is **not** run here.

**Required inputs:** none — the generator works from scratch (HL2–HL5 factories).

**Generated outputs** (default under `output/toplibgen/`):

| Directory | What |
|-----------|------|
| `SingleOutputOpAmps/` | `one_stage_…` / `two_stage_single_output_op_amp<N>.ckt` |
| `FullyDifferentialOpAmps/` | `one_stage_…` / `two_stage_fully_differential_op_amp<N>.ckt` |
| `ComplementaryOpAmps/` | `complementary_op_amp<N>.ckt` |

The script prints per-category counts, now at **exact parity with the acst
benchmark** (issues #20 + #48 — device-for-device topology set, one file per
distinct topology):

| Category | pyckt | acst benchmark |
|----------|------:|---------------:|
| SingleOutputOpAmps | 2940 | 2940 |
| FullyDifferentialOpAmps | 936 | 936 |
| ComplementaryOpAmps | 36 | 36 |
| **TOTAL** | **3912** | **3912** |

All three categories match exactly and the emitted netlists are structurally
identical to acst's (verified by canonical device-level signature — see
`comparison/topology_signature.py` and `reports/TOPOLOGY_COUNTS.md`). The
writer emits one file per *distinct* topology (the generator produces 4302
raw candidates, 390 of which are structural duplicates that are de-duplicated
at emission), and re-running into a populated directory clears the previous
output first.

Paths are environment-overridable: `PYCKT`, `OUT`.

---

## Output location

Each script defaults to writing into `output/<mode>/` inside the repo root
(i.e. `pyckt/output/`).  Override with the `OUT` environment variable:

```bash
OUT=/tmp/results ./scripts/run_structrec.sh
```
