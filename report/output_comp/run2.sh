#!/bin/bash
# output_comp SET 2 — a DIFFERENT set of conditions:
#   * different circuit: complementaryOpAmp (complementary CMOS OTA), not the
#     cascoded symmetric OTA of set 1
#   * both tools use acst's OWN 52-item library (pyckt via the #47 wrapper
#     loader) so recognition is a fair like-for-like comparison
#   * sizing at scaling 1mum (set 1 used 0.1mum), 5-min budget both
#   * synthesis at 5 s/candidate (set 1 used 2 s)
set -u
export PATH="$HOME/.local/bin:$PATH"

ACST=/home/jrad/acst/build/bin/acst.sh
PYCKT="/home/jrad/pyckt/pyckt/.venv/bin/python -m cli"
ALIB=/home/jrad/acst/StructRec/xml/AnalogLibrary.xml     # acst's 52-item wrapper
C=/home/jrad/acst/InputFileExamples/AutomaticSizing/complementaryOpAmp
HERE=/home/jrad/report/output_comp/set2
cd /home/jrad/pyckt/pyckt
say(){ echo "=== $* ==="; }

# ── structrec (complementary circuit, acst's library on both) ─────────
say "structrec (complementaryOpAmp, acst library)"
$ACST --circuit-netlist $C/complementaryOpAmp.hspice \
  --device-types-file $C/deviceTypes.xcat \
  --hspice-mapping-file $C/HSpiceMapping.xcat \
  --hspice-supplynet-file $C/supplyNets.xcat \
  --xml-structrec-library-file $ALIB --analysis structrec \
  --output-file $HERE/structrec/acst/out.xml >/dev/null 2>&1
$PYCKT --log-level-console OFF structrec \
  --circuit $C/complementaryOpAmp.hspice --device-types $C/deviceTypes.xcat \
  --mapping $C/HSpiceMapping.xcat --supply-nets $C/supplyNets.xcat \
  --library $ALIB \
  --output-format acst --output $HERE/structrec/pyckt/out.xml >/dev/null 2>&1

# ── partitioning (same circuit, acst library) ─────────────────────────
say "partitioning (complementaryOpAmp, acst library)"
$ACST --circuit-netlist $C/complementaryOpAmp.hspice \
  --device-types-file $C/deviceTypes.xcat \
  --hspice-mapping-file $C/HSpiceMapping.xcat \
  --hspice-supplynet-file $C/supplyNets.xcat \
  --xml-structrec-library-file $ALIB --analysis partitioning \
  --output-file $HERE/partitioning/acst/out.xml >/dev/null 2>&1
$PYCKT --log-level-console OFF partitioning \
  --circuit $C/complementaryOpAmp.hspice --device-types $C/deviceTypes.xcat \
  --mapping $C/HSpiceMapping.xcat --supply-nets $C/supplyNets.xcat \
  --library $ALIB \
  --output-format acst --output $HERE/partitioning/pyckt/out.xml >/dev/null 2>&1

# ── automaticsizing (complementary circuit, scaling 1mum, 5-min both) ──
say "automaticsizing (complementaryOpAmp, scaling 1mum, 5-min budget)"
$ACST --circuit-netlist $C/complementaryOpAmp.hspice \
  --device-types-file $C/deviceTypes.xcat \
  --hspice-mapping-file $C/HSpiceMapping.xcat \
  --hspice-supplynet-file $C/supplyNets.xcat \
  --xml-structrec-library-file $ALIB \
  --xml-technologie-file $C/TechnologyFile.xml \
  --xml-circuit-information-file $C/CircuitParameterAndSpecifications.xml \
  --transistor-model SHM --scaling 1mum --runtime 5 --analysis automaticsizing \
  --output-file $HERE/automaticsizing/acst/out.xml >/dev/null 2>&1
$PYCKT --log-level-console OFF automaticsizing \
  --circuit $C/complementaryOpAmp.hspice --device-types $C/deviceTypes.xcat \
  --mapping $C/HSpiceMapping.xcat --supply-nets $C/supplyNets.xcat \
  --tech-file $C/TechnologyFile.xml \
  --circuit-params $C/CircuitParameterAndSpecifications.xml \
  --library $ALIB \
  --transistor-model SHM --scaling 1mum --timeout 300 \
  --output-format acst --output $HERE/automaticsizing/pyckt/out.xml >/dev/null 2>&1

say done
