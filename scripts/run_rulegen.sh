#!/usr/bin/env bash
# run_rulegen.sh — Recognition-rule generation (rulegen), standalone.
#
# acst's rulegen *learns a recognition library* (a pairLibrary of new composite
# structures), NOT sizing rules.  pyckt reproduces that artifact with
# `--output-format acst`.  Both write a <Name>Library.xml index plus Items/.
#
# acst writes its result next to the input library (not via --output-file), so
# we copy it into the comparison tree afterwards.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYCKT="${PYCKT:-$REPO/.venv/bin/pyckt}"
ACST="${ACST:-/home/jrad/acst/build/bin/acst.sh}"
PY_IN="${PY_IN:-$REPO/tests/data/inputs}"
ACST_IN="${ACST_IN:-/home/jrad/acst/InputFileExamples}"
ACST_LIB="${ACST_LIB:-/home/jrad/acst/StructRec/xml/AnalogLibrary.xml}"
NAME="${NAME:-SymmetricalCascodeOpAmp}"
OUT="${OUT:-$REPO/output/rulegen}"

src="$PY_IN/RuleGeneration"
acst_src="$ACST_IN/RuleGeneration"
mkdir -p "$OUT/py_acst" "$OUT/cpp"

echo "[rulegen] pyckt (acst format — learns pairLibrary) ..."
"$PYCKT" --log-level-console OFF rulegen \
  --circuit        "$src/cascodedSymmetricalCMOSOTA.hspice" \
  --device-types   "$src/deviceTypes.xcat" \
  --mapping        "$src/HSpiceMapping.xcat" \
  --supply-nets    "$src/supplyNets.xcat" \
  --library        "$ACST_LIB" \
  --structure-name "$NAME" \
  --output-format  acst \
  --output "$OUT/py_acst/${NAME}Library.xml"
echo "  -> $OUT/py_acst/${NAME}Library.xml  (+ Items/)"

if [[ -x "$ACST" ]]; then
  echo "[rulegen] acst (reference) ..."
  "$ACST" --log-level-console OFF --analysis rulegen \
    --circuit-netlist            "$acst_src/cascodedSymmetricalCMOSOTA.hspice" \
    --device-types-file          "$acst_src/deviceTypes.xcat" \
    --hspice-mapping-file        "$acst_src/HSpiceMapping.xcat" \
    --hspice-supplynet-file      "$acst_src/supplyNets.xcat" \
    --xml-structrec-library-file "$acst_src/Library.xml" \
    --structure-name "$NAME"
  # acst writes <libdir>/<Name>/<Name>Library.xml (+ Items/) — copy it in.
  acst_result="$acst_src/${NAME}/${NAME}Library.xml"
  if [[ -f "$acst_result" ]]; then
    cp -r "$acst_src/${NAME}/." "$OUT/cpp/"
    echo "  -> $OUT/cpp/${NAME}Library.xml  (+ Items/)"
  else
    echo "  acst result not found at $acst_result"
  fi
else
  echo "[rulegen] acst binary not found ($ACST) — skipped reference run"
fi
echo "[rulegen] done."
