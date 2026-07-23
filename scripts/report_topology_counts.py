#!/usr/bin/env python3
"""Per-category op-amp count cross-tab (issue #8).

Regenerates the topology library through the public API and cross-tabs it by
stage count × output family, writing a markdown table.

Usage
-----
    .venv/bin/python scripts/report_topology_counts.py \
        [--report report/reports/TOPOLOGY_COUNTS.md]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))


def _family(spec) -> str:
    if spec.is_complementary:
        return "Complementary"
    if spec.is_fully_differential:
        return "Fully-differential"
    if spec.is_symmetrical:
        return "Symmetrical"
    return "Single-ended"


def crosstab() -> tuple[Counter, int]:
    """Return ``{(stage_label, family): count}`` over the generated library."""
    import loguru
    loguru.logger.remove()

    from pyckt import generate_topology_library

    library = generate_topology_library()
    counts: Counter = Counter()
    for spec in library.topologies.values():
        stage = f"{spec.num_stages}-stage"
        counts[(stage, _family(spec))] += 1
    return counts, library.size()


def render(counts: Counter, total: int) -> str:
    families = ["Single-ended", "Symmetrical", "Fully-differential",
                "Complementary"]
    stages = sorted({stage for stage, _ in counts})
    lines = [
        "# Topology library — per-category op-amp counts (issue #8)",
        "",
        "Cross-tab of the generated topology library by stage count and",
        "output family (the symmetrical one-stage family is acst's own",
        "`symmetrical_op_amp` sub-family of `SingleOutputOpAmps`).",
        "",
        "**Regenerate**: "
        "`.venv/bin/python scripts/report_topology_counts.py`",
        "",
        "| | " + " | ".join(families) + " | total |",
        "|---|" + "---:|" * (len(families) + 1),
    ]
    for stage in stages:
        row = [counts.get((stage, fam), 0) for fam in families]
        lines.append(
            f"| **{stage}** | " + " | ".join(str(v) for v in row)
            + f" | {sum(row)} |"
        )
    col_totals = [
        sum(counts.get((stage, fam), 0) for stage in stages)
        for fam in families
    ]
    lines.append(
        "| **total** | " + " | ".join(str(v) for v in col_totals)
        + f" | {total} |"
    )
    lines += [
        "",
        "Counts are *generated* topologies.  The single-ended enumeration",
        "contains 30 one-stage variants (and their 360 two-stage multiples)",
        "that are structural duplicates of other variants, so the library",
        "collapses to **3912 distinct** topologies — exactly acst's reference",
        "set, matched device-for-device (issue #20): `SingleOutputOpAmps`",
        "2940 (= single-ended 210×13 + symmetrical 210),",
        "`FullyDifferentialOpAmps` 936 (= 72×13), `ComplementaryOpAmps` 36",
        "(one-stage only).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path,
                    default=REPO / "report" / "reports" / "TOPOLOGY_COUNTS.md")
    args = ap.parse_args()

    counts, total = crosstab()
    text = render(counts, total)
    print(text)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(text)
    print(f"report → {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
