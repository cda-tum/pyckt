#!/usr/bin/env python3
"""Compare pyckt output against the FUBOCO Gallery reference (issue #7).

The gallery (https://github.com/analog-ml/fuboco-gallery) ships, per circuit,
the acst-generated artefacts of the *labeled* topology-library flow:

* ``netlist.ckt``           — the topology netlist,
* ``subcircuits.xml``       — acst structure recognition on that netlist,
* ``functional_blocks.xml`` — acst partitioning on that netlist.

For every circuit of a category (``s-1-2``, ``fd-1-2``) this script parses the
gallery netlist with pyckt, runs pyckt's structure recognition and
partitioning in acst output format, and compares the XML against the gallery
reference **semantically**: structure ordinals (``[N]``), element order,
whitespace and the ``<date>`` header are normalised away; names, tech types,
pin→net assignments, device sets, nesting, and part classifications must all
match.

Usage
-----
    .venv/bin/python scripts/compare_fuboco_gallery.py \
        --gallery /path/to/fuboco-gallery [--category s-1-2 fd-1-2] \
        [--limit N] [--report report/reports/FUBOCO_GALLERY_REPORT.md]
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

_ORDINAL = re.compile(r"\[\d+\]")

# acst's labeled outputs rename the generated netlists' rails
_RAIL_ALIASES = {"/sourceNmos": "/gnd!", "/sourcePmos": "/vdd!"}


def _net(name: str) -> str:
    return _RAIL_ALIASES.get(name, name)


# ── canonicalisation ───────────────────────────────────────────────────────


def _canon_structure(el: ET.Element):
    """Canonical, ordinal-free form of a ``<structure>`` element tree."""
    name = _ORDINAL.sub("", el.get("name", ""))
    pins = tuple(sorted(
        (p.get("name", ""), _net(p.get("net", "")))
        for pins in el.findall("pins") for p in pins.findall("pin")
    ))
    devices = tuple(sorted(
        d.get("name", "")
        for devs in el.findall("devices") for d in devs.findall("device")
    ))
    children = tuple(sorted(
        _canon_structure(c) for c in el.findall("structure")
    ))
    return (name, el.get("techType", ""), pins, devices, children)


def canon_structrec(xml_path_or_root) -> Counter:
    """Multiset of canonical top-level structures of a structrec result."""
    root = _root_of(xml_path_or_root)
    results = root.find("structure_recognition_results")
    if results is None:
        raise ValueError("no <structure_recognition_results>")
    return Counter(_canon_structure(s) for s in results.findall("structure"))


def canon_partitioning(xml_path_or_root) -> Counter:
    """Multiset of canonical parts of a partitioning result.

    Each part is ``(container tag, part tag, sorted attrs, structures)`` so a
    gm part typed ``firstStage`` with a given structure tree must match
    exactly, wherever it appears in the file.
    """
    root = _root_of(xml_path_or_root)
    results = root.find("circuit_partitioning_results")
    if results is None:
        raise ValueError("no <circuit_partitioning_results>")
    parts: Counter = Counter()
    for container in results:
        for part in container:
            attrs = tuple(sorted(part.attrib.items()))
            structures = tuple(sorted(
                _canon_structure(s) for s in part.findall("structure")
            ))
            parts[(container.tag, part.tag, attrs, structures)] += 1
    return parts


def _root_of(xml_path_or_root) -> ET.Element:
    if isinstance(xml_path_or_root, ET.Element):
        return xml_path_or_root
    return ET.parse(str(xml_path_or_root)).getroot()


def diff_counters(ref: Counter, got: Counter) -> list[str]:
    """Human-readable one-liners for every multiset difference."""
    out = []
    for key in (ref - got):
        out.append(f"missing (in gallery, not pyckt): {_describe(key)}")
    for key in (got - ref):
        out.append(f"extra (in pyckt, not gallery): {_describe(key)}")
    return out


def _describe(key) -> str:
    if len(key) == 5:  # structure
        name, tech, pins, devices, _ = key
        return f"structure {name} [{tech}] devices={list(devices)} pins={dict(pins)}"
    container, tag, attrs, structures = key
    names = [s[0] for s in structures]
    return f"{container}/{tag} {dict(attrs)} structures={names}"


# ── pyckt pipeline on a gallery netlist ────────────────────────────────────


def _make_parser():
    from ckt_io.device_types_parser import load_device_types
    from ckt_io.hspice_mapping import HSpiceMapping
    from ckt_io.hspice_parser import HSpiceParser
    from ckt_io.supply_nets_parser import SupplyNetConfig

    cfg = REPO / "tests" / "data" / "inputs" / "Partitioning"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".xcat", delete=False
    ) as supply:
        # the generated netlists' rails
        supply.write('GND_1 "sourceNmos"\nVDD_1 "sourcePmos"\n')
        supply_path = supply.name
    return HSpiceParser(
        HSpiceMapping.from_file(str(cfg / "HSpiceMapping.xcat")),
        SupplyNetConfig.from_file(supply_path),
        load_device_types(str(cfg / "deviceTypes.xcat")),
    )


def compare_circuit(circuit_dir: Path, parser, library) -> dict:
    """Run pyckt on one gallery circuit; return per-artefact diff lists."""
    from partitioning.acst_partitioner import AcstPartitioner
    from partitioning.net_inference import infer_circuit_parameters
    from partitioning.writer import AcstPartitionXMLWriter
    from recognition.recognizer import StructureRecognizer
    from recognition.writer import AcstStructRecXMLWriter

    result = {"structrec": None, "partitioning": None}

    circuit = parser.parse(str(circuit_dir / "netlist.ckt"))
    sc = StructureRecognizer(library).recognize(circuit)

    with tempfile.TemporaryDirectory() as tmp:
        sr_path = Path(tmp) / "sr.xml"
        AcstStructRecXMLWriter().write(sc, sr_path)
        result["structrec"] = diff_counters(
            canon_structrec(circuit_dir / "subcircuits.xml"),
            canon_structrec(sr_path),
        )

        params = infer_circuit_parameters(circuit)
        part_path = Path(tmp) / "part.xml"
        AcstPartitionXMLWriter(AcstPartitioner(params).partition(sc)).write(
            part_path
        )
        result["partitioning"] = diff_counters(
            canon_partitioning(circuit_dir / "functional_blocks.xml"),
            canon_partitioning(part_path),
        )
    return result


# ── driver ─────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gallery", required=True, type=Path,
                    help="path to a fuboco-gallery checkout")
    ap.add_argument("--category", nargs="+", default=["s-1-2", "fd-1-2"])
    ap.add_argument("--limit", type=int, default=None,
                    help="only the first N circuits per category")
    ap.add_argument("--report", type=Path, default=None,
                    help="write a markdown report here")
    args = ap.parse_args()

    import logging

    import loguru
    loguru.logger.remove()
    logging.disable(logging.CRITICAL)

    from recognition.library import Library

    parser = _make_parser()
    library = Library.from_directory(None)

    lines = ["# FUBOCO Gallery comparison — pyckt vs reference", ""]
    exit_code = 0
    for cat in args.category:
        raw = args.gallery / "circuits" / cat / "raw"
        dirs = sorted(
            (d for d in raw.iterdir() if d.is_dir()),
            key=lambda d: [int(t) for t in d.name.split("_")],
        )
        if args.limit:
            dirs = dirs[: args.limit]

        ok = {"structrec": 0, "partitioning": 0}
        failures: list[tuple[str, str, list[str]]] = []
        errors: list[tuple[str, str]] = []
        # aggregate recurring diff shapes: net names vary per circuit, so
        # bucket on the structural fingerprint (everything before "pins=")
        patterns: Counter = Counter()
        pattern_examples: dict = {}
        for d in dirs:
            try:
                res = compare_circuit(d, parser, library)
            except Exception as exc:  # noqa: BLE001 — record and continue
                errors.append((d.name, f"{type(exc).__name__}: {exc}"))
                continue
            for kind, diffs in res.items():
                if diffs:
                    failures.append((d.name, kind, diffs))
                    for line in diffs:
                        pat = (kind, line.split(" pins=")[0])
                        patterns[pat] += 1
                        pattern_examples.setdefault(pat, d.name)
                else:
                    ok[kind] += 1

        total = len(dirs)
        print(f"[{cat}] circuits={total} "
              f"structrec OK={ok['structrec']} "
              f"partitioning OK={ok['partitioning']} "
              f"diffs={len(failures)} errors={len(errors)}")
        lines += [
            f"## `{cat}` — {total} circuits",
            "",
            "| artefact | identical | differing |",
            "|---|---:|---:|",
            f"| structure recognition (`subcircuits.xml`) | "
            f"{ok['structrec']} | {total - ok['structrec'] - len(errors)} |",
            f"| partitioning (`functional_blocks.xml`) | "
            f"{ok['partitioning']} | {total - ok['partitioning'] - len(errors)} |",
            "",
        ]
        if errors:
            exit_code = 1
            lines += [f"**errors ({len(errors)}):**", ""]
            lines += [f"- `{n}`: {msg}" for n, msg in errors[:20]] + [""]
        if patterns:
            exit_code = 1
            lines += [
                "**recurring diff patterns** "
                "(occurrences across all circuits; net names elided):", "",
                "| n | artefact | pattern | example circuit |",
                "|---:|---|---|---|",
            ]
            for (kind, pat), n in patterns.most_common(40):
                lines.append(
                    f"| {n} | {kind} | `{pat}` | `{pattern_examples[(kind, pat)]}` |"
                )
            lines.append("")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(lines) + "\n")
        print(f"report → {args.report}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
