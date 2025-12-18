from src.topogen.common.circuit import *

from src.topogen.HL2.cb import CurrentBiasManager
from itertools import chain
from typing import Iterator

cb_mng = CurrentBiasManager()


class InverterManager:
    def __init__(self):
        self.analogInverters_ = list(self.initializeAnalogInverters())

    def getAnalogInverters(self):
        return self.analogInverters_

    def initializeAnalogInverters(self) -> Iterator[Inverter]:
        currentBiasesPmos = CurrentBiasManager().getAllCurrentBiasesPmos()
        currentBiasesNmos = CurrentBiasManager().getAllCurrentBiasesNmos()
        for currentBiasPmos in currentBiasesPmos:
            for currentBiasNmos in currentBiasesNmos:
                if (
                    len(currentBiasPmos.instances) == 2
                    and len(currentBiasNmos.instances) == 2
                ):
                    if not (
                        len(currentBiasPmos.getGateNetsNotConnectedToADrain()) == 1
                        and len(currentBiasNmos.getGateNetsNotConnectedToADrain()) == 1
                    ):
                        yield self.createNewAnalogInverter(
                            currentBiasPmos, currentBiasNmos
                        )
                else:
                    yield self.createNewAnalogInverter(currentBiasPmos, currentBiasNmos)

    def createNewAnalogInverter(
        self, currentBiasPmos: CurrentBias, currentBiasNmos: CurrentBias
    ) -> Inverter:
        inv = Inverter(id=1, techtype="undef")
        inv.ports += [
            Inverter.OUTPUT,
            Inverter.SOURCE_CURRENTBIASNMOS,
            Inverter.SOURCE_CURRENTBIASPMOS,
        ]

        if currentBiasPmos.component_count == 2:
            inv.ports += [
                Inverter.INSOURCE_CURRENTBIASPMOS,
                Inverter.INOUTPUT_CURRENTBIASPMOS,
                Inverter.INNER_CURRENTBIASPMOS,
            ]
        else:
            inv.ports += [Inverter.IN_CURRENTBIASPMOS]

        if currentBiasNmos.component_count == 2:
            inv.ports += [
                Inverter.INSOURCE_CURRENTBIASNMOS,
                Inverter.INOUTPUT_CURRENTBIASNMOS,
                Inverter.INNER_CURRENTBIASNMOS,
            ]
        else:
            inv.ports += [Inverter.IN_CURRENTBIASNMOS]
        inv.add_instance(currentBiasPmos)
        inv.add_instance(currentBiasNmos)
        inv = self.connectInstanceTerminals(inv, currentBiasNmos, currentBiasPmos)
        return inv

    def connectInstanceTerminals(
        self,
        inv: Inverter,
        currentBiasNmosInstance: CurrentBias,
        currentBiasPmosInstance: CurrentBias,
    ) -> Inverter:
        # fmt: off
        connect((inv, Inverter.OUTPUT), (currentBiasPmosInstance, CurrentBias.OUT))
        connect((inv, Inverter.OUTPUT), (currentBiasNmosInstance, CurrentBias.OUT))

        connect((inv, Inverter.SOURCE_CURRENTBIASPMOS),(currentBiasPmosInstance, CurrentBias.SOURCE))
        connect((inv, Inverter.SOURCE_CURRENTBIASNMOS),(currentBiasNmosInstance, CurrentBias.SOURCE))

        if currentBiasPmosInstance.component_count == 2:
            connect((inv, Inverter.INSOURCE_CURRENTBIASPMOS),(currentBiasPmosInstance, CurrentBias.INSOURCE))
            connect((inv, Inverter.INOUTPUT_CURRENTBIASPMOS),(currentBiasPmosInstance, CurrentBias.INOUTPUT))
            connect((inv, Inverter.INNER_CURRENTBIASPMOS),(currentBiasPmosInstance, CurrentBias.INNER))
        elif currentBiasPmosInstance.component_count == 1:
            connect((inv, Inverter.IN_CURRENTBIASPMOS),(currentBiasPmosInstance, CurrentBias.IN))

        if currentBiasNmosInstance.component_count == 2:
            connect((inv, Inverter.INSOURCE_CURRENTBIASNMOS),(currentBiasNmosInstance, CurrentBias.INSOURCE))
            connect((inv, Inverter.INOUTPUT_CURRENTBIASNMOS),(currentBiasNmosInstance, CurrentBias.INOUTPUT))
            connect((inv, Inverter.INNER_CURRENTBIASNMOS),(currentBiasNmosInstance, CurrentBias.INNER))
        else:
            connect((inv, Inverter.IN_CURRENTBIASNMOS),(currentBiasNmosInstance, CurrentBias.IN))
        return inv
