#!/usr/bin/env bash
# run_automaticsizing.sh — Automatic transistor sizing, standalone.
#
# Runs pyckt's `automaticsizing` (in acst-compatible format) and, when the acst
# binary is available, the acst reference for the same circuit under a MATCHED
# budget (acst --runtime 5 min ≈ pyckt --timeout 300 s), leaving both outputs
# ready for comparison.
#
# Both tools solve a discrete W/L operating point (KCL + operating region +
# gain/Ft/PM/power/area/CM specs). The XML schema and the performance model
# match acst; the exact W/L endpoint differs because acst's optimiser is a
# randomized, time-bounded search (it differs from itself run-to-run — see
# reports/SIZING_CONVERGENCE.md).
#
# Override any path or budget via environment variable, e.g.
#   TIMEOUT=30 RUNTIME=1 ./run_automaticsizing.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYCKT="${PYCKT:-$REPO/.venv/bin/pyckt}"
ACST="${ACST:-/home/jrad/acst/build/bin/acst.sh}"
PY_IN="${PY_IN:-$REPO/tests/data/inputs}"
ACST_IN="${ACST_IN:-/home/jrad/acst/InputFileExamples}"
ACST_LIB="${ACST_LIB:-/home/jrad/acst/StructRec/xml/AnalogLibrary.xml}"
OUT="${OUT:-$REPO/output/automaticsizing}"
MODEL="${MODEL:-SHM}"        # transistor model: SHM | EKV
SCALING="${SCALING:-0.1mum}" # geometric grid: 0.1mum | 1mum
TIMEOUT="${TIMEOUT:-300}"    # pyckt CP-SAT budget [s]
RUNTIME="${RUNTIME:-5}"      # acst Gecode budget [min]

src="$PY_IN/AutomaticSizing"
acst_src="$ACST_IN/AutomaticSizing/cascodeSymmetricalOpAmp"
mkdir -p "$OUT/py" "$OUT/cpp"

echo "[automaticsizing] pyckt (acst format, ${MODEL}/${SCALING}, ${TIMEOUT}s) ..."
"$PYCKT" --log-level-console OFF automaticsizing \
  --circuit        "$src/cascodedSymmetricalCMOSOTA.hspice" \
  --device-types   "$src/deviceTypes.xcat" \
  --mapping        "$src/HSpiceMapping.xcat" \
  --supply-nets    "$src/supplyNets.xcat" \
  --tech-file      "$src/TechnologyFile.xml" \
  --circuit-params "$src/CircuitParameterAndSpecifications.xml" \
  --transistor-model "$MODEL" --scaling "$SCALING" --timeout "$TIMEOUT" \
  --output-format acst \
  --output "$OUT/py/py_acst.xml"
echo "  -> $OUT/py/py_acst.xml  (+ py_acst.sized.hspice)"

if [[ -x "$ACST" ]]; then
  echo "[automaticsizing] acst (reference, ${MODEL}/${SCALING}, ${RUNTIME}min) ..."
  "$ACST" --log-level-console OFF --analysis automaticsizing \
    --circuit-netlist              "$acst_src/cascodedSymmetricalCMOSOTA.hspice" \
    --device-types-file            "$acst_src/deviceTypes.xcat" \
    --hspice-mapping-file          "$acst_src/HSpiceMapping.xcat" \
    --hspice-supplynet-file        "$acst_src/supplyNets.xcat" \
    --xml-structrec-library-file   "$ACST_LIB" \
    --xml-technologie-file         "$acst_src/TechnologyFile.xml" \
    --xml-circuit-information-file "$acst_src/CircuitParameterAndSpecifications.xml" \
    --transistor-model "$MODEL" --scaling "$SCALING" --runtime "$RUNTIME" \
    --output-file "$OUT/cpp/cpp.xml"
  echo "  -> $OUT/cpp/cpp.xml"
else
  echo "[automaticsizing] acst binary not found ($ACST) — skipped reference run"
fi
echo "[automaticsizing] done."
