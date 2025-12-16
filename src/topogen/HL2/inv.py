from src.topogen.common.circuit import *

from src.topogen.HL2.cb import CurrentBiasManager

cb_mng = CurrentBiasManager()

inv1 = Inverter(techtype="?", id=1)
inv1.ports = [
    Inverter.IN_CURRENTBIASNMOS,
    Inverter.IN_CURRENTBIASPMOS,
    Inverter.OUTPUT,
    Inverter.SOURCE_CURRENTBIASNMOS,
    Inverter.SOURCE_CURRENTBIASPMOS,
]

inv1.add_instance(cb_mng.getAllCurrentBiasesNmos()[0])
inv1.add_connection_xxx(
    port=Inverter.IN_CURRENTBIASNMOS, instance_id=0, instance_port=CurrentBias.IN
)
inv1.add_connection_xxx(
    port=Inverter.OUTPUT, instance_id=0, instance_port=CurrentBias.OUT
)
inv1.add_connection_xxx(
    port=Inverter.SOURCE_CURRENTBIASNMOS,
    instance_id=0,
    instance_port=CurrentBias.SOURCE,
)

inv1.add_instance(cb_mng.getAllCurrentBiasesPmos()[0])
inv1.add_connection_xxx(
    port=Inverter.IN_CURRENTBIASNMOS, instance_id=1, instance_port=CurrentBias.IN
)
inv1.add_connection_xxx(
    port=Inverter.OUTPUT, instance_id=1, instance_port=CurrentBias.OUT
)
inv1.add_connection_xxx(
    port=Inverter.SOURCE_CURRENTBIASPMOS,
    instance_id=1,
    instance_port=CurrentBias.SOURCE,
)

# -----------------

inv2 = Inverter(techtype="?", id=2)
inv2.ports = [
    Inverter.IN_CURRENTBIASPMOS,
    Inverter.INOUTPUT_CURRENTBIASNMOS,
    Inverter.INSOURCE_CURRENTBIASNMOS,
    Inverter.INNER_CURRENTBIASNMOS,
    Inverter.OUTPUT,
    Inverter.SOURCE_CURRENTBIASNMOS,
    Inverter.SOURCE_CURRENTBIASPMOS,
]

inv2.add_instance(cb_mng.getAllCurrentBiasesNmos()[1])
inv2.add_connection_xxx(Inverter.OUTPUT, 0, CurrentBias.OUT)
inv2.add_connection_xxx(Inverter.SOURCE_CURRENTBIASNMOS, 0, CurrentBias.SOURCE)
inv2.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASNMOS, 0, CurrentBias.INOUTPUT)
inv2.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASNMOS, 0, CurrentBias.INSOURCE)
inv2.add_connection_xxx(Inverter.INNER_CURRENTBIASNMOS, 0, CurrentBias.INNER)


inv2.add_instance(cb_mng.getAllCurrentBiasesPmos()[0])
inv2.add_connection_xxx(Inverter.IN_CURRENTBIASNMOS, 1, CurrentBias.IN)
inv2.add_connection_xxx(Inverter.OUTPUT, 1, CurrentBias.OUT)
inv2.add_connection_xxx(Inverter.SOURCE_CURRENTBIASPMOS, 1, CurrentBias.INOUTPUT)
# -----------------

inv3 = Inverter(techtype="?", id=3)
inv3.ports = [
    Inverter.IN_CURRENTBIASPMOS,
    Inverter.INOUTPUT_CURRENTBIASNMOS,
    Inverter.INSOURCE_CURRENTBIASNMOS,
    Inverter.INNER_CURRENTBIASNMOS,
    Inverter.OUTPUT,
    Inverter.SOURCE_CURRENTBIASNMOS,
    Inverter.SOURCE_CURRENTBIASPMOS,
]

inv3.add_instance(cb_mng.getAllCurrentBiasesNmos()[2])
inv3.add_connection_xxx(Inverter.OUTPUT, 0, CurrentBias.OUT)
inv3.add_connection_xxx(Inverter.SOURCE_CURRENTBIASNMOS, 0, CurrentBias.SOURCE)
inv3.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASNMOS, 0, CurrentBias.INOUTPUT)
inv3.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASNMOS, 0, CurrentBias.INSOURCE)
inv3.add_connection_xxx(Inverter.INNER_CURRENTBIASNMOS, 0, CurrentBias.INNER)


inv3.add_instance(cb_mng.getAllCurrentBiasesPmos()[0])
inv3.add_connection_xxx(Inverter.IN_CURRENTBIASNMOS, 1, CurrentBias.IN)
inv3.add_connection_xxx(Inverter.OUTPUT, 1, CurrentBias.OUT)
inv3.add_connection_xxx(Inverter.SOURCE_CURRENTBIASPMOS, 1, CurrentBias.INOUTPUT)


# --------------------

inv4 = Inverter(techtype="?", id=4)
inv4.ports = [
    Inverter.IN_CURRENTBIASNMOS,
    Inverter.INOUTPUT_CURRENTBIASPMOS,
    Inverter.INSOURCE_CURRENTBIASPMOS,
    Inverter.INNER_CURRENTBIASPMOS,
    Inverter.OUTPUT,
    Inverter.SOURCE_CURRENTBIASNMOS,
    Inverter.SOURCE_CURRENTBIASPMOS,
]

inv4.add_instance(cb_mng.getAllCurrentBiasesNmos()[0])
inv4.add_connection_xxx(Inverter.IN_CURRENTBIASNMOS, 0, CurrentBias.IN)
inv4.add_connection_xxx(Inverter.OUTPUT, 0, CurrentBias.OUT)
inv4.add_connection_xxx(Inverter.SOURCE_CURRENTBIASNMOS, 0, CurrentBias.SOURCE)


inv4.add_instance(cb_mng.getAllCurrentBiasesPmos()[1])
inv4.add_connection_xxx(Inverter.OUTPUT, 1, CurrentBias.OUT)
inv4.add_connection_xxx(Inverter.SOURCE_CURRENTBIASPMOS, 1, CurrentBias.SOURCE)
inv4.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASPMOS, 1, CurrentBias.INOUTPUT)
inv4.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASPMOS, 1, CurrentBias.INSOURCE)
inv4.add_connection_xxx(Inverter.INNER_CURRENTBIASPMOS, 1, CurrentBias.INNER)


# --------------------

inv5 = Inverter(techtype="?", id=5)
inv5.ports = [
    Inverter.INOUTPUT_CURRENTBIASNMOS,
    Inverter.INOUTPUT_CURRENTBIASPMOS,
    Inverter.INSOURCE_CURRENTBIASNMOS,
    Inverter.INSOURCE_CURRENTBIASPMOS,
    Inverter.INNER_CURRENTBIASNMOS,
    Inverter.INNER_CURRENTBIASPMOS,
    Inverter.OUTPUT,
    Inverter.SOURCE_CURRENTBIASNMOS,
    Inverter.SOURCE_CURRENTBIASPMOS,
]

inv5.add_instance(cb_mng.getAllCurrentBiasesNmos()[1])
inv5.add_connection_xxx(Inverter.OUTPUT, 0, CurrentBias.OUT)
inv5.add_connection_xxx(Inverter.SOURCE_CURRENTBIASNMOS, 0, CurrentBias.SOURCE)
inv5.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASNMOS, 0, CurrentBias.INOUTPUT)
inv5.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASNMOS, 0, CurrentBias.INSOURCE)
inv5.add_connection_xxx(Inverter.INNER_CURRENTBIASNMOS, 0, CurrentBias.INNER)


inv5.add_instance(cb_mng.getAllCurrentBiasesPmos()[1])
inv5.add_connection_xxx(Inverter.OUTPUT, 1, CurrentBias.OUT)
inv5.add_connection_xxx(Inverter.SOURCE_CURRENTBIASPMOS, 1, CurrentBias.SOURCE)
inv5.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASPMOS, 1, CurrentBias.INOUTPUT)
inv5.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASPMOS, 1, CurrentBias.INSOURCE)
inv5.add_connection_xxx(Inverter.INNER_CURRENTBIASPMOS, 1, CurrentBias.INNER)

# --------------------

inv6 = Inverter(techtype="?", id=6)
inv6.ports = [
    Inverter.INOUTPUT_CURRENTBIASNMOS,
    Inverter.INOUTPUT_CURRENTBIASPMOS,
    Inverter.INSOURCE_CURRENTBIASNMOS,
    Inverter.INSOURCE_CURRENTBIASPMOS,
    Inverter.INNER_CURRENTBIASNMOS,
    Inverter.INNER_CURRENTBIASPMOS,
    Inverter.OUTPUT,
    Inverter.SOURCE_CURRENTBIASNMOS,
    Inverter.SOURCE_CURRENTBIASPMOS,
]

inv6.add_instance(cb_mng.getAllCurrentBiasesNmos()[2])
inv6.add_connection_xxx(Inverter.OUTPUT, 0, CurrentBias.OUT)
inv6.add_connection_xxx(Inverter.SOURCE_CURRENTBIASNMOS, 0, CurrentBias.SOURCE)
inv6.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASNMOS, 0, CurrentBias.INOUTPUT)
inv6.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASNMOS, 0, CurrentBias.INSOURCE)
inv6.add_connection_xxx(Inverter.INNER_CURRENTBIASNMOS, 0, CurrentBias.INNER)


inv6.add_instance(cb_mng.getAllCurrentBiasesPmos()[2])
inv6.add_connection_xxx(Inverter.OUTPUT, 1, CurrentBias.OUT)
inv6.add_connection_xxx(Inverter.SOURCE_CURRENTBIASPMOS, 1, CurrentBias.SOURCE)
inv6.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASPMOS, 1, CurrentBias.INOUTPUT)
inv6.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASPMOS, 1, CurrentBias.INSOURCE)
inv6.add_connection_xxx(Inverter.INNER_CURRENTBIASPMOS, 1, CurrentBias.INNER)


# --------------------

inv7 = Inverter(techtype="?", id=7)
inv7.ports = [
    Inverter.IN_CURRENTBIASNMOS,
    Inverter.INOUTPUT_CURRENTBIASPMOS,
    Inverter.INSOURCE_CURRENTBIASPMOS,
    Inverter.INNER_CURRENTBIASPMOS,
    Inverter.OUTPUT,
    Inverter.SOURCE_CURRENTBIASNMOS,
    Inverter.SOURCE_CURRENTBIASPMOS,
]

inv7.add_instance(cb_mng.getAllCurrentBiasesNmos()[0])
inv7.add_connection_xxx(Inverter.IN_CURRENTBIASNMOS, 0, CurrentBias.IN)
inv7.add_connection_xxx(Inverter.OUTPUT, 0, CurrentBias.OUT)
inv7.add_connection_xxx(Inverter.SOURCE_CURRENTBIASNMOS, 0, CurrentBias.SOURCE)


inv7.add_instance(cb_mng.getAllCurrentBiasesPmos()[1])
inv7.add_connection_xxx(Inverter.OUTPUT, 1, CurrentBias.OUT)
inv7.add_connection_xxx(Inverter.SOURCE_CURRENTBIASPMOS, 1, CurrentBias.SOURCE)
inv7.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASPMOS, 1, CurrentBias.INOUTPUT)
inv7.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASPMOS, 1, CurrentBias.INSOURCE)
inv7.add_connection_xxx(Inverter.INNER_CURRENTBIASPMOS, 1, CurrentBias.INNER)


# --------------------

inv8 = Inverter(techtype="?", id=8)
inv8.ports = [
    Inverter.INOUTPUT_CURRENTBIASNMOS,
    Inverter.INOUTPUT_CURRENTBIASPMOS,
    Inverter.INSOURCE_CURRENTBIASNMOS,
    Inverter.INSOURCE_CURRENTBIASPMOS,
    Inverter.INNER_CURRENTBIASNMOS,
    Inverter.INNER_CURRENTBIASPMOS,
    Inverter.OUTPUT,
    Inverter.SOURCE_CURRENTBIASNMOS,
    Inverter.SOURCE_CURRENTBIASPMOS,
]

inv8.add_instance(cb_mng.getAllCurrentBiasesNmos()[2])
inv8.add_connection_xxx(Inverter.OUTPUT, 0, CurrentBias.OUT)
inv8.add_connection_xxx(Inverter.SOURCE_CURRENTBIASNMOS, 0, CurrentBias.SOURCE)
inv8.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASNMOS, 0, CurrentBias.INOUTPUT)
inv8.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASNMOS, 0, CurrentBias.INSOURCE)
inv8.add_connection_xxx(Inverter.INNER_CURRENTBIASNMOS, 0, CurrentBias.INNER)


inv8.add_instance(cb_mng.getAllCurrentBiasesPmos()[2])
inv8.add_connection_xxx(Inverter.OUTPUT, 1, CurrentBias.OUT)
inv8.add_connection_xxx(Inverter.SOURCE_CURRENTBIASPMOS, 1, CurrentBias.SOURCE)
inv8.add_connection_xxx(Inverter.INOUTPUT_CURRENTBIASPMOS, 1, CurrentBias.INOUTPUT)
inv8.add_connection_xxx(Inverter.INSOURCE_CURRENTBIASPMOS, 1, CurrentBias.INSOURCE)
inv8.add_connection_xxx(Inverter.INNER_CURRENTBIASPMOS, 1, CurrentBias.INNER)


class InverterManager:
    def getAllInverters(self):
        return [inv1, inv2, inv3, inv4, inv5, inv6, inv7, inv8]
