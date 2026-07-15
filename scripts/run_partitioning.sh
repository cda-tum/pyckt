#!/usr/bin/env bash
# run_partitioning.sh — Circuit Partitioning, standalone.
#
# Runs pyckt's `partitioning` (acst-compatible format) and, when available, the
# acst reference for the same circuit.
#
# Like acst, pyckt derives the input/output/bias/supply net roles from the
# circuit structure — no --circuit-params file is needed (it remains available
# as an optional override).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYCKT="${PYCKT:-$REPO/.venv/bin/pyckt}"
ACST="${ACST:-/home/jrad/acst/build/bin/acst.sh}"
PY_IN="${PY_IN:-$REPO/tests/data/inputs}"
ACST_IN="${ACST_IN:-/home/jrad/acst/InputFileExamples}"
ACST_LIB="${ACST_LIB:-/home/jrad/acst/StructRec/xml/AnalogLibrary.xml}"
OUT="${OUT:-$REPO/output/partitioning}"

src="$PY_IN/Partitioning"
acst_src="$ACST_IN/Partitioning"
mkdir -p "$OUT/py" "$OUT/cpp"

echo "[partitioning] pyckt (acst format) ..."
"$PYCKT" --log-level-console OFF partitioning \
  --circuit        "$src/cascodedSymmetricalCMOSOTA.hspice" \
  --device-types   "$src/deviceTypes.xcat" \
  --mapping        "$src/HSpiceMapping.xcat" \
  --supply-nets    "$src/supplyNets.xcat" \
  --output-format  acst \
  --output "$OUT/py/py_acst.xml"
echo "  -> $OUT/py/py_acst.xml"

if [[ -x "$ACST" ]]; then
  echo "[partitioning] acst (reference) ..."
  "$ACST" --log-level-console OFF --analysis partitioning \
    --circuit-netlist            "$acst_src/cascodedSymmetricalCMOSOTA.hspice" \
    --device-types-file          "$acst_src/deviceTypes.xcat" \
    --hspice-mapping-file        "$acst_src/HSpiceMapping.xcat" \
    --hspice-supplynet-file      "$acst_src/supplyNets.xcat" \
    --xml-structrec-library-file "$ACST_LIB" \
    --output-file "$OUT/cpp/cpp.xml"
  echo "  -> $OUT/cpp/cpp.xml"
else
  echo "[partitioning] acst binary not found ($ACST) — skipped reference run"
fi
echo "[partitioning] done."
