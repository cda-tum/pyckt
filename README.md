# pyckt — Analog Circuit Synthesis Tool (Python)

Python re-implementation of [ACST](https://github.com/inga000/acst/)
(TU München).  Six end-to-end analyses for analog op-amp design:

| Mode               | Subcommand          | Pipeline                                                   |
|--------------------|---------------------|------------------------------------------------------------|
| Structure recognition | `pyckt structrec`   | parse → recognise → write XML                              |
| Sizing-rule generation| `pyckt rulegen`     | parse → recognise → derive rules → write XML               |
| Partitioning          | `pyckt partitioning`| parse → recognise → 12-step classify → write XML           |
| Automatic sizing      | `pyckt automaticsizing` | full pipeline → CP-SAT solver → write sized HSpice + XML |
| Topology synthesis    | `pyckt synthesis`   | filter library → size each → rank → write summary          |
| Topology library generation | `pyckt toplibgen` | enumerate ~7000 op-amp topologies → write `.ckt`/`.json` per topology |

## Installation

```bash
git clone https://github.com/<your-org>/pyckt.git
cd pyckt
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"   # `[dev]` adds pytest, pytest-cov, ruff, mypy, build
```

Requires Python ≥ 3.11 (uses PEP 604 union syntax in module-level
type hints).  Core dependencies: `loguru`, `ortools` ≥ 9.8.

## Quick start

All examples reference the bundled fixtures under
`tests/data/inputs/{Mode}/` (a 284 KB self-contained subset of
`acst/InputFileExamples/`).

### Structure recognition

```bash
pyckt structrec \
    --circuit       tests/data/inputs/Partitioning/cascodedSymmetricalCMOSOTA.hspice \
    --device-types  tests/data/inputs/Partitioning/deviceTypes.xcat \
    --mapping       tests/data/inputs/Partitioning/HSpiceMapping.xcat \
    --supply-nets   tests/data/inputs/Partitioning/supplyNets.xcat \
    --output        result.xml
```

### Automatic sizing

```bash
pyckt automaticsizing \
    --circuit         tests/data/inputs/AutomaticSizing/cascodedSymmetricalCMOSOTA.hspice \
    --device-types    tests/data/inputs/AutomaticSizing/deviceTypes.xcat \
    --mapping         tests/data/inputs/AutomaticSizing/HSpiceMapping.xcat \
    --supply-nets     tests/data/inputs/AutomaticSizing/supplyNets.xcat \
    --tech-file       tests/data/inputs/AutomaticSizing/TechnologyFile.xml \
    --circuit-params  tests/data/inputs/AutomaticSizing/CircuitParameterAndSpecifications.xml \
    --output          sized.xml \
    --timeout         60
```

### Topology library generation

```bash
pyckt toplibgen --output-dir ./topology_library
# → ./topology_library/{one,two}_stage_{single_output,fully_differential}/topology_NNNN.{ckt,json}
```

For complete per-mode help, run `pyckt <mode> --help`.

## Python API

Every mode is also a typed function under the top-level `pyckt` package, so
notebooks and pipelines can run analyses in-process — no subprocess, no `argv`:

```python
import pyckt

overlay = pyckt.recognize(
    circuit="circuit.hspice",
    device_types="deviceTypes.xcat",
    mapping="HSpiceMapping.xcat",
    supply_nets="supplyNets.xcat",
)                                          # → StructureCircuits

result = pyckt.size(..., tech_file="TechnologyFile.xml",
                    circuit_params="...xml", timeout=60, output="sized.xml")
print(result.performance.gain_db)
```

Each function (`recognize`, `generate_rules`, `partition`, `size`,
`synthesize`, `generate_topology_library`) takes `str`/`Path` paths plus
keyword options and returns the mode's typed result object; writing to disk is
optional (pass `output=` / `output_dir=`).  See `pyckt.api` for the full
signatures, or build the Sphinx docs (below).

A lower-level argv dispatcher, `cli.run([...])`, is also available for tests
that want to drive the CLI in-process.

## Project layout

The user-facing API lives in the `pyckt` package; the analysis engines are
sibling top-level packages (so `recognition`, `partitioning`, `core`, … all
import unprefixed).  `ckt_io` is the netlist/XML IO package — it is **not**
named `io`, to avoid shadowing the standard-library `io` module.

```
pyckt/
├── src/
│   ├── pyckt/                Public Python API (facade)
│   │   ├── __init__.py       Re-exports recognize / partition / size / …
│   │   └── api.py            Typed per-mode entry points
│   ├── cli.py                Subcommand dispatcher (`pyckt <mode>`)
│   ├── core/                 Flat circuit + device + net data model
│   ├── ckt_io/               HSpice + XML parsers and writers
│   ├── sizing/               CP-SAT sizing solver
│   ├── synthesis/            Topology library + synthesis search
│   ├── topogen/              Topology generation (HL2–HL5 factories)
│   ├── recognition/          Structure recognition + rule generation
│   ├── partitioning/         Functional classification of structures
│   └── data/structrec/       Bundled XML pattern libraries (ships in wheel)
├── docs/                     Sphinx documentation (build: see below)
├── scripts/                  Per-mode standalone run scripts
└── tests/                    pytest suite
```

## Documentation

```bash
pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

## Testing

```bash
pytest                 # full suite (~140 s)
pytest -m "not slow"   # fast subset (~3 s) — skips full library gen
pytest -m slow         # slow tests only (library gen + sizing)
pytest --cov=src       # coverage report (currently 96%)
```

The bundled fixtures under `tests/data/inputs/` make the suite
self-contained — no host paths required.

## Continuous integration

No CI workflow is checked in yet. The repo is set up to run cleanly
under any standard Python CI: each tool below already has its config
in `pyproject.toml` (ruff, pytest+cov, mypy), so a CI job only needs to
shell out to the three commands.

The recommended local-equivalent invocations:

```bash
ruff check src/                            # lint (must be clean)
pytest --cov=src --cov-fail-under=80       # tests + coverage gate (80%)
mypy src/pyckt/                            # type check (non-blocking)
```

## Documentation

* `planning/00-overview.md` — top-level architecture
* `planning/01-week1-core-cli.md` … `planning/09-week9-integration.md`
  — per-week detailed design
* `planning/week*_progress.md` — implementation log for each week

## Acknowledgements

Inspired by the original C++ implementation:

* [acst — Analog Circuit Synthesis Tool](https://github.com/inga000/acst/)
* Inga Abel & Helmut Graeb. "FUBOCO: Structure synthesis of basic
  op-amps by FUnctional BlOck COmposition." *ACM Transactions on Design
  Automation of Electronic Systems* (TODAES) 27.6 (2022): 1-27.

## License

MIT. See [LICENSE](LICENSE) for details.
