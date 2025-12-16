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
    connect,
)

from pathlib import Path
import json

# fmt: off

GALLERY_DOT_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "lp" / "dots"
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "lp" / "images"
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

logger = setup_logger(log_level="DEBUG", log_file=None)


def connectInstanceTerminalsOfTwoTransistorLoadPart(out: LoadPart, ts1, ts2):
    num = 1
    # fmt: off
    for transistorStack in [ts1, ts2]:
        if transistorStack.instances[0].name.startswith("cb"):
            if num == 1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))

            connect((out, LoadPart.INNER), (transistorStack, TransistorStack.IN))
            connect((out, LoadPart.SOURCE), (transistorStack, TransistorStack.SOURCE))

        else:
            if num == 1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.IN))
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.IN))

            if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith("vb"):
                if num == 1:
                    connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))
                else:
                    connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))
            else:
                connect((out, LoadPart.INNER), (transistorStack, TransistorStack.OUT))
            
            connect((out, LoadPart.SOURCE), (transistorStack, TransistorStack.SOURCE))
        num += 1
    # fmt: on
    return out


def connectInstanceTerminalsOfFourTransistorLoadPart(out: LoadPart, ts1, ts2):
    num = 1
    # fmt: off
    for transistorStack in [ts1, ts2]:
        if transistorStack.instances[0].name.startswith("cb"):
            if num==1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))
                connect((out, LoadPart.INNERTRANSISTORSTACK1), (transistorStack, TransistorStack.INNER))

            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))
                connect((out, LoadPart.INNERTRANSISTORSTACK2), (transistorStack, TransistorStack.INNER))

            connect((out, LoadPart.INNEROUTPUT), (transistorStack, TransistorStack.INOUTPUT))
            connect((out, LoadPart.INNERSOURCE), (transistorStack, TransistorStack.INSOURCE))
            connect((out, LoadPart.SOURCE), (transistorStack, TransistorStack.SOURCE))
        else:
            if num==1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.IN))
                connect((out, LoadPart.INNERTRANSISTORSTACK1), (transistorStack, TransistorStack.INNER))
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.IN))
                connect((out, LoadPart.INNERTRANSISTORSTACK2), (transistorStack, TransistorStack.INNER))

            if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith("vb"): 
                if num==1:
                    connect((out, LoadPart.OUTOUTPUT1), (transistorStack, TransistorStack.OUTINPUT))
                    connect((out, LoadPart.OUTSOURCE1), (transistorStack, TransistorStack.OUTSOURCE))
                else:
                    connect((out, LoadPart.OUTOUTPUT2), (transistorStack, TransistorStack.OUTINPUT))
                    connect((out, LoadPart.OUTSOURCE2), (transistorStack, TransistorStack.OUTSOURCE))
            else:
                connect((out, LoadPart.INNEROUTPUT), (transistorStack, TransistorStack.OUTINPUT))
                connect((out, LoadPart.INNERSOURCE), (transistorStack, TransistorStack.OUTSOURCE))

            connect((out, LoadPart.SOURCE), (transistorStack, TransistorStack.SOURCE))   
        
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
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))   
                connect((out, LoadPart.SOURCE1), (transistorStack, TransistorStack.SOURCE))   
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))   
                connect((out, LoadPart.SOURCE2), (transistorStack, TransistorStack.SOURCE))   
            
            connect((out, LoadPart.INNER), (transistorStack, TransistorStack.IN))   
        else:
            if num == 1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.IN))   
                connect((out, LoadPart.SOURCE1), (transistorStack, TransistorStack.SOURCE))   
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.IN))   
                connect((out, LoadPart.SOURCE2), (transistorStack, TransistorStack.SOURCE))   

            if ts1.name == "vb" and ts2.name == "vb":
                if num == 1:
                    connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))   
                else:
                    connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT)) 
            else:
                connect((out, LoadPart.INNER), (transistorStack, TransistorStack.OUT)) 
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
    lp.ports = [LoadPart.OUT1, LoadPart.OUT2, LoadPart.SOURCE]
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
    lp.ports = [LoadPart.OUT1, LoadPart.OUT2, LoadPart.SOURCE1, LoadPart.SOURCE2]
    lp.add_instance(ts1)
    lp.add_instance(ts2)

    if ts1.instances[0].name.startswith("vb") or ts2.instances[0].name.startswith("vb"):
        pass

    lp = connectInstanceTerminalsOfTwoTransistorLoadPartDifferentSources(lp, ts1, ts2)
    return lp


def connectInstanceTerminalsOfThreeTransistorLoadPart(
    out, ts1: TransistorStack, ts2: TransistorStack
):
    
    connect((out, LoadPart.OUT1), (ts1, TransistorStack.IN))
    connect((out, LoadPart.INNERSOURCE), (ts1, TransistorStack.OUT))
    connect((out, LoadPart.SOURCE), (ts1, TransistorStack.SOURCE))

    connect((out, LoadPart.OUT2), (ts2, TransistorStack.OUT))

    if len(ts1.instances) == 1 and ts1.instances[0].name == "dt":
        connect((out, LoadPart.INNEROUTPUT), (ts2, TransistorStack.INOUTPUT))
    else:
        connect((out, LoadPart.OUT1), (ts2, TransistorStack.INOUTPUT))

    connect((out, LoadPart.INNERSOURCE), (ts2, TransistorStack.INSOURCE))
    connect((out, LoadPart.INNERTRANSISTORSTACK2), (ts2, TransistorStack.INNER))
    connect((out, LoadPart.SOURCE), (ts2, TransistorStack.SOURCE))
    return out


def createThreeTransistorLoadPart(ts1: TransistorStack, ts2: TransistorStack):
    lp = LoadPart(id=1, techtype="p")
    lp.ports = [ LoadPart.OUT1, LoadPart.OUT2, LoadPart.SOURCE, LoadPart.INNERTRANSISTORSTACK2, LoadPart.INNERSOURCE]
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
        LoadPart.OUT1,
        LoadPart.OUT2,
        LoadPart.INNERTRANSISTORSTACK1,
        LoadPart.INNERTRANSISTORSTACK2,
        LoadPart.SOURCE
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

    def __init__(self):
        self.initializeLoadPartsPmos()
        self.initializeLoadPartsNmos()

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

    def initializeLoadPartsPmos(self):
        oneTransistorVoltageBiases = VoltageBiasManager().getOneTransistorVoltageBiasesPmos()
        twoTransistorVoltageBiases = VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        # oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        # twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()

        self.twoTransistorsLoadPartsPmosVoltageBiases_ = createTwoTransistorLoadPartsVoltageBiases(oneTransistorVoltageBiases)
        self.fourTransistorsLoadPartsPmosVoltageBiases_ = createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    def initializeLoadPartsNmos(self):
        oneTransistorVoltageBiases = VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
        twoTransistorVoltageBiases = VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        # oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesNmos();
        # twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesNmos();

        self.twoTransistorsLoadPartsNmosVoltageBiases_ = createTwoTransistorLoadPartsVoltageBiases(oneTransistorVoltageBiases)
        self.fourTransistorsLoadPartsNmosVoltageBiases_ = createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    def getLoadPartsPmosVoltageBiases(self):
        assert self.twoTransistorsLoadPartsPmosVoltageBiases_ != None
        assert self.fourTransistorsLoadPartsPmosVoltageBiases_ != None

        return self.twoTransistorsLoadPartsPmosVoltageBiases_ + self.fourTransistorsLoadPartsPmosVoltageBiases_


    def getLoadPartsNmosVoltageBiases(self):
        assert self.twoTransistorsLoadPartsNmosVoltageBiases_ is not None
        assert self.fourTransistorsLoadPartsNmosVoltageBiases_ is not None
        return self.twoTransistorsLoadPartsNmosVoltageBiases_  + self.fourTransistorsLoadPartsNmosVoltageBiases_
       


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
