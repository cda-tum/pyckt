from src.utils.loguru_loader import setup_logger
from src.topogen.HL2.vb import VoltageBiasManager
from src.topogen.HL2.cb import CurrentBiasManager
from src.topogen.common.circuit import (
    Circuit,
    TransistorStack,
    LoadPart,
    save_graphviz_figure,
    convert_dot_to_png,
    createTransistorStack,
    connectInstanceTerminal,
)

from pathlib import Path
import json

# fmt: off

GALLERY_DOT_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "lp" / "dots"
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "lp" / "images"
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

logger = setup_logger(log_level="DEBUG", log_file=None)


def connectInstanceTerminalsOfTwoTransistorLoadPart(out: dict, ts1, ts2):
    num = 1
    # fmt: off
    for transistorStack in [ts1, ts2]:
        if transistorStack.instances[0].name.startswith("cb"):
            if num == 1:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out1", "out")
            else:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out2", "out")
            out, transistorStack =  connectInstanceTerminal(out, transistorStack, "inner", "in")
            out, transistorStack =  connectInstanceTerminal(out, transistorStack, "source", "source")

        else:
            if num == 1:
                out, transistorStack =  connectInstanceTerminal(out, transistorStack, "out1", "in")
            else:
                out, transistorStack =  connectInstanceTerminal(out, transistorStack, "out2", "in")
            if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith("vb"):
                if num == 1:
                    out, transistorStack = connectInstanceTerminal(out, transistorStack, "out1", "out")
                else:
                    out, transistorStack =  connectInstanceTerminal(out, transistorStack, "out2", "out")
            else:
                out, transistorStack =  connectInstanceTerminal(out, transistorStack, "inner", "out")
            out, transistorStack = connectInstanceTerminal(out, transistorStack, "source", "source")
        num += 1
    # fmt: on
    return out


def connectInstanceTerminalsOfFourTransistorLoadPart(out, ts1, ts2):
    num = 1
    # fmt: off
    for transistorStack in [ts1, ts2]:
        if transistorStack.instances[0].name.startswith("cb"):
            if num==1:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out1", "out" )
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "inner_transistorstack1", "inner" )
            else:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out2", "out" )
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "inner_transistorstack2", "inner" )                    

            out, transistorStack =connectInstanceTerminal(out, transistorStack, "inner_output", "inoutput" )
            out, transistorStack = connectInstanceTerminal(out, transistorStack, "inner_source", "insource" )
            out, transistorStack = connectInstanceTerminal(out, transistorStack, "source", "source" )
        else:
            if num==1:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out1", "in" )
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "inner_transistorstack1", "inner" )
            else:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out2", "in" )
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "inner_transistorstack2", "inner" )
            
            if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith("vb"): 
                if num==1:
                    out, transistorStack =connectInstanceTerminal(out, transistorStack, "outoutput1", "outinput" )
                    out, transistorStack = connectInstanceTerminal(out, transistorStack, "outsource1", "outsource" )
                else:
                    out, transistorStack=connectInstanceTerminal(out, transistorStack, "outoutput2", "outinput" )
                    out, transistorStack=connectInstanceTerminal(out, transistorStack, "outsource2", "outsource" )
            else:
                out, transistorStack=connectInstanceTerminal(out, transistorStack, "inner_output", "outinput" )
                out, transistorStack=connectInstanceTerminal(out, transistorStack, "inner_source", "outsource" )
            
            out, transistorStack=connectInstanceTerminal(out, transistorStack, "source", "source" )
        
        num+=1
    return out
    # fmt: on


def connectInstanceTerminalsOfTwoTransistorLoadPartDifferentSources(
    out, ts1: TransistorStack, ts2: TransistorStack
):
    num = 1
    # fmt: off
    for transistorStack in [ts1, ts2]:
        if transistorStack.name.startswith("cb"):
            if num == 1:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out1", "out")
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "source1", "source")
            else:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out2", "out")
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "source2", "source")
            out, transistorStack = connectInstanceTerminal(out, transistorStack, "inner", "in")
        else:
            if num == 1:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out1", "in")
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "source1", "source")
            else:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "out2", "in")
                out, transistorStack =connectInstanceTerminal(out, transistorStack, "source2", "source")

            if ts1.name == "vb" and ts2.name == "vb":
                if num == 1:
                    out, transistorStack = connectInstanceTerminal(out, transistorStack, "out1", "out")
                else:
                    out, transistorStack = connectInstanceTerminal(out, transistorStack, "out2", "out")
            else:
                out, transistorStack = connectInstanceTerminal(out, transistorStack, "inner", "out")
        num += 1
    return out
    # fmt: on


def createTwoTransistorLoadPart(ts1: TransistorStack, ts2: TransistorStack):
    # if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith(
    #     "vb"
    # ):
    #     lp = LoadPart(id=1, techtype="p")
    # else:
    lp = LoadPart(id=1, techtype="p")
    lp.ports = ["out1", "out2", "source"]
    lp.add_instance(ts1)
    lp.add_instance(ts2)

    if ts1.instances[0].name.startswith("vb") or ts2.instances[0].name.startswith("vb"):
        pass

    lp = connectInstanceTerminalsOfTwoTransistorLoadPart(lp, ts1, ts2)
    return lp


def createTwoTransistorLoadPartDifferentSources(
    ts1: TransistorStack, ts2: TransistorStack
):
    lp = LoadPart(id=1, techtype="p")
    lp.ports = ["out1", "out2", "source1", "source2"]
    lp.add_instance(ts1)
    lp.add_instance(ts2)

    if ts1.instances[0].name.startswith("vb") or ts2.instances[0].name.startswith("vb"):
        pass

    lp = connectInstanceTerminalsOfTwoTransistorLoadPartDifferentSources(lp, ts1, ts2)
    return lp


def connectInstanceTerminalsOfThreeTransistorLoadPart(
    out, ts1: TransistorStack, ts2: TransistorStack
):
    out, ts1 = connectInstanceTerminal(out, ts1, "out1", "in")
    out, ts1 = connectInstanceTerminal(out, ts1, "inner_source", "out")
    out, ts1 = connectInstanceTerminal(out, ts1, "source", "source")

    out, ts2 = connectInstanceTerminal(out, ts2, "out2", "out")
    if len(ts1.instances) == 1 and ts1.instances[0].name == "dt":
        out, ts2 = connectInstanceTerminal(out, ts2, "inner_output", "inoutput")
    else:
        out, ts2 = connectInstanceTerminal(out, ts2, "out1", "inoutput")

    out, ts2 = connectInstanceTerminal(out, ts2, "inner_source", "insource")
    out, ts2 = connectInstanceTerminal(out, ts2, "inner_transistorstack2", "inner")
    out, ts2 = connectInstanceTerminal(out, ts2, "source", "source")
    return out


def createThreeTransistorLoadPart(ts1: TransistorStack, ts2: TransistorStack):
    lp = LoadPart(id=1, techtype="p")
    lp.ports = ["out1", "out2", "source", "inner_transistorstack2", "inner_source"]
    lp.add_instance(ts1)
    lp.add_instance(ts2)

    if ts1.instances[0].name.startswith("vb") or ts2.instances[0].name.startswith("vb"):
        pass

    lp = connectInstanceTerminalsOfThreeTransistorLoadPart(lp, ts1, ts2)
    return lp


def isNDoped(name):
    if "NMOS" in name:
        return True
    if "DIODE_NMOS" in name:
        return True
    return False


def isPDoped(name):
    if "PMOS" in name:
        return True
    if "DIODE_PMOS" in name:
        return True
    return False


def moreThanOneNDopdedDrainPin(drainPins):
    counter = 0
    for pin in drainPins:
        if "NMOS" in pin:
            counter += 1
        if counter >= 2:
            return True
    return False


def moreThanOnePDopdedDrainPin(drainPins):
    counter = 0
    for pin in drainPins:
        if "PMOS" in pin:
            counter += 1
        if counter >= 2:
            return True
    return False


def everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType(flatNets):
    for main_net, sub_nets in flatNets.items():
        gatePins = [net for net in sub_nets if net.endswidth("MOS.G")]
        drainPins = [net for net in sub_nets if net.endswidth("MOS.D")]

        if False not in list(map(isNDoped, gatePins)):
            if moreThanOneNDopdedDrainPin(drainPins):
                return False
        elif False not in list(map(isPDoped, gatePins)):
            if moreThanOnePDopdedDrainPin(drainPins):
                return False
        else:
            if moreThanOneNDopdedDrainPin(drainPins) or moreThanOnePDopdedDrainPin(
                drainPins
            ):
                return False

    return True


def hasGateNetsNotConnectedToADrain(subcircuit):
    return False


def isSingleDiodeTransistor(subcircuit):
    if subcircuit["type"] in ["DIODE_PMOS", "DIODE_NMOS"]:
        return True
    else:
        pass
        # if "instances" in subcircuit:
        #     for


def createTwoTransistorLoadPartsVoltageBiases(
    oneTransistorVoltageBiases: list[Circuit],
):
    out: list[Circuit] = []
    for voltageBias in oneTransistorVoltageBiases:

        if len(voltageBias.instances) == 1:
            ts1 = createTransistorStack(1, voltageBias)
            ts2 = createTransistorStack(2, voltageBias)

            # fmt: on
            loadpart = createTwoTransistorLoadPart(ts1, ts2)
            out.append(loadpart)
            pass

    return out


def createTwoTransistorLoadPartsMixed(
    oneTransistorVoltageBiases, oneTransistorCurrentBiases
):
    out = []
    for voltageBias in oneTransistorVoltageBiases:
        for currentBias in oneTransistorCurrentBiases:
            ts1 = createTransistorStack(1, voltageBias)
            ts2 = createTransistorStack(2, currentBias)

            # fmt: on

            loadpart = createTwoTransistorLoadPart(ts1, ts2)
            out.append(loadpart)
    return out


def createThreeTransistorLoadPartsMixed(
    oneTransistorVoltageBiases, twoTransistorCurrentBiases
):
    out = []
    for voltageBias in oneTransistorVoltageBiases:
        for currentBias in twoTransistorCurrentBiases:
            ts1 = createTransistorStack(1, voltageBias)
            ts2 = createTransistorStack(2, currentBias)

            # fmt: on

            loadpart = createThreeTransistorLoadPart(ts1, ts2)
            out.append(loadpart)
    return out


def createFourTransistorLoadPart(ts1, ts2):
    # out = {}
    # if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith(
    #     "vb"
    # ):
    #     lp = LoadPart(id=1, techtype="p")
    # else:
    lp = LoadPart(id=1, techtype="p")
    lp.ports = [
        "out1",
        "out2",
        "inner_transistorstack1",
        "inner_transistorstack2",
        "source",
    ]
    lp.add_instance(ts1)
    lp.add_instance(ts2)

    if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith(
        "vb"
    ):
        lp.ports.append(["outoutput1", "outoutput2", "outsource1", "outsource2"])
    else:
        lp.ports.append(["inner_output", "innersouce"])

    lp = connectInstanceTerminalsOfFourTransistorLoadPart(lp, ts1, ts2)
    return lp


def createFourTransistorLoadPartsMixed(
    twoTransistorVoltageBiases, twoTransistorCurrentBiases
):
    out = []
    for voltageBias in twoTransistorVoltageBiases:
        for currentBias in twoTransistorCurrentBiases:
            # fmt: on
            ts1 = createTransistorStack(1, voltageBias)
            ts2 = createTransistorStack(2, currentBias)
            loadpart = createFourTransistorLoadPart(ts1, ts2)
            out.append(loadpart)
    return out


def createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases):
    out = []
    for voltageBias in twoTransistorVoltageBiases:
        ts1 = createTransistorStack(1, voltageBias)
        ts2 = createTransistorStack(2, voltageBias)
        loadpart = createFourTransistorLoadPart(ts1, ts2)
        out.append(loadpart)
    return out


def createTwoTransistorLoadPartsCurrentBiasesDifferentSources(
    oneTransistorCurrentBiases,
):
    out = []
    for currentBias in oneTransistorCurrentBiases:
        ts1 = createTransistorStack(1, currentBias)
        ts2 = createTransistorStack(2, currentBias)
        loadpart = createTwoTransistorLoadPartDifferentSources(ts1, ts2)
        out.append(loadpart)
    return out


def createFourTransistorLoadPartsCurrentBiases(twoTransistorCurrentBiases):
    out = []
    for currentBias in twoTransistorCurrentBiases:
        ts1 = createTransistorStack(1, currentBias)
        ts2 = createTransistorStack(2, currentBias)

        loadpart = createFourTransistorLoadPart(ts1, ts2)
        out.append(loadpart)
    return out


def createTwoTransistorLoadPartsCurrentBiases(oneTransistorCurrentBiases):
    out = []
    for currentBias in oneTransistorCurrentBiases:
        ts1 = createTransistorStack(1, currentBias)
        ts2 = createTransistorStack(2, currentBias)

        loadpart = createTwoTransistorLoadPart(ts1, ts2)
        out.append(loadpart)
    return out


class LoadPartManager:

    # case 1
    def createTwoTransistorsLoadPartsLoadPartsPmosVoltageBiases(self):
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesPmos()
        )
        loadParts = createTwoTransistorLoadPartsVoltageBiases(
            oneTransistorVoltageBiases
        )
        return loadParts

    # case 2
    def createFourTransistorsLoadPartsLoadPartsPmosVoltageBiases(self):
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        )

        return createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    # case 3
    def createFourTransistorsLoadPartsLoadPartsNmosVoltageBiases(self):
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        )

        return createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    # case 4
    def createTwoTransistorsLoadPartsLoadPartsNmosVoltageBiases(self):
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
        )
        loadParts = createTwoTransistorLoadPartsVoltageBiases(
            oneTransistorVoltageBiases
        )
        return loadParts

    # case 5
    def createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources(self):
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        )
        loadParts = createTwoTransistorLoadPartsCurrentBiasesDifferentSources(
            oneTransistorCurrentBiases
        )
        return loadParts

    # case 6
    def createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources(self):
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        )
        loadParts = createTwoTransistorLoadPartsCurrentBiasesDifferentSources(
            oneTransistorCurrentBiases
        )
        return loadParts

    # case 7
    def createLoadPartsPmosFourTransistorCurrentBiases(self):
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        )
        loadParts = createFourTransistorLoadPartsCurrentBiases(
            twoTransistorCurrentBiases
        )
        return loadParts

    # case 8
    def createLoadPartsNmosFourTransistorCurrentBiases(self):
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        )
        loadParts = createFourTransistorLoadPartsCurrentBiases(
            twoTransistorCurrentBiases
        )
        return loadParts

    # case 9
    def createLoadPartsPmosCurrentBiases(self):
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        )
        return createTwoTransistorLoadPartsCurrentBiases(
            oneTransistorCurrentBiases
        ) + createFourTransistorLoadPartsCurrentBiases(twoTransistorCurrentBiases)

    # case 10
    def createLoadPartsNmosCurrentBiases(self):
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        )
        return createTwoTransistorLoadPartsCurrentBiases(
            oneTransistorCurrentBiases
        ) + createFourTransistorLoadPartsCurrentBiases(twoTransistorCurrentBiases)

    def createLoadPartsPmosVoltageBiases(self):
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesPmos()
        )
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        )
        return createTwoTransistorLoadPartsVoltageBiases(
            oneTransistorVoltageBiases
        ) + createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    def createLoadPartsNmosVoltageBiases(self):
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
        )
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        )
        return createTwoTransistorLoadPartsVoltageBiases(
            oneTransistorVoltageBiases
        ) + createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    def createLoadPartsPmosMixed(self):
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesPmos()
        )
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        )
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        )
        return (
            createTwoTransistorLoadPartsMixed(
                oneTransistorVoltageBiases, oneTransistorCurrentBiases
            )
            + createThreeTransistorLoadPartsMixed(
                oneTransistorVoltageBiases, twoTransistorCurrentBiases
            )
            + createFourTransistorLoadPartsMixed(
                twoTransistorVoltageBiases, twoTransistorCurrentBiases
            )
        )

    def createLoadPartsNmosMixed(self):
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
        )
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        )
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        )
        return (
            createTwoTransistorLoadPartsMixed(
                oneTransistorVoltageBiases, oneTransistorCurrentBiases
            )
            + createThreeTransistorLoadPartsMixed(
                oneTransistorVoltageBiases, twoTransistorCurrentBiases
            )
            + createFourTransistorLoadPartsMixed(
                twoTransistorVoltageBiases, twoTransistorCurrentBiases
            )
        )

    def createLoadPartsPmosFourTransistorMixed(self):
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        )
        return createFourTransistorLoadPartsMixed(
            twoTransistorVoltageBiases, twoTransistorCurrentBiases
        )

    def createLoadPartsNmosFourTransistorMixed(self):
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        )
        return createFourTransistorLoadPartsMixed(
            twoTransistorVoltageBiases, twoTransistorCurrentBiases
        )


def print_json(data):
    print(json.dumps(data, indent=4))
    print("length: ", len(data))


def print_json_v2(data: list, print_graphviz=False):
    for d in data:
        if print_graphviz:
            print(d.graphviz())
    print(f"# numbers: {len(data)}")


create_methods = [
    "createTwoTransistorsLoadPartsLoadPartsPmosVoltageBiases",
    "createFourTransistorsLoadPartsLoadPartsPmosVoltageBiases",
    "createTwoTransistorsLoadPartsLoadPartsNmosVoltageBiases",
    "createFourTransistorsLoadPartsLoadPartsNmosVoltageBiases",
    "createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources",
    "createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources",
    "createLoadPartsPmosFourTransistorCurrentBiases",
    "createLoadPartsNmosFourTransistorCurrentBiases",
    "createLoadPartsPmosCurrentBiases",
    "createLoadPartsNmosCurrentBiases",
    "createLoadPartsPmosVoltageBiases",
    "createLoadPartsNmosVoltageBiases",
    "createLoadPartsPmosMixed",
    "createLoadPartsNmosMixed",
    "createLoadPartsPmosFourTransistorMixed",
    "createLoadPartsNmosFourTransistorMixed",
]

if __name__ == "__main__":

    lp_mng = LoadPartManager()
    for case_id, method in enumerate(create_methods):
        for circuit_id, circuit in enumerate(getattr(lp_mng, method)()):
            if circuit != None:
                save_graphviz_figure(
                    circuit, filename=GALLERY_DOT_DIR/ f"lp_{case_id}_{circuit_id}.dot"
                )
                convert_dot_to_png(
                    GALLERY_DOT_DIR/ f"lp_{case_id}_{circuit_id}.dot", GALLERY_IMAGE_DIR/ f"lp_{case_id}_{circuit_id}.png"
                )
            else:
                logger.warning(f"circuit is None for {method} - {case_id}-{circuit_id}")
                exit(1)
