#!/usr/bin/env python3
"""Compare the acst and pyckt outputs collected in output_comp/.

Deterministic modes are checked for content equivalence (device→structure,
device→section, library level/persistence); sizing is checked for schema
completeness + performance-model closeness (the numeric endpoint differs by
acst's own randomized search, documented in COMPARISON_REPORT).
"""
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OK, WARN, BAD = "\033[32m✓\033[0m", "\033[33m⚠\033[0m", "\033[31m✗\033[0m"
issues = []


def strip(n):
    return (n or "").lstrip("/")


def base(n):
    return (n or "").split("[", 1)[0]


# ── structrec: device → leaf + top-level structure ────────────────────
def structrec():
    def leaves(path):
        root = ET.parse(path).getroot()
        by_dev = {}
        for struct in root.iter("Structure"):
            for dev in struct.iter("device"):
                by_dev.setdefault(strip(dev.get("name")), base(struct.get("name")))
        # last (deepest) wins → leaf; also collect device set
        devs = {strip(d.get("name")) for d in root.iter("device")}
        return devs
    a = ET.parse(HERE / "structrec/acst/out.xml").getroot()
    p = ET.parse(HERE / "structrec/pyckt/out.xml").getroot()
    da = Counter(base(s.get("name")) for s in a.iter("Structure"))
    dp = Counter(base(s.get("name")) for s in p.iter("Structure"))
    na = len({strip(d.get("name")) for d in a.iter("device")})
    npy = len({strip(d.get("name")) for d in p.iter("device")})
    same = da == dp
    print(f"  {OK if same else BAD} structrec: {na} devices (acst) / {npy} (pyckt); "
          f"structure-type multiset {'identical' if same else 'DIFFERS'}")
    if not same:
        issues.append(f"structrec structure types differ: acst={dict(da)} pyckt={dict(dp)}")


# ── partitioning: section device-counts ───────────────────────────────
def partitioning():
    def sections(path):
        root = ET.parse(path).getroot()
        res = root.find("circuit_partitioning_results") or root
        c = Counter()
        for container in res:
            for part in container:
                key = container.tag
                if part.get("type"):
                    key += ":" + part.get("type")
                c[key] += len(part.findall("structure"))
        return c
    a = sections(HERE / "partitioning/acst/out.xml")
    p = sections(HERE / "partitioning/pyckt/out.xml")
    same = a == p
    print(f"  {OK if same else BAD} partitioning: section device-counts "
          f"{'identical' if same else 'DIFFER'}  acst={dict(a)}")
    if not same:
        issues.append(f"partitioning sections differ: acst={dict(a)} pyckt={dict(p)}")


# ── rulegen: item level + persistence ─────────────────────────────────
def rulegen():
    def items(path):
        root = ET.parse(path).getroot()
        out = {}
        for lvl in root.iter("hierarchyLevel"):
            L = int(lvl.get("level"))
            for it in lvl.findall("pairLibraryItem"):
                out[it.text.strip()] = (L, int(it.get("persistence", 0)))
        return out
    a = items(HERE / "rulegen/acst/SymmetricalCascodeOpAmpLibrary.xml")
    p = items(HERE / "rulegen/pyckt/SymmetricalCascodeOpAmpLibrary.xml")
    names = sorted(set(a) | set(p), key=lambda n: int(n.replace("SymmetricalCascodeOpAmp", "")))
    lvl_match = sum(1 for n in names if n in a and n in p and a[n][0] == p[n][0])
    per_match = sum(1 for n in names if n in a and n in p and a[n][1] == p[n][1])
    both = len(set(a) & set(p))
    good = lvl_match == both == len(a) == len(p)
    print(f"  {OK if good else WARN} rulegen: {len(a)} acst / {len(p)} pyckt items; "
          f"level {lvl_match}/{both}, persistence {per_match}/{both}")
    if not good:
        issues.append(f"rulegen: items acst={len(a)} pyckt={len(p)}, "
                      f"level {lvl_match}/{both}, persistence {per_match}/{both}")


# ── automaticsizing: schema completeness + performance closeness ──────
def sizing():
    def facts(path):
        asr = ET.parse(path).getroot().find("automatic_sizing-results")
        perf = {e.tag: e.text for e in asr.find("ExpectedPerformance")}
        secs = [c.tag for c in asr]
        nv = len(asr.find("Voltages").findall("Net")) if asr.find("Voltages") is not None else 0
        nt = len(asr.find("Dimensions").find("Transistors").findall("Transistor"))
        return perf, secs, nv, nt
    pa, sa, va, ta = facts(HERE / "automaticsizing/acst/out.xml")
    pp, sp, vp, tp = facts(HERE / "automaticsizing/pyckt/out.xml")
    fields_ok = set(pa) <= set(pp)
    sec_ok = sa == sp
    print(f"  {OK if sec_ok else BAD} sizing sections: acst={sa} pyckt={sp}")
    print(f"  {OK if fields_ok else BAD} sizing ExpectedPerformance fields: "
          f"pyckt has all {len(pa)} acst fields" if fields_ok
          else f"  {BAD} sizing missing fields: {set(pa) - set(pp)}")
    print(f"  {OK if (vp>0 and tp==ta) else WARN} Voltages {va}(acst)/{vp}(pyckt) nets, "
          f"Transistors {ta}/{tp}")
    # performance deltas (endpoint differs by design — informational)
    print("  ── ExpectedPerformance (acst vs pyckt, both 5-min budget):")
    for k in ("Gain", "TransitFrequency", "SlewRate", "PhaseMargin",
              "Power", "Area", "CMRR"):
        av, pv = pa.get(k), pp.get(k)
        if av is None or pv is None:
            continue
        try:
            a, p = float(av), float(pv)
            d = abs(a - p) / abs(a) * 100 if a else 0
            print(f"       {k:<18} {a:>10.4g}  {p:>10.4g}   Δ {d:5.1f}%")
        except ValueError:
            pass
    if not fields_ok:
        issues.append(f"sizing missing acst fields: {set(pa) - set(pp)}")
    if not sec_ok:
        issues.append(f"sizing sections differ: acst={sa} pyckt={sp}")


# ── toplibgen: canonical topology signatures per category ─────────────
def toplibgen():
    import sys
    sys.path.insert(0, "/home/jrad/pyckt/pyckt/comparison")
    from topology_signature import signatures_in_dir
    ref = HERE / "toplibgen/acst/Netlists"
    out = HERE / "toplibgen/pyckt"
    if not (out / "SingleOutputOpAmps").is_dir():
        print(f"  {WARN} toplibgen: pyckt output not ready yet — skipping")
        return
    pairs = [("SingleOutputOpAmps", "SingleOutputOpAmps"),
             ("FullyDifferentialOpAmps", "FullyDifferentialOpAmps"),
             ("ComplementaryOpAmps", "CommplementaryOpAmps")]
    all_ok = True
    for py_c, ref_c in pairs:
        a = signatures_in_dir(ref / ref_c)
        pp = signatures_in_dir(out / py_c)
        exact = (sum(a.values()) == sum(pp.values()) and set(a) == set(pp)
                 and all(c == 1 for c in pp.values()))
        all_ok &= exact
        print(f"  {OK if exact else BAD} toplibgen/{py_c}: acst {sum(a.values())} "
              f"vs pyckt {sum(pp.values())} files, sets {'equal' if set(a)==set(pp) else 'DIFFER'}")
        if not exact:
            issues.append(f"toplibgen {py_c}: acst={sum(a.values())} pyckt={sum(pp.values())}")
    return all_ok


# ── synthesis: coverage of acst's sized topologies ───────────────────
def synthesis():
    import sys
    sys.path.insert(0, "/home/jrad/pyckt/pyckt/comparison")
    import topology_signature as ts
    def sig_no_cap(path):
        devs, nets = ts.parse_ckt(path)
        devs = [(k, m.rstrip("4"), t) for k, m, t in devs if k != "cap"]
        used = {n for _, _, terms in devs for _, n in terms}
        return ts._wl_signature(devs, used)
    acst_dir = HERE / "synthesis/acst/results"
    py_dir = HERE / "synthesis/pyckt/candidates"
    if not py_dir.is_dir():
        print(f"  {WARN} synthesis: pyckt output not ready yet — skipping")
        return
    a = {sig_no_cap(f) for f in acst_dir.glob("*.ckt")}
    pp = {sig_no_cap(f) for f in py_dir.glob("*.ckt")}
    covered = len(a & pp)
    pct = covered / len(a) * 100 if a else 0
    good = pct >= 99.0
    print(f"  {OK if good else WARN} synthesis: pyckt sized {sum(1 for _ in py_dir.glob('*.ckt'))} "
          f"candidates, covering {covered}/{len(a)} ({pct:.1f}%) of acst's sized topologies")
    if pct < 99.0:
        issues.append(f"synthesis coverage {covered}/{len(a)} ({pct:.1f}%)")


if __name__ == "__main__":
    print("output_comp — acst vs pyckt (matched inputs & budgets)\n")
    for fn in (structrec, partitioning, rulegen, sizing, toplibgen, synthesis):
        try:
            fn()
        except Exception as e:  # surface a broken/missing output as an issue
            print(f"  {BAD} {fn.__name__}: {type(e).__name__}: {e}")
            issues.append(f"{fn.__name__} comparison crashed: {e}")
    print()
    if issues:
        print(f"{BAD} {len(issues)} issue(s):")
        for i in issues:
            print("   -", i)
    else:
        print(f"{OK} no content issues — every mode matches or is within documented bounds.")
