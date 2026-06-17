# Comparing the C++ (`acst`) and Python (`pyckt`) implementations

This guide describes how to run the two implementations on identical inputs and diff their outputs. It is meant for someone validating that the Python port reproduces the C++ reference.

- C++ reference: `/home/jrad/acst/` — entry point `acst/build/bin/acst.sh`
- Python port: `/home/jrad/pyckt/pyckt/` — entry point `pyckt.cli` (`python -m pyckt.cli …`)
- Upstream docs: <https://deepwiki.com/phuocphn/analog-env/1-overview>

---

## 1. Architecture at a glance

Both implementations expose the **same five analyses** (`acst` adds `toplibgen`):

| Analysis        | Input                            | Output kind             |
|-----------------|----------------------------------|-------------------------|
| `structrec`     | HSpice netlist + library         | XML structure tree      |
| `rulegen`       | HSpice netlist + library         | XML sizing rules        |
| `partitioning`  | HSpice netlist + library         | XML gm/load/bias tree   |
| `automaticsizing` | netlist + tech + spec          | XML perf + sized devices |
| `synthesis`     | tech + spec (+ optional library) | directory of HSpice netlists |
| `toplibgen`     | (Python-only ckt+json bundles)   | directory of topologies |

The C++ chooses the analysis via `--analysis <name>`; Python uses an argparse subcommand. Same business logic, **different output schemas** — see §3.

---

## 2. CLI flag mapping

The two binaries take the *same* conceptual inputs under *different* flag names.

| Concept                    | C++ flag (`acst --analysis …`)      | Python flag (`pyckt …`)       |
|----------------------------|-------------------------------------|-------------------------------|
| Mode                       | `--analysis structrec` (etc.)       | subcommand `structrec` (etc.) |
| Input netlist              | `--circuit-netlist FILE`            | `--circuit FILE`              |
| Device types XCat          | `--device-types-file FILE`          | `--device-types FILE`         |
| HSpice mapping XCat        | `--hspice-mapping-file FILE`        | `--mapping FILE`              |
| Supply nets XCat           | `--hspice-supplynet-file FILE`      | `--supply-nets FILE`          |
| Structrec library          | `--xml-structrec-library-file FILE` | `--library FILE`              |
| Tech XML                   | `--xml-technologie-file FILE`       | `--tech-file FILE`            |
| Circuit specs XML          | `--xml-circuit-information-file FILE` | `--circuit-params FILE`     |
| Output file                | `--output-file FILE`                | `--output FILE`               |
| Output dir (synthesis)     | `--HSPICE-netlist-dir DIR`          | `--output-dir DIR`            |
| Solver runtime (sizing)    | `--runtime N`                       | `--timeout N`                 |
| Transistor model           | `--transistor-model SHM\|EKV`        | `--transistor-model SHM\|EKV`  |
| Geometric scaling          | `--scaling 0.1mum\|1mum`             | `--scaling 0.1mum\|1mum`       |
| Console log level          | `--log-level-console DEBUG\|TRACE\|OFF` | `--log-level-console DEBUG\|TRACE\|OFF` |

**Worked example** — `automaticsizing` on `cascodedSymmetricalCMOSOTA`, both runs from the same input bundle:

```bash
# C++
cd /home/jrad/acst/InputFileExamples/AutomaticSizing/cascodeSymmetricalOpAmp
/home/jrad/acst/build/bin/acst.sh --log-level-console OFF \
  --analysis automaticsizing \
  --circuit-netlist cascodedSymmetricalCMOSOTA.hspice \
  --device-types-file deviceTypes.xcat \
  --hspice-mapping-file HSpiceMapping.xcat \
  --hspice-supplynet-file supplyNets.xcat \
  --xml-structrec-library-file /home/jrad/acst/StructRec/xml/AnalogLibrary.xml \
  --xml-technologie-file TechnologyFile.xml \
  --xml-circuit-information-file CircuitParameterAndSpecifications.xml \
  --output-file /tmp/cpp.xml \
  --transistor-model SHM --scaling 0.1mum --runtime 5

# Python — same bundle, copied to the pyckt test data tree
cd /home/jrad/pyckt/pyckt/tests/data/inputs/AutomaticSizing
PYTHONPATH=/home/jrad/.venv/lib/python3.11/site-packages:/home/jrad/pyckt/pyckt/src \
  /usr/bin/python3.11 -m pyckt.cli --log-level-console OFF automaticsizing \
  --circuit cascodedSymmetricalCMOSOTA.hspice \
  --device-types deviceTypes.xcat \
  --mapping HSpiceMapping.xcat \
  --supply-nets supplyNets.xcat \
  --tech-file TechnologyFile.xml \
  --circuit-params CircuitParameterAndSpecifications.xml \
  --output /tmp/py.xml \
  --transistor-model SHM --scaling 0.1mum --timeout 5
```

---

## 3. Output schemas — why a textual `diff` is useless

The two writers produce **different element names, different units, and different attribute styles**. A naive `diff` shows noise on every line. Here is what you actually have to align.

### 3.1 Structure recognition

| C++ (`acst_results > structure_recognition_results`) | Python (`StructureRecognitionResult`) |
|---|---|
| `<acst_results>` root with `<date>` child | `<StructureRecognitionResult>` root, no date |
| `<structure_recognition_results>` wrapper | (no wrapper) |
| `<structure name="X[id]" techType="p" instance="/">` | `<Structure name="X" techType="p">` (no instance, no `[id]` in name) |
| `<pins><pin name="..." net="..."/></pins>` | `<Pins><Pin name="..." net="..."/></Pins>` (capital P) |
| `<devices><device name="..." deviceType="Mosfet" techType="p" instance="/"/></devices>` | `<Transistor name="..."/>` (sibling of `<Pins>`, no devices wrapper, no extra attrs) |
| Nested `<structure>` recursion | `<Children><Structure …>…</Structure><Structure …/></Children>` (Pair-typed structures only) |

**Examples** — see [`/home/jrad/acst/InputFileExamples/StructureRecognition/output.xml`](file:///home/jrad/acst/InputFileExamples/StructureRecognition/output.xml) (C++) and the Python writer at [`pyckt/src/recognition/writer.py`](src/recognition/writer.py).

### 3.2 Partitioning

| C++ (`circuit_partitioning_results`) | Python (`PartitioningResult`) |
|---|---|
| `<gmParts><gmPart type="firstStage" firstStageType="symmetrical">` | `<FirstStage><Transconductance>…</Transconductance><Load>…</Load><Bias>…</Bias></FirstStage>` |
| `<loadParts>` / `<biasParts>` flat lists | Roles nested under `FirstStage`/`SecondStage` |
| Reuses the same `<structure>`/`<pins>`/`<devices>` schema from §3.1 | Reuses Python `<Structure>`/`<Pins>` schema from §3.1 |

### 3.3 Automatic sizing

| C++ (`automatic_sizing-results`) | Python (`SizingResult`) |
|---|---|
| `<acst_results><date …/><automatic_sizing-results>` | `<SizingResult status iterations solve_time_seconds [objective_value]>` |
| `<ExpectedPerformance>` with units `m_W`, `(mu_m)^2`, `M_Hz`, `V/mum_s` | `<ExpectedPerformance>` with units `mW`, `um2`, `MHz`, `V/us` |
| Separate `<Voltages>`, `<Currents>`, `<Dimensions>` (with `<Transistors>` / `<Capacitors>`) | `<Devices>` containing `<Device>` per transistor with `<Width> <Length> <Current> <Vgs> <Vds> <Vov> <Gm> <Gds> <Area>` |
| Per-transistor `<Transistor name><Width unit="mu_m">…</Width><Length …></Transistor>` | Per-device `<Device name>` with explicit `unit="um"` |

### 3.4 Synthesis

Both write **HSpice netlists into a directory**, but file-naming differs:

- C++: `--HSPICE-netlist-dir <DIR>` ⇒ `<DIR>/<topology_name>.ckt` (and `OpAmpN.hspice` for the small library)
- Python: `--output-dir <DIR>` ⇒ format defined by `pyckt/src/pyckt/synthesis/converter.py` — verify against actual files after a run

The netlist body is mostly comparable (`.MACRO ... mDeviceName net1 net2 net3 net4 model L=… W=…`) but **device-name prefixes** and **net-name conventions** may diverge. Diff at the structural level (count + connectivity) rather than verbatim.

### 3.5 Units cheat-sheet

When normalising for comparison, apply these conversions (Python → C++ on the left):

| Quantity      | Python writes | C++ writes        | Convert        |
|---------------|---------------|-------------------|----------------|
| Power         | `mW`          | `m_W`             | identical magnitude — relabel only |
| Area          | `um2`         | `(mu_m)^2`        | identical — relabel |
| Frequency     | `MHz`         | `M_Hz`            | identical — relabel |
| Slew rate     | `V/us`        | `V/mum_s`         | identical — relabel |
| Length/width  | `um`          | `mu_m`            | identical — relabel |
| Current       | `nA`          | `mu_A` (Currents) | 1 mu_A = 1000 nA |
| Voltage       | `V`           | `V`               | same |

---

## 4. Strategy: normalise, then structurally diff

A useful comparison happens in three steps:

1. **Run both implementations on the same input bundle** with identical solver settings (`--runtime`/`--timeout`, `--transistor-model`, `--scaling`).
2. **Canonicalise each XML into a common intermediate** — a sorted dict keyed by stable identifiers (device name, structure name, pin name). Strip schema-specific wrappers (`acst_results`, `date`), normalise units to a single base, and ignore element-name casing.
3. **Diff the intermediates** with a numeric tolerance (CP-SAT and the C++ solver may pick equivalent-cost solutions whose individual W/L values differ slightly).

A first-pass comparator (drop into `scripts/compare_outputs.py`):

```python
"""Compare C++ ACST and Python pyckt outputs for the same input bundle.

Run from project root:
    python scripts/compare_outputs.py automaticsizing /tmp/cpp.xml /tmp/py.xml
"""
import sys, xml.etree.ElementTree as ET
from collections import OrderedDict

def _scale_to_base(text: str, unit: str) -> float:
    """Map any (value, unit) to a single base unit (V, A, m, W, Hz, s, m^2)."""
    v = float(text)
    scale = {
        "m_W": 1e-3, "mW": 1e-3,
        "(mu_m)^2": 1e-12, "um2": 1e-12,
        "M_Hz": 1e6, "MHz": 1e6,
        "V/mum_s": 1e6, "V/us": 1e6,
        "mu_m": 1e-6, "um": 1e-6,
        "mu_A": 1e-6, "nA": 1e-9, "nA/V": 1e-9,
        "mV": 1e-3, "V": 1.0,
        "dB": 1.0, "degree": 1.0, "deg": 1.0,
    }.get(unit, 1.0)
    return v * scale

def load_sizing(path: str) -> dict:
    """Flatten either schema to {device_name: {width, length, ...},
    'perf': {...}, 'voltages': {...}, 'currents': {...}}."""
    root = ET.parse(path).getroot()
    out: dict = {"devices": OrderedDict(), "perf": {}, "voltages": {}, "currents": {}}

    if root.tag == "acst_results":                      # C++
        body = root.find("automatic_sizing-results")
        perf = body.find("ExpectedPerformance")
        if perf is not None:
            for child in perf:
                out["perf"][child.tag] = _scale_to_base(child.text, child.get("unit", ""))
        v = body.find("Voltages")
        if v is not None:
            for n in v.findall("Net"):
                out["voltages"][n.get("name").lstrip("/")] = float(n.text)
        c = body.find("Currents")
        if c is not None:
            unit = c.get("unit", "")
            for comp in c.findall("Component"):
                out["currents"][comp.get("name").lstrip("/")] = _scale_to_base(comp.text, unit)
        for t in body.iterfind("Dimensions/Transistors/Transistor"):
            name = t.get("name").lstrip("/")
            out["devices"][name] = {
                "width":  _scale_to_base(t.find("Width").text,  t.find("Width").get("unit", "")),
                "length": _scale_to_base(t.find("Length").text, t.find("Length").get("unit", "")),
            }
    elif root.tag == "SizingResult":                    # Python
        perf = root.find("ExpectedPerformance")
        if perf is not None:
            mapping = {  # match C++ tag names where they differ
                "TotalArea": "Area", "TransitFrequency": "TransitFrequency",
                "Power": "Power", "Gain": "Gain", "SlewRate": "SlewRate",
                "PhaseMargin": "PhaseMargin",
            }
            for child in perf:
                key = mapping.get(child.tag, child.tag)
                out["perf"][key] = _scale_to_base(child.text, child.get("unit", ""))
        for d in root.iterfind("Devices/Device"):
            name = d.get("name").lstrip("/")
            out["devices"][name] = {
                "width":  _scale_to_base(d.find("Width").text,  d.find("Width").get("unit", "um")),
                "length": _scale_to_base(d.find("Length").text, d.find("Length").get("unit", "um")),
            }
            cur = d.find("Current")
            if cur is not None:
                out["currents"][name] = _scale_to_base(cur.text, cur.get("unit", "nA"))
    else:
        raise SystemExit(f"unknown root <{root.tag}> in {path}")
    return out

def diff(cpp: dict, py: dict, rel_tol: float = 0.05) -> int:
    """Print mismatches; return non-zero if any field exceeds rel_tol."""
    bad = 0
    for section in ("perf", "voltages", "currents"):
        keys = sorted(set(cpp[section]) | set(py[section]))
        for k in keys:
            a, b = cpp[section].get(k), py[section].get(k)
            if a is None or b is None:
                print(f"{section}.{k}: only in {'cpp' if b is None else 'py'} ({a or b})"); bad += 1; continue
            denom = max(abs(a), abs(b), 1e-30)
            if abs(a - b) / denom > rel_tol:
                print(f"{section}.{k}: cpp={a:.4g} py={b:.4g}  (Δ={abs(a-b)/denom:.1%})"); bad += 1

    common = sorted(set(cpp["devices"]) & set(py["devices"]))
    only_cpp = sorted(set(cpp["devices"]) - set(py["devices"]))
    only_py  = sorted(set(py["devices"]) - set(cpp["devices"]))
    for n in only_cpp: print(f"device {n}: only in cpp"); bad += 1
    for n in only_py:  print(f"device {n}: only in py");  bad += 1
    for n in common:
        for prop in ("width", "length"):
            a, b = cpp["devices"][n][prop], py["devices"][n][prop]
            denom = max(abs(a), abs(b), 1e-30)
            if abs(a - b) / denom > rel_tol:
                print(f"device {n}.{prop}: cpp={a:.4g} py={b:.4g}  (Δ={abs(a-b)/denom:.1%})"); bad += 1
    return bad

if __name__ == "__main__":
    mode, cpp_xml, py_xml = sys.argv[1], sys.argv[2], sys.argv[3]
    if mode != "automaticsizing":
        raise SystemExit("Only automaticsizing comparator implemented; extend for structrec/partitioning")
    cpp = load_sizing(cpp_xml)
    py  = load_sizing(py_xml)
    code = diff(cpp, py)
    sys.exit(0 if code == 0 else 1)
```

Usage:

```bash
python scripts/compare_outputs.py automaticsizing /tmp/cpp.xml /tmp/py.xml
```

Exit code is 0 when every field matches within 5 %; non-zero otherwise with one line per mismatch.

### Extending the comparator

- **structrec** → flatten both schemas to a sorted set of `(structure_name, tech_type, frozenset(pin→net), frozenset(device_names))` tuples; compare set equality. The trailing `[id]` in C++ structure names is allocator-dependent — strip it before comparing.
- **partitioning** → flatten both schemas to `{role: [structures]}` grouped by `(stage, role)`. Compare role membership; do not assume identical ordering inside a role.
- **synthesis** → iterate the two output directories. For each filename, parse the HSpice into a graph (devices + nets), then compare graphs canonically with `networkx.is_isomorphic`. Tolerate net-name renaming via a graph-isomorphism approach.

---

## 5. End-to-end recipe per analysis

For each analysis, pick a bundle from one of the test-data trees and run both implementations against it. Bundles available out of the box:

| Analysis        | C++ bundle root                                          | Python bundle root                                                |
|-----------------|----------------------------------------------------------|-------------------------------------------------------------------|
| structrec       | `/home/jrad/acst/InputFileExamples/StructureRecognition` | `/home/jrad/pyckt/pyckt/tests/data/inputs/StructureRecognition`   |
| rulegen         | `/home/jrad/acst/InputFileExamples/RuleGeneration`       | `/home/jrad/pyckt/pyckt/tests/data/inputs/RuleGeneration`         |
| partitioning    | `/home/jrad/acst/InputFileExamples/Partitioning`         | `/home/jrad/pyckt/pyckt/tests/data/inputs/Partitioning`           |
| automaticsizing | `/home/jrad/acst/InputFileExamples/AutomaticSizing/...`  | `/home/jrad/pyckt/pyckt/tests/data/inputs/AutomaticSizing`        |
| synthesis       | `/home/jrad/acst/InputFileExamples/Synthesis`            | `/home/jrad/pyckt/pyckt/tests/data/inputs/Synthesis`              |

`tests/data/inputs/AutomaticSizing/cascodedSymmetricalCMOSOTA.hspice` in the Python tree is a copy of the C++ bundle — same content, so both runs operate on **bit-identical** inputs.

### Driver script

```bash
#!/usr/bin/env bash
# scripts/run_both.sh — run both implementations on the canonical sizing bundle.
set -e
TMP=${TMP:-/tmp/pyckt-diff}
mkdir -p "$TMP"

BUNDLE_CPP=/home/jrad/acst/InputFileExamples/AutomaticSizing/cascodeSymmetricalOpAmp
BUNDLE_PY=/home/jrad/pyckt/pyckt/tests/data/inputs/AutomaticSizing

( cd "$BUNDLE_CPP" && /home/jrad/acst/build/bin/acst.sh --log-level-console OFF \
    --analysis automaticsizing \
    --circuit-netlist cascodedSymmetricalCMOSOTA.hspice \
    --device-types-file deviceTypes.xcat \
    --hspice-mapping-file HSpiceMapping.xcat \
    --hspice-supplynet-file supplyNets.xcat \
    --xml-structrec-library-file /home/jrad/acst/StructRec/xml/AnalogLibrary.xml \
    --xml-technologie-file TechnologyFile.xml \
    --xml-circuit-information-file CircuitParameterAndSpecifications.xml \
    --output-file "$TMP/cpp.xml" \
    --transistor-model SHM --scaling 0.1mum --runtime 5 )

( cd "$BUNDLE_PY" && PYTHONPATH=/home/jrad/.venv/lib/python3.11/site-packages:/home/jrad/pyckt/pyckt/src \
    /usr/bin/python3.11 -m pyckt.cli --log-level-console OFF automaticsizing \
    --circuit cascodedSymmetricalCMOSOTA.hspice \
    --device-types deviceTypes.xcat \
    --mapping HSpiceMapping.xcat \
    --supply-nets supplyNets.xcat \
    --tech-file TechnologyFile.xml \
    --circuit-params CircuitParameterAndSpecifications.xml \
    --output "$TMP/py.xml" \
    --transistor-model SHM --scaling 0.1mum --timeout 5 )

python /home/jrad/pyckt/pyckt/scripts/compare_outputs.py automaticsizing "$TMP/cpp.xml" "$TMP/py.xml"
```

---

## 6. Known sources of false positives

When the comparator flags a difference, check these before assuming a bug:

- **Solver non-determinism.** CP-SAT and the C++ solver may converge to equivalent-cost W/L tuples. Increase the relative tolerance, or pin device dimensions and compare only performance.
- **Random net names.** Both implementations may rename internal nets (`n3`, `net29`, …). Connectivity, not the literal names, is the invariant.
- **Structure-instance IDs in C++.** The `[N]` suffix in `<structure name="MosfetCascodePair[5]">` is an allocator counter — strip it before set comparison.
- **Floating-point formatting.** C++ writes `6.11801`; Python may write `6.118010`. The numeric comparator handles this; a textual diff will not.
- **Date stamps in C++.** The `<date day month year hour minute second/>` element changes every run — strip it during canonicalisation.

---

## 7. Reference

| File                                                                            | What it gives you                              |
|---------------------------------------------------------------------------------|------------------------------------------------|
| `/home/jrad/acst/build/bin/acst.sh`                                             | C++ entry point wrapper                        |
| `/home/jrad/acst/InputFileExamples/<analysis>/command.sh`                       | Canonical C++ invocation per analysis          |
| `/home/jrad/pyckt/pyckt/src/pyckt/cli.py`                                       | Python CLI parser + dispatch                   |
| `/home/jrad/pyckt/pyckt/src/pyckt/sizing/writer.py`                             | Python sizing XML writer                       |
| `/home/jrad/pyckt/pyckt/src/recognition/writer.py`                              | Python structrec XML writer                    |
| `/home/jrad/pyckt/pyckt/src/partitioning/writer.py`                             | Python partitioning XML writer                 |
| `/home/jrad/acst/InputFileExamples/AutomaticSizing/.../cascodedSymmetricalCMOSOTA.xml` | C++ reference sizing output            |
| `/home/jrad/pyckt/pyckt/tests/data/inputs/<analysis>/`                          | Python bundles (copies of C++ examples)        |
