#!/usr/bin/env bash
# run_toplibgen.sh — Topology-library generation (toplibgen), standalone.
#
# Runs pyckt's `toplibgen` in acst-compatible format: it enumerates every
# op-amp topology and writes one `.ckt` netlist per topology into ACST's three
# category directories (SingleOutputOpAmps / FullyDifferentialOpAmps /
# ComplementaryOpAmps).  pyckt-only — acst is a benchmark and is not run here.
#
# Override any path via environment variable, e.g.  OUT=/tmp/out ./run_toplibgen.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYCKT="${PYCKT:-$REPO/.venv/bin/pyckt}"
OUT="${OUT:-$REPO/output/toplibgen}"

out_dir="$OUT"
mkdir -p "$out_dir"

echo "[toplibgen] pyckt (acst format) ..."
"$PYCKT" --log-level-console OFF toplibgen \
  --output-dir "$out_dir" \
  --output-format acst
echo "  -> $out_dir/{SingleOutputOpAmps,FullyDifferentialOpAmps,ComplementaryOpAmps}/"

echo "[toplibgen] per-category counts:"
total=0
for cat in SingleOutputOpAmps FullyDifferentialOpAmps ComplementaryOpAmps; do
  d="$out_dir/$cat"
  n=0
  [[ -d "$d" ]] && n=$(find "$d" -maxdepth 1 -name '*.ckt' | wc -l | tr -d ' ')
  printf '  %-26s %6d\n' "$cat" "$n"
  total=$((total + n))
done
printf '  %-26s %6d\n' "TOTAL" "$total"
echo "[toplibgen] done."
