#!/bin/bash
# output_comp — run acst (reference) and pyckt under matched conditions,
# same inputs and same budgets, for every deterministic mode + sizing.
# The two long generators (toplibgen, synthesis) are driven separately by
# run_generators.sh because acst takes minutes-to-hours on them.
set -u
export PATH="$HOME/.local/bin:$PATH"

ACST=/home/jrad/acst/build/bin/acst.sh
PYCKT="/home/jrad/pyckt/pyckt/.venv/bin/python -m cli"
LIB=/home/jrad/acst/StructRec/xml/AnalogLibrary.xml
AIN=/home/jrad/acst/InputFileExamples
PIN=/home/jrad/pyckt/pyckt/tests/data/inputs
HERE=/home/jrad/report/output_comp
cd /home/jrad/pyckt/pyckt   # pyckt CLI runs from repo root

say(){ echo "=== $* ==="; }

# ── structrec ─────────────────────────────────────────────────────────
say structrec
$ACST --circuit-netlist $AIN/StructureRecognition/input.ckt \
  --device-types-file $AIN/StructureRecognition/deviceTypes.xcat \
  --hspice-mapping-file $AIN/StructureRecognition/HSpiceMapping.xcat \
  --hspice-supplynet-file $AIN/StructureRecognition/supplyNets.xcat \
  --xml-structrec-library-file $LIB --analysis structrec \
  --output-file $HERE/structrec/acst/out.xml >/dev/null 2>&1
$PYCKT --log-level-console OFF structrec \
  --circuit $PIN/StructureRecognition/input.ckt \
  --device-types $PIN/StructureRecognition/deviceTypes.xcat \
  --mapping $PIN/StructureRecognition/HSpiceMapping.xcat \
  --supply-nets $PIN/StructureRecognition/supplyNets.xcat \
  --output-format acst --output $HERE/structrec/pyckt/out.xml >/dev/null 2>&1

# ── partitioning ──────────────────────────────────────────────────────
say partitioning
$ACST --circuit-netlist $AIN/Partitioning/cascodedSymmetricalCMOSOTA.hspice \
  --device-types-file $AIN/Partitioning/deviceTypes.xcat \
  --hspice-mapping-file $AIN/Partitioning/HSpiceMapping.xcat \
  --hspice-supplynet-file $AIN/Partitioning/supplyNets.xcat \
  --xml-structrec-library-file $LIB --analysis partitioning \
  --output-file $HERE/partitioning/acst/out.xml >/dev/null 2>&1
$PYCKT --log-level-console OFF partitioning \
  --circuit $PIN/Partitioning/cascodedSymmetricalCMOSOTA.hspice \
  --device-types $PIN/Partitioning/deviceTypes.xcat \
  --mapping $PIN/Partitioning/HSpiceMapping.xcat \
  --supply-nets $PIN/Partitioning/supplyNets.xcat \
  --output-format acst --output $HERE/partitioning/pyckt/out.xml >/dev/null 2>&1

# ── rulegen (both consume acst's own wrapper library) ─────────────────
say rulegen
$ACST --circuit-netlist $AIN/RuleGeneration/cascodedSymmetricalCMOSOTA.hspice \
  --device-types-file $AIN/RuleGeneration/deviceTypes.xcat \
  --hspice-mapping-file $AIN/RuleGeneration/HSpiceMapping.xcat \
  --hspice-supplynet-file $AIN/RuleGeneration/supplyNets.xcat \
  --xml-structrec-library-file $AIN/RuleGeneration/Library.xml \
  --structure-name SymmetricalCascodeOpAmp --analysis rulegen \
  --output-file $HERE/rulegen/acst/out.xml >/dev/null 2>&1
# acst rulegen ignores --output-file: it writes <name>Library.xml next to the
# --xml-structrec-library-file. Collect the real pairLibrary from there.
RG=$AIN/RuleGeneration/SymmetricalCascodeOpAmp
cp $RG/SymmetricalCascodeOpAmpLibrary.xml $HERE/rulegen/acst/ 2>/dev/null
mkdir -p $HERE/rulegen/acst/Items && cp $RG/Items/*.xml $HERE/rulegen/acst/Items/ 2>/dev/null
$PYCKT --log-level-console OFF rulegen \
  --circuit $PIN/RuleGeneration/cascodedSymmetricalCMOSOTA.hspice \
  --device-types $PIN/RuleGeneration/deviceTypes.xcat \
  --mapping $PIN/RuleGeneration/HSpiceMapping.xcat \
  --supply-nets $PIN/RuleGeneration/supplyNets.xcat \
  --library $AIN/RuleGeneration/Library.xml \
  --structure-name SymmetricalCascodeOpAmp \
  --output-format acst --output $HERE/rulegen/pyckt/SymmetricalCascodeOpAmpLibrary.xml >/dev/null 2>&1

# ── automaticsizing (matched budget: acst --runtime 5, pyckt --timeout 300) ─
say "automaticsizing (5-min budget both)"
ASIN=$AIN/AutomaticSizing/cascodeSymmetricalOpAmp
$ACST --circuit-netlist $ASIN/cascodedSymmetricalCMOSOTA.hspice \
  --device-types-file $ASIN/deviceTypes.xcat \
  --hspice-mapping-file $ASIN/HSpiceMapping.xcat \
  --hspice-supplynet-file $ASIN/supplyNets.xcat \
  --xml-structrec-library-file $LIB \
  --xml-technologie-file $ASIN/TechnologyFile.xml \
  --xml-circuit-information-file $ASIN/CircuitParameterAndSpecifications.xml \
  --transistor-model SHM --scaling 0.1mum --runtime 5 --analysis automaticsizing \
  --output-file $HERE/automaticsizing/acst/out.xml >/dev/null 2>&1
$PYCKT --log-level-console OFF automaticsizing \
  --circuit $PIN/AutomaticSizing/cascodedSymmetricalCMOSOTA.hspice \
  --device-types $PIN/AutomaticSizing/deviceTypes.xcat \
  --mapping $PIN/AutomaticSizing/HSpiceMapping.xcat \
  --supply-nets $PIN/AutomaticSizing/supplyNets.xcat \
  --tech-file $PIN/AutomaticSizing/TechnologyFile.xml \
  --circuit-params $PIN/AutomaticSizing/CircuitParameterAndSpecifications.xml \
  --transistor-model SHM --scaling 0.1mum --timeout 300 \
  --output-format acst --output $HERE/automaticsizing/pyckt/out.xml >/dev/null 2>&1

say done
