#!/usr/bin/env python3
"""acst (C++) vs pyckt (Python) — comparison of the **acst-format** outputs.

Since the first report, pyckt grew an acst-compatible writer (``--output-format
acst``-style), so for every mode we now have, side by side in the *same schema*:

    outputs/<mode>/cpp/cpp.xml          (acst, reference)
    outputs/<mode>/py/py_acst.xml       (pyckt in acst format)
    outputs/rulegen/py_acst/...         (pyckt pairLibrary + Items/)

This script diffs cpp vs py_acst per mode and reports the comparable facts:
device geometry / currents / performance (sizing), device->structure
assignment + hierarchy (structrec), device->section assignment (partitioning),
and library hierarchy (rulegen). Run: ``python3 compare_acst.py``.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"


def strip(name: str) -> str:
    return (name or "").lstrip("/")


def base(name: str) -> str:
    """'MosfetDiodeArray[5]' -> 'MosfetDiodeArray'."""
    return (name or "").split("[", 1)[0]


def section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def pct(a: float | None, b: float | None) -> str:
    if a is None or b is None:
        return "—"
    if a == 0:
        return "0" if b == 0 else "inf"
    return f"{abs(a - b) / abs(a) * 100:.1f}"


# --------------------------------------------------------------------------
# automaticsizing — both sides are <acst_results>/<automatic_sizing-results>
# --------------------------------------------------------------------------

CUR_FACTOR = {"mu_A": 1000.0, "nA": 1.0}  # -> nA


def sizing_facts(path: Path) -> dict:
    asr = ET.parse(path).getroot().find("automatic_sizing-results")
    dev: dict[str, dict] = {}
    for tr in asr.findall("./Dimensions/Transistors/Transistor"):
        n = strip(tr.get("name", ""))
        w, ln = tr.find("Width"), tr.find("Length")
        dev.setdefault(n, {})["W"] = float(w.text) if w is not None else None
        dev[n]["L"] = float(ln.text) if ln is not None else None
    cur = asr.find("Currents")
    if cur is not None:
        f = CUR_FACTOR.get(cur.get("unit", "nA"), 1.0)
        for c in cur.findall("Component"):
            dev.setdefault(strip(c.get("name", "")), {})["I"] = abs(float(c.text)) * f
    perf = {}
    pe = asr.find("ExpectedPerformance")
    for el in (pe if pe is not None else []):
        try:
            perf[el.tag] = float(el.text)
        except (TypeError, ValueError):
            pass
    sections = [e.tag for e in asr]
    return {"dev": dev, "perf": perf, "sections": sections}


# --------------------------------------------------------------------------
# structrec / partitioning — recursive structure walk
# --------------------------------------------------------------------------

def walk_leaves(struct, top_base, out):
    """Map each leaf device -> base name of the TOP-LEVEL structure & its own."""
    own = base(struct.get("name", ""))
    dc = struct.find("devices")
    if dc is not None:
        for d in dc.findall("device"):
            out[strip(d.get("name", ""))] = {"top": top_base, "leaf": own}
    for child in struct.findall("structure"):
        walk_leaves(child, top_base, out)


def structrec_facts(path: Path) -> dict:
    root = ET.parse(path).getroot().find("structure_recognition_results")
    dev: dict[str, dict] = {}
    top_types: Counter = Counter()
    all_types: Counter = Counter()
    for s in root.findall("structure"):
        top_types[base(s.get("name", ""))] += 1
        walk_leaves(s, base(s.get("name", "")), dev)
    for s in root.iter("structure"):
        all_types[base(s.get("name", ""))] += 1
    return {"dev": dev, "top_types": top_types, "all_types": all_types}


def partitioning_facts(path: Path) -> dict:
    root = ET.parse(path).getroot().find("circuit_partitioning_results")
    dev: dict[str, str] = {}
    sec_counts: Counter = Counter()
    # gmParts have a typed sub-bucket; everything else uses its container tag.
    for gm in root.findall("./gmParts/gmPart"):
        sec = f"gm:{gm.get('type', '?')}"
        for d in gm.iter("device"):
            dev[strip(d.get("name", ""))] = sec
    for container in ("loadParts", "biasParts", "capacitances",
                      "resistorParts", "commonModeSignalDetectorParts",
                      "positiveFeedbackParts", "undefinedParts"):
        cel = root.find(container)
        if cel is None:
            continue
        for d in cel.iter("device"):
            dev[strip(d.get("name", ""))] = container
    for sec in dev.values():
        sec_counts[sec] += 1
    return {"dev": dev, "sec_counts": sec_counts}


# --------------------------------------------------------------------------
# rulegen — pairLibrary hierarchy
# --------------------------------------------------------------------------

def rulegen_facts(path: Path) -> dict:
    root = ET.parse(path).getroot()
    items = [e.text for e in root.iter("pairLibraryItem")]
    levels: dict[str, str] = {}
    pers: dict[str, str] = {}
    for lvl in root.iter("hierarchyLevel"):
        for it in lvl.findall("pairLibraryItem"):
            levels[it.text] = lvl.get("level")
            pers[it.text] = it.get("persistence", "—")
    return {"n_items": len(items), "levels": levels, "pers": pers}


# --------------------------------------------------------------------------

def cmp_assignment(cpp: dict, py: dict, key: str, label: str) -> None:
    common = sorted(set(cpp) & set(py), key=lambda n: (len(n), n))
    agree = sum(1 for d in common if cpp[d] == py[d])
    print(f"  devices in cpp: {len(cpp)}   in py: {len(py)}   "
          f"in both: {len(common)}")
    print(f"  SAME {label}: {agree}/{len(common)}")
    mism = [(d, cpp[d], py[d]) for d in common if cpp[d] != py[d]]
    if mism:
        print(f"  mismatches (device, cpp, py):")
        for d, c, p in mism:
            print(f"      {d:5s} {c}  vs  {p}")


def main() -> int:
    # ---- automaticsizing ----
    section("AUTOMATICSIZING  (cpp.xml  vs  py_acst.xml)")
    c = sizing_facts(OUT / "automaticsizing/cpp/cpp.xml")
    p = sizing_facts(OUT / "automaticsizing/py/py_acst.xml")
    print(f"  cpp sections: {c['sections']}")
    print(f"  py  sections: {p['sections']}")
    print(f"\n  Performance (cpp -> py, Δ% vs cpp):")
    allk = list(dict.fromkeys(list(c["perf"]) + list(p["perf"])))
    for k in allk:
        cv, pv = c["perf"].get(k), p["perf"].get(k)
        print(f"    {k:38s} {str(cv):>10} -> {str(pv):>10}   Δ {pct(cv, pv)}%")
    print(f"\n  Per-transistor W/L/|I|  (Δ% vs cpp):")
    print(f"    {'dev':5s} {'Wc':>8} {'Wp':>8} {'ΔW%':>7}  "
          f"{'Lc':>6} {'Lp':>6} {'ΔL%':>7}  {'Ic(nA)':>9} {'Ip(nA)':>9} {'ΔI%':>7}")
    names = sorted(set(c["dev"]) | set(p["dev"]), key=lambda n: (len(n), n))
    dW = []
    for n in names:
        a, b = c["dev"].get(n, {}), p["dev"].get(n, {})
        wc, wp = a.get("W"), b.get("W")
        if wc is not None and wp is not None:
            dW.append(abs(wc - wp) / wc * 100 if wc else 0.0)
        print(f"    {n:5s} {str(wc):>8} {str(wp):>8} {pct(wc, wp):>7}  "
              f"{str(a.get('L')):>6} {str(b.get('L')):>6} {pct(a.get('L'), b.get('L')):>7}  "
              f"{str(a.get('I')):>9} {str(b.get('I')):>9} {pct(a.get('I'), b.get('I')):>7}")
    if dW:
        print(f"\n  devices compared: {len(dW)}   mean ΔW%: {sum(dW)/len(dW):.1f}   "
              f"max ΔW%: {max(dW):.1f}")

    # ---- structrec ----
    section("STRUCTREC  (cpp.xml  vs  py_acst.xml)")
    c = structrec_facts(OUT / "structrec/cpp/cpp.xml")
    p = structrec_facts(OUT / "structrec/py/py_acst.xml")
    print(f"  cpp top-level structure types: {dict(c['top_types'])}")
    print(f"  py  top-level structure types: {dict(p['top_types'])}")
    print(f"  cpp all structure types (full tree): {dict(c['all_types'])}")
    print(f"  py  all structure types (full tree): {dict(p['all_types'])}")
    cl = {d: v["leaf"] for d, v in c["dev"].items()}
    pl = {d: v["leaf"] for d, v in p["dev"].items()}
    ct = {d: v["top"] for d, v in c["dev"].items()}
    pt = {d: v["top"] for d, v in p["dev"].items()}
    print("\n  -- leaf structure assignment --")
    cmp_assignment(cl, pl, "leaf", "leaf structure")
    print("\n  -- top-level (composite) structure assignment --")
    cmp_assignment(ct, pt, "top", "top-level structure")

    # ---- partitioning ----
    section("PARTITIONING  (cpp.xml  vs  py_acst.xml)")
    c = partitioning_facts(OUT / "partitioning/cpp/cpp.xml")
    p = partitioning_facts(OUT / "partitioning/py/py_acst.xml")
    print(f"  cpp section device-counts: {dict(c['sec_counts'])}")
    print(f"  py  section device-counts: {dict(p['sec_counts'])}")
    print()
    cmp_assignment(c["dev"], p["dev"], "sec", "section")

    # ---- rulegen ----
    section("RULEGEN  (cpp.xml  vs  py_acst/SymmetricalCascodeOpAmpLibrary.xml)")
    c = rulegen_facts(OUT / "rulegen/cpp/cpp.xml")
    p = rulegen_facts(OUT / "rulegen/py_acst/SymmetricalCascodeOpAmpLibrary.xml")
    print(f"  cpp library items: {c['n_items']}   py library items: {p['n_items']}")
    print(f"  {'item':28s} {'cpp lvl':>7} {'py lvl':>7}   {'cpp pers':>8} {'py pers':>8}")
    allitems = sorted(set(c["levels"]) | set(p["levels"]),
                      key=lambda s: (len(s), s))
    lvl_agree = 0
    for it in allitems:
        cl_, pl_ = c["levels"].get(it, "—"), p["levels"].get(it, "—")
        if cl_ == pl_:
            lvl_agree += 1
        print(f"  {it:28s} {cl_:>7} {pl_:>7}   "
              f"{c['pers'].get(it, '—'):>8} {p['pers'].get(it, '—'):>8}")
    print(f"\n  items at SAME hierarchy level: {lvl_agree}/{len(allitems)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
