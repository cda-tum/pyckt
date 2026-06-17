#!/usr/bin/env bash
# run_structrec.sh — Structure Recognition, standalone.
#
# Runs pyckt's `structrec` (in acst-compatible format) and, when the acst
# binary is available, the acst reference for the same input, leaving both
# outputs ready for comparison.
#
# Override any path via environment variable, e.g.  OUT=/tmp/out ./run_structrec.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYCKT="${PYCKT:-$REPO/.venv/bin/pyckt}"
ACST="${ACST:-/home/jrad/acst/build/bin/acst.sh}"
PY_IN="${PY_IN:-$REPO/tests/data/inputs}"
ACST_IN="${ACST_IN:-/home/jrad/acst/InputFileExamples}"
ACST_LIB="${ACST_LIB:-/home/jrad/acst/StructRec/xml/AnalogLibrary.xml}"
OUT="${OUT:-$REPO/output/structrec}"

src="$PY_IN/StructureRecognition"
acst_src="$ACST_IN/StructureRecognition"
mkdir -p "$OUT/py" "$OUT/cpp"

echo "[structrec] pyckt (acst format) ..."
"$PYCKT" --log-level-console OFF structrec \
  --circuit      "$src/input.ckt" \
  --device-types "$src/deviceTypes.xcat" \
  --mapping      "$src/HSpiceMapping.xcat" \
  --supply-nets  "$src/supplyNets.xcat" \
  --output-format acst \
  --output "$OUT/py/py_acst.xml"
echo "  -> $OUT/py/py_acst.xml"

if [[ -x "$ACST" ]]; then
  echo "[structrec] acst (reference) ..."
  "$ACST" --log-level-console OFF --analysis structrec \
    --circuit-netlist            "$acst_src/input.ckt" \
    --device-types-file          "$acst_src/deviceTypes.xcat" \
    --hspice-mapping-file        "$acst_src/HSpiceMapping.xcat" \
    --hspice-supplynet-file      "$acst_src/supplyNets.xcat" \
    --xml-structrec-library-file "$ACST_LIB" \
    --output-file "$OUT/cpp/cpp.xml"
  echo "  -> $OUT/cpp/cpp.xml"
else
  echo "[structrec] acst binary not found ($ACST) — skipped reference run"
fi
echo "[structrec] done."
