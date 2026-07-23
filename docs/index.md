# pyckt

Python re-implementation of [ACST](https://github.com/inga000/acst/) (Analog
Circuit Synthesis Tool, TU München). pyckt provides six end-to-end analyses for
analog op-amp design, available from both the command line and a typed Python
API.

| Mode | CLI | Python API |
|------|-----|------------|
| Structure recognition | `pyckt structrec` | {func}`pyckt.recognize` |
| Sizing-rule generation | `pyckt rulegen` | {func}`pyckt.generate_rules` |
| Partitioning | `pyckt partitioning` | {func}`pyckt.partition` |
| Automatic sizing | `pyckt automaticsizing` | {func}`pyckt.size` |
| Topology synthesis | `pyckt synthesis` | {func}`pyckt.synthesize` |
| Topology library generation | `pyckt toplibgen` | {func}`pyckt.generate_topology_library` |

## Quick start (Python API)

```python
import pyckt

# 1. Recognise the analog structures in a netlist
structures = pyckt.recognize(
    circuit="circuit.hspice",
    device_types="deviceTypes.xcat",
    mapping="HSpiceMapping.xcat",
    supply_nets="supplyNets.xcat",
)
print(structures.total_structures)

# 2. Size every transistor (and write the sized netlist)
result = pyckt.size(
    circuit="circuit.hspice",
    device_types="deviceTypes.xcat",
    mapping="HSpiceMapping.xcat",
    supply_nets="supplyNets.xcat",
    tech_file="TechnologyFile.xml",
    circuit_params="CircuitParameterAndSpecifications.xml",
    timeout=60,
    output="sized.xml",
)
print(result.performance.gain_db)
```

Every API function takes file paths (`str` or `pathlib.Path`) plus keyword
options and returns the mode's typed result object. Writing output to disk is
optional — pass `output=...` (or `output_dir=...`) to also serialise.

## Building these docs

```bash
pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

```{toctree}
:maxdepth: 2
:caption: Contents

api/index
```
