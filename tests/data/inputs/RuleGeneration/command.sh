#!/bin/sh

/home/jrad/acst/build/bin/acst.sh --log-level-console DEBUG  --circuit-netlist cascodedSymmetricalCMOSOTA.hspice --analysis rulegen --xml-structrec-library-file /home/jrad/acst/InputFileExamples/RuleGeneration/Library.xml --hspice-mapping-file HSpiceMapping.xcat --hspice-supplynet-file supplyNets.xcat --device-types-file deviceTypes.xcat --structure-name SymmetricalCascodeOpAmp

