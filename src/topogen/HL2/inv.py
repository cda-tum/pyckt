from typing import Iterator

from topogen.common.circuit import *
from topogen.HL2.cb import CurrentBiasManager

cb_mng = CurrentBiasManager()


class InverterManager:
    """Enumerate analog inverters built from every PMOS/NMOS current-bias pairing.

    An *analog inverter* here is a PMOS current bias stacked on an NMOS
    current bias, sharing a common ``OUTPUT`` drain node — the classic
    push-pull inverting stage used as HL3/HL4 building block.
    """

    def __init__(self):
        """Build and cache every PMOS x NMOS current-bias inverter combination."""
        self.analogInverters_ = list(self.initializeAnalogInverters())

    def getAnalogInverters(self):
        """Return the cached list of generated :class:`Inverter` circuits."""
        return self.analogInverters_

    def initializeAnalogInverters(self) -> Iterator[Inverter]:
        """Yield one :class:`Inverter` per valid PMOS/NMOS current-bias pairing.

        Iterates the full cross-product of
        :meth:`~topogen.HL2.cb.CurrentBiasManager.getAllCurrentBiasesPmos` x
        :meth:`~topogen.HL2.cb.CurrentBiasManager.getAllCurrentBiasesNmos`,
        skipping two-transistor/two-transistor combinations where neither side
        has exactly one free (non-drain-connected) gate net — those would
        produce a degenerate inverter with no usable input.
        """
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
        """Build one :class:`Inverter` from a PMOS and an NMOS current bias.

        Adds an ``IN_*``/``INSOURCE_*``/``INOUTPUT_*``/``INNER_*`` port set per
        side depending on whether that side's current bias is a one- or
        two-transistor stack (``component_count``), then wires both instances
        in via :meth:`connectInstanceTerminals`.
        """
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
        """Wire the PMOS/NMOS current-bias instances' pins to *inv*'s ports.

        Both ``OUT`` pins tie to the shared ``Inverter.OUTPUT``; each side's
        ``SOURCE`` and (depending on ``component_count``) either its single
        ``IN`` pin or its ``INSOURCE``/``INOUTPUT``/``INNER`` triple are
        connected to the matching ports added in
        :meth:`createNewAnalogInverter`.
        """
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
