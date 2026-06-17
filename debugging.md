# Debugging pyckt

A practical guide to dropping into [`pdb`](https://docs.python.org/3/library/pdb.html) for the three places things tend to break:

1. CLI subcommands (`pyckt structrec`, `automaticsizing`, …)
2. The topogen gallery `__main__` scripts (`src/topogen/HL*/…`)
3. The OR-Tools CP-SAT solver inside `src/pyckt/sizing/solver.py`

Audience: someone touching the repo for the first time. We use **command-line debugging only** — `breakpoint()` and `python -m pdb`. No IDE config.

---

## 1. Environment setup (read this first)

Run everything from the project root: `/home/jrad/pyckt/pyckt`.

### The non-obvious bits

- **Python 3.11 is required.** `pyproject.toml` declares `requires-python = ">=3.11"`.
- **`PYTHONPATH=src`** must be set for any direct `python` invocation (e.g. running a `__main__` script). Pytest reads `pythonpath = ["src"]` from `pyproject.toml` and doesn't need it.
- **The project-local `.venv`** at `.venv/` has `pytest` but not `coverage` / `pytest-cov`. Don't rely on it for coverage runs.
- **The shared `.venv` is broken in a specific way.** `/home/jrad/.venv/bin/python3.11` is a symlink that resolves to system Python 3.8, whose `sys.path` does not see the 3.11 site-packages. You must run the system 3.11 binary directly and inject `PYTHONPATH` by hand:

  ```bash
  PYTHONPATH=/home/jrad/.venv/lib/python3.11/site-packages:src \
    /usr/bin/python3.11 -m pytest tests/test_topology.py -q
  ```

  Confirm setup: this should print `118 passed`.

### Recommended shell alias

```bash
# add to ~/.bashrc / ~/.zshrc
alias pyckt-py='PYTHONPATH=/home/jrad/.venv/lib/python3.11/site-packages:src /usr/bin/python3.11'
```

Then every command below becomes shorter:

```bash
pyckt-py -m pytest tests/test_topology.py -q
pyckt-py src/topogen/HL2/cb.py
pyckt-py -m pdb -m pyckt.cli structrec --circuit …
```

The rest of this guide assumes the alias.

---

## 2. Debugging the CLI

### Entry point

`src/pyckt/cli.py` — `run(argv)` is the in-process entry point; `main()` is the console-script wrapper. Subcommands are registered in `ANALYSIS_REGISTRY` at [src/pyckt/cli.py:42](src/pyckt/cli.py#L42):

| Subcommand        | Analysis class                                  |
|-------------------|-------------------------------------------------|
| `structrec`       | `recognition.analysis.StructRecAnalysis`        |
| `rulegen`         | `recognition.analysis.RuleGenAnalysis`          |
| `partitioning`    | `partitioning.analysis.PartitioningAnalysis`    |
| `automaticsizing` | `pyckt.sizing.analysis.AutomaticSizingAnalysis` |
| `synthesis`       | `pyckt.synthesis.analysis.SynthesisAnalysis`    |
| `toplibgen`       | `topogen.analysis.TopLibGenAnalysis`            |

### The exception boundary

[`run()` at cli.py:206](src/pyckt/cli.py#L206) wraps the analysis lifecycle (`initialize / compute / write`) in a single `try / except Exception` block at [cli.py:233](src/pyckt/cli.py#L233). Any exception is **logged** and converted into `Result(returncode=1, data=None)` — you will *not* see a raw traceback unless you go around it.

Two ways to surface the real error:

**a) `breakpoint()` inside the analysis class** (preferred)

```python
# src/pyckt/sizing/analysis.py (or wherever the suspect step lives)
def compute(self):
    breakpoint()
    ...
```

Then run the CLI normally and pdb stops at that line.

**b) `python -m pdb` wrapping the whole thing**

```bash
pyckt-py -m pdb -m pyckt.cli automaticsizing --circuit …
```

When the exception fires inside the try-block, hit `c` to keep going until pdb stops at the handler. Then `up` until you're back in the failing frame.

### A worked example: `automaticsizing`

Bundled inputs live at `tests/data/inputs/AutomaticSizing/`. The canonical flag set is captured in `tests/data/inputs/AutomaticSizing/command.sh` — copy it and replace the placeholders. Translated to the actual `pyckt` CLI:

```bash
cd tests/data/inputs/AutomaticSizing/
pyckt-py -m pyckt.cli --log-level-console DEBUG automaticsizing \
  --circuit cascodedSymmetricalCMOSOTA.hspice \
  --device-types deviceTypes.xcat \
  --mapping HSpiceMapping.xcat \
  --supply-nets supplyNets.xcat \
  --tech-file TechnologyFile.xml \
  --circuit-params CircuitParameterAndSpecifications.xml \
  --output cascodedSymmetricalCMOSOTA.xml \
  --timeout 5 \
  --transistor-model SHM \
  --scaling 0.1mum
```

`--log-level-console` accepts `DEBUG` (default), `TRACE`, or `OFF` — see [cli.py:79](src/pyckt/cli.py#L79).

### In-process invocation (handy for stepping)

If you want to drive the CLI from a REPL or a one-off script without spawning a subprocess:

```python
from pyckt.cli import run

result = run([
    "structrec",
    "--circuit", "tests/data/inputs/StructureRecognition/...hspice",
    "--device-types", "tests/data/inputs/StructureRecognition/deviceTypes.xcat",
    "--mapping", "tests/data/inputs/StructureRecognition/HSpiceMapping.xcat",
    "--supply-nets", "tests/data/inputs/StructureRecognition/supplyNets.xcat",
    "--output", "/tmp/out.xml",
])
assert result.returncode == 0
analysis = result.data            # the AbstractAnalysis instance
print(analysis.structure_circuits)
```

Drop `breakpoint()` inside any analysis-class method first and the REPL hands you a live pdb session.

---

## 3. Debugging the topogen gallery scripts

Each topogen `__main__` builds every variant the file knows about and writes DOT files (+ PNGs via the `dot` binary) under `gallery/HL*/<name>/{dots,images}/`.

Files with runnable `__main__` blocks:

- HL2: `src/topogen/HL2/{cb,ccp,cm,dp,inv,vb}.py`
- HL3: `src/topogen/HL3/{l,lp,sb,tc}.py`
- HL4: `src/topogen/HL4/{inv,non_inv}.py`
- HL5: `src/topogen/HL5/opamps.py`

Run any of them directly:

```bash
pyckt-py src/topogen/HL3/lp.py
ls gallery/HL3/lp/{dots,images}/
```

### What gets generated

Running `src/topogen/HL3/lp.py` produces **64 `.dot` files** in `gallery/HL3/lp/dots/` — one per circuit variant. Each file is named `lp_<typeIndex>_<variantIndex>.dot`, e.g.:

```
gallery/HL3/lp/dots/lp_0_0.dot
gallery/HL3/lp/dots/lp_0_1.dot
gallery/HL3/lp/dots/lp_10_0.dot
...
```

Each `.dot` file is a [Graphviz](https://graphviz.org/) `digraph` describing one load-part topology. The nodes are transistor terminals (S, G, D) rendered as record-shaped boxes; the edges are net connections. Example snippet from `lp_0_0.dot`:

```dot
digraph g {
  subgraph "cluster_..." {
    label="[p]  ([-1].lp1)"
    subgraph "cluster_..." {
      label="[?]  ([0].ts1)"
      ...
      "top...nt1" [label="{ <S> S↲| <G> G| <D> D }" shape="record"]
    }
  }
}
```

The label format `[p] ([0].ts1)` means: tech-type `p` (PMOS), instance index 0, named `ts1`.

If `graphviz` (`dot` binary) is installed, a matching PNG is also written to `gallery/HL3/lp/images/lp_0_0.png` — a visual schematic of that topology. If `gallery/HL3/lp/images/` is empty but `dots/` is full, the `dot` (graphviz) binary isn't on `PATH`. `convert_dot_to_png` at [src/topogen/common/circuit.py:697](src/topogen/common/circuit.py#L697) literally shells out:

```bash
which dot                       # if empty: sudo apt install graphviz
```

### Stepping through one variant

Insert `breakpoint()` inside the manager's `create…` or `connectInstanceTerminals…` helper and rerun the same script:

```python
# e.g. inside src/topogen/HL3/lp.py
def connectInstanceTerminalsOfTwoTransistorLoadPartDifferentSources(out, ts1, ts2):
    breakpoint()
    ...
```

### Inspecting a circuit from inside pdb

Every `Circuit` has a `.graphviz()` method ([src/topogen/common/circuit.py:116](src/topogen/common/circuit.py#L116)) that returns the DOT text — useful when you want to see the wiring of an intermediate object without rebuilding everything:

```text
(Pdb) print(some_loadpart.graphviz())
(Pdb) print(some_loadpart.connections)         # raw nets
(Pdb) [i.name for i in some_loadpart.instances]
```

---

## 4. Debugging OR-Tools CP-SAT solver issues

The sizing solver lives in [src/pyckt/sizing/solver.py](src/pyckt/sizing/solver.py).

### The two layers

- `CPSATAdapter` at [solver.py:65](src/pyckt/sizing/solver.py#L65) — wraps `cp_model.CpModel()` and stores the OR-Tools handles.
- `SizingSolver.solve()` at [solver.py:225](src/pyckt/sizing/solver.py#L225) — builds the model, calls `solver.Solve(...)` at [solver.py:241](src/pyckt/sizing/solver.py#L241), then formats the result.

### Where to set the breakpoint

```python
# src/pyckt/sizing/solver.py, around line 241
status = solver.Solve(self._adapter.model)
breakpoint()         # <-- inspect here
```

From inside pdb:

```text
(Pdb) status                                    # raw OR-Tools status int
(Pdb) self._status_to_text(self._adapter.cp_model, status)
'infeasible'
(Pdb) solver.NumBranches()
(Pdb) solver.WallTime()
(Pdb) solver.NumConflicts()
```

### Status decoding

`_status_to_text(cp_model, status)` at [solver.py:299](src/pyckt/sizing/solver.py#L299) maps the int to one of: `optimal`, `feasible`, `infeasible`, `model_invalid`, `unknown`. Anything else comes back as `status_<N>` — that means OR-Tools added a code we haven't taught the wrapper about; check the [`cp_model_pb2.CpSolverStatus`](https://github.com/google/or-tools/blob/stable/ortools/sat/cp_model.proto) values.

### Safe attribute access

`_safe_solver_stat(solver, name, default)` at [solver.py:289](src/pyckt/sizing/solver.py#L289) wraps `getattr` and swallows exceptions, so a missing stat doesn't crash the run. Useful directly inside pdb:

```text
(Pdb) SizingSolver._safe_solver_stat(solver, "NumBranches", 0)
(Pdb) SizingSolver._safe_solver_stat(solver, "ObjectiveValue", None)
(Pdb) SizingSolver._safe_solver_stat(solver, "SufficientAssumptionsForInfeasibility", None)
```

The third one is the OR-Tools API for getting a *minimal infeasible subset* — but only if you registered each constraint with `model.AddAssumption(literal)`. See the [CP-SAT assumptions docs](https://developers.google.com/optimization/cp/cp_solver#assumption).

### Reducing an infeasible run

When `--timeout` is long and you keep getting `infeasible`, the fastest path is bisection:

1. Shrink `--timeout` to a few seconds so each iteration is cheap.
2. Comment out groups of constraints inside `SizingProblem` (or whichever class wires them in).
3. Re-run; whichever group flips you to `feasible`/`optimal` contains the over-tight constraint.

---

## 5. A typical session, end-to-end

> Symptom: `pyckt automaticsizing` on the cascoded OTA reports `infeasible` after 5 s.

1. Add `breakpoint()` after [solver.py:241](src/pyckt/sizing/solver.py#L241).
2. Run the worked example from §2 with `--timeout 5`.
3. At the pdb prompt:
   ```text
   (Pdb) self._status_to_text(self._adapter.cp_model, status)
   'infeasible'
   (Pdb) len(self._adapter.model.Proto().constraints)
   (Pdb) for c in problem.constraints: print(type(c).__name__)
   ```
4. Re-run after commenting out a constraint group; repeat until `optimal`.

That's the loop. The same pattern (breakpoint → run the entry point of the failing scenario → inspect with pdb) covers every layer of the codebase.

---

## Reference

| What                                  | Where                                                                              |
|---------------------------------------|------------------------------------------------------------------------------------|
| CLI registry                          | [src/pyckt/cli.py:42](src/pyckt/cli.py#L42)                                        |
| CLI exception boundary                | [src/pyckt/cli.py:233](src/pyckt/cli.py#L233)                                      |
| Solver entry                          | [src/pyckt/sizing/solver.py:225](src/pyckt/sizing/solver.py#L225)                  |
| Status decoder                        | [src/pyckt/sizing/solver.py:299](src/pyckt/sizing/solver.py#L299)                  |
| `Circuit.graphviz()`                  | [src/topogen/common/circuit.py:116](src/topogen/common/circuit.py#L116)            |
| Canonical CLI flag set                | [tests/data/inputs/AutomaticSizing/command.sh](tests/data/inputs/AutomaticSizing/command.sh) |
| Logger setup                          | [src/pyckt/utils/loguru_loader.py](src/pyckt/utils/loguru_loader.py)               |
| Test bundles per mode                 | [tests/data/inputs/](tests/data/inputs/)                                           |
