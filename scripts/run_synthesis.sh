#!/usr/bin/env bash
# run_synthesis.sh — Topology synthesis (filter → size → rank), standalone.
#
# pyckt's `synthesis` sizes every candidate topology with the real CP-SAT
# solver and ranks them on the solved performance, writing fully-sized `.ckt`
# netlists plus a ranked JSON summary. Always runs pyckt.
#
# The acst reference is OPT-IN (RUN_ACST=1): acst's synthesis is a multi-hour
# run (~3 h on this fixture) and — unlike the other modes — writes its sized
# netlists *into the --HSPICE-netlist-dir input directory itself*, not a clean
# output path. When enabled, this script snapshots that directory and collects
# only the newly-written files.
#
# Override any path or budget via environment variable, e.g.
#   SIZING_TIMEOUT=5 MAX_CANDIDATES=50 ./run_synthesis.sh
#   RUN_ACST=1 ./run_synthesis.sh          # also run the (slow) acst reference
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYCKT="${PYCKT:-$REPO/.venv/bin/pyckt}"
ACST="${ACST:-/home/jrad/acst/build/bin/acst.sh}"
PY_IN="${PY_IN:-$REPO/tests/data/inputs}"
ACST_IN="${ACST_IN:-/home/jrad/acst/InputFileExamples}"
ACST_LIB="${ACST_LIB:-/home/jrad/acst/StructRec/xml/AnalogLibrary.xml}"
OUT="${OUT:-$REPO/output/synthesis}"
SIZING_TIMEOUT="${SIZING_TIMEOUT:-2}"     # per-candidate CP-SAT budget [s]
MAX_CANDIDATES="${MAX_CANDIDATES:-}"      # empty = size the whole library
MODEL="${MODEL:-SHM}"
SCALING="${SCALING:-1mum}"

src="$PY_IN/Synthesis"
acst_src="$ACST_IN/Synthesis"
mkdir -p "$OUT/py" "$OUT/cpp"

echo "[synthesis] pyckt (real sizing, ${SIZING_TIMEOUT}s/candidate${MAX_CANDIDATES:+, first $MAX_CANDIDATES}) ..."
max_arg=()
[[ -n "$MAX_CANDIDATES" ]] && max_arg=(--max-candidates "$MAX_CANDIDATES")
# The engine sizes every candidate (recognise → partition → CP-SAT); its
# per-candidate logs are verbose on a full ~3.3k-candidate run, so tee them to
# a log file and keep the console to the ranked summary below.
"$PYCKT" --log-level-console OFF synthesis \
  --device-types "$src/deviceTypes.xcat" \
  --tech-file    "$src/TechnologieFile.xml" \
  --spec         "$src/CircuitSpecifications.xml" \
  --sizing-timeout "$SIZING_TIMEOUT" "${max_arg[@]}" \
  --output-dir "$OUT/py" > "$OUT/py/run.log" 2>&1
n=$(find "$OUT/py/candidates" -maxdepth 1 -name '*.ckt' 2>/dev/null | wc -l | tr -d ' ')
echo "  -> $OUT/py/synthesis_results.json  (+ $n sized candidates/)"
if [[ -f "$OUT/py/synthesis_results.json" ]]; then
  python3 - "$OUT/py/synthesis_results.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
from collections import Counter
c = Counter(r.get("solver_status") for r in d)
print(f"  ranked {len(d)} candidates  ({', '.join(f'{k}={v}' for k,v in c.items())})")
if d:
    t = d[0]
    print(f"  rank 1: {t['name']}  gain={t['gain_db']}dB ft={t['transit_freq_mhz']}MHz "
          f"power={t['power_mw']}mW area={t['area_um2']}um2")
PY
fi

if [[ "${RUN_ACST:-0}" == "1" && -x "$ACST" ]]; then
  echo "[synthesis] acst (reference — SLOW, ~3 h; writes into its input dir) ..."
  marker="$(mktemp)"; sleep 1
  "$ACST" --log-level-console OFF --analysis synthesis \
    --xml-structrec-library-file   "$ACST_LIB" \
    --device-types-file            "$acst_src/deviceTypes.xcat" \
    --xml-technologie-file         "$acst_src/TechnologieFile.xml" \
    --xml-circuit-information-file "$acst_src/CircuitSpecifications.xml" \
    --transistor-model "$MODEL" --scaling "$SCALING" \
    --HSPICE-netlist-dir "$acst_src/HspiceNetlist" > "$OUT/cpp/run.log" 2>&1
  # acst wrote its sized netlists into HspiceNetlist/ — collect only the new ones
  found=$(find "$acst_src/HspiceNetlist" -name '*.ckt' -newer "$marker" -print0 \
            | tee >(xargs -0 -I{} cp {} "$OUT/cpp/" 2>/dev/null) | tr -dc '\0' | wc -c)
  rm -f "$marker"
  echo "  -> $OUT/cpp/  ($found sized netlists collected)"
else
  echo "[synthesis] acst reference skipped (set RUN_ACST=1 to run it — ~3 h)."
fi
echo "[synthesis] done."
