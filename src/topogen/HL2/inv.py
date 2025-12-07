import jsbeautifier
from src.topogen.common.circuit import *

from src.topogen.HL2.cb import CurrentBiasManager

cb_mng = CurrentBiasManager()

inv1 = Inverter(techtype="?", id=1)
inv1.ports = [
    "inCurrentBiasNmos",
    "inCurrentBiasPmos",
    "output",
    "sourceCurrentBiasNmos",
    "sourceCurrentBiasPmos",
]

inv1.add_instance(cb_mng.getAllCurrentBiasesNmos()[0])
inv1.add_connection_xxx(port="inCurrentBiasNmos", instance_id=0, instance_port="in")
inv1.add_connection_xxx(port="output", instance_id=0, instance_port="out")
inv1.add_connection_xxx(
    port="sourceCurrentBiasNmos", instance_id=0, instance_port="source"
)

inv1.add_instance(cb_mng.getAllCurrentBiasesPmos()[0])
inv1.add_connection_xxx(port="inCurrentBiasNmos", instance_id=1, instance_port="in")
inv1.add_connection_xxx(port="output", instance_id=1, instance_port="out")
inv1.add_connection_xxx(
    port="sourceCurrentBiasPmos", instance_id=1, instance_port="source"
)

# -----------------

inv2 = Inverter(techtype="?", id=2)
inv2.ports = [
    "inCurrentBiasPmos",
    "inOutputCurrentBiasNmos",
    "inSourceCurrentBiasNmos",
    "innerCurrentBiasNmos",
    "output",
    "sourceCurrentBiasNmos",
    "sourceCurrentBiasPmos",
]

inv2.add_instance(cb_mng.getAllCurrentBiasesNmos()[1])
inv2.add_connection_xxx("output", 0, "out")
inv2.add_connection_xxx("sourceCurrentBiasNmos", 0, "source")
inv2.add_connection_xxx("inOutputCurrentBiasNmos", 0, "inOutput")
inv2.add_connection_xxx("inSourceCurrentBiasNmos", 0, "inSource")
inv2.add_connection_xxx("innerCurrentBiasNmos", 0, "inner")


inv2.add_instance(cb_mng.getAllCurrentBiasesPmos()[0])
inv2.add_connection_xxx("inCurrentBiasNmos", 1, "in")
inv2.add_connection_xxx("output", 1, "out")
inv2.add_connection_xxx("sourceCurrentBiasPmos", 1, "inOutput")
# -----------------

inv3 = Inverter(techtype="?", id=3)
inv3.ports = [
    "inCurrentBiasPmos",
    "inOutputCurrentBiasNmos",
    "inSourceCurrentBiasNmos",
    "innerCurrentBiasNmos",
    "output",
    "sourceCurrentBiasNmos",
    "sourceCurrentBiasPmos",
]

inv3.add_instance(cb_mng.getAllCurrentBiasesNmos()[2])
inv3.add_connection_xxx("output", 0, "out")
inv3.add_connection_xxx("sourceCurrentBiasNmos", 0, "source")
inv3.add_connection_xxx("inOutputCurrentBiasNmos", 0, "inOutput")
inv3.add_connection_xxx("inSourceCurrentBiasNmos", 0, "inSource")
inv3.add_connection_xxx("innerCurrentBiasNmos", 0, "inner")


inv3.add_instance(cb_mng.getAllCurrentBiasesPmos()[0])
inv3.add_connection_xxx("inCurrentBiasNmos", 1, "in")
inv3.add_connection_xxx("output", 1, "out")
inv3.add_connection_xxx("sourceCurrentBiasPmos", 1, "inOutput")


# --------------------

inv4 = Inverter(techtype="?", id=4)
inv4.ports = [
    "inCurrentBiasNmos",
    "inOutputCurrentBiasPmos",
    "inSourceCurrentBiasPmos",
    "innerCurrentBiasPmos",
    "output",
    "sourceCurrentBiasNmos",
    "sourceCurrentBiasPmos",
]

inv4.add_instance(cb_mng.getAllCurrentBiasesNmos()[0])
inv4.add_connection_xxx("inCurrentBiasNmos", 0, "in")
inv4.add_connection_xxx("output", 0, "out")
inv4.add_connection_xxx("sourceCurrentBiasNmos", 0, "source")


inv4.add_instance(cb_mng.getAllCurrentBiasesPmos()[1])
inv4.add_connection_xxx("output", 1, "out")
inv4.add_connection_xxx("sourceCurrentBiasPmos", 1, "source")
inv4.add_connection_xxx("inOutputCurrentBiasPmos", 1, "inOutput")
inv4.add_connection_xxx("inSourceCurrentBiasPmos", 1, "inSource")
inv4.add_connection_xxx("innerCurrentBiasPmos", 1, "inner")


# --------------------

inv5 = Inverter(techtype="?", id=5)
inv5.ports = [
    "inOutputCurrentBiasNmos",
    "inOutputCurrentBiasPmos",
    "inSourceCurrentBiasNmos",
    "inSourceCurrentBiasPmos",
    "innerCurrentBiasNmos",
    "innerCurrentBiasPmos",
    "output",
    "sourceCurrentBiasNmos",
    "sourceCurrentBiasPmos",
]

inv5.add_instance(cb_mng.getAllCurrentBiasesNmos()[1])
inv5.add_connection_xxx("output", 0, "out")
inv5.add_connection_xxx("sourceCurrentBiasNmos", 0, "source")
inv5.add_connection_xxx("inOutputCurrentBiasNmos", 0, "inOutput")
inv5.add_connection_xxx("inSourceCurrentBiasNmos", 0, "inSource")
inv5.add_connection_xxx("innerCurrentBiasNmos", 0, "inner")


inv5.add_instance(cb_mng.getAllCurrentBiasesPmos()[1])
inv5.add_connection_xxx("output", 1, "out")
inv5.add_connection_xxx("sourceCurrentBiasPmos", 1, "source")
inv5.add_connection_xxx("inOutputCurrentBiasPmos", 1, "inOutput")
inv5.add_connection_xxx("inSourceCurrentBiasPmos", 1, "inSource")
inv5.add_connection_xxx("innerCurrentBiasPmos", 1, "inner")

# --------------------

inv6 = Inverter(techtype="?", id=6)
inv6.ports = [
    "inOutputCurrentBiasNmos",
    "inOutputCurrentBiasPmos",
    "inSourceCurrentBiasNmos",
    "inSourceCurrentBiasPmos",
    "innerCurrentBiasNmos",
    "innerCurrentBiasPmos",
    "output",
    "sourceCurrentBiasNmos",
    "sourceCurrentBiasPmos",
]

inv6.add_instance(cb_mng.getAllCurrentBiasesNmos()[2])
inv6.add_connection_xxx("output", 0, "out")
inv6.add_connection_xxx("sourceCurrentBiasNmos", 0, "source")
inv6.add_connection_xxx("inOutputCurrentBiasNmos", 0, "inOutput")
inv6.add_connection_xxx("inSourceCurrentBiasNmos", 0, "inSource")
inv6.add_connection_xxx("innerCurrentBiasNmos", 0, "inner")


inv6.add_instance(cb_mng.getAllCurrentBiasesPmos()[2])
inv6.add_connection_xxx("output", 1, "out")
inv6.add_connection_xxx("sourceCurrentBiasPmos", 1, "source")
inv6.add_connection_xxx("inOutputCurrentBiasPmos", 1, "inOutput")
inv6.add_connection_xxx("inSourceCurrentBiasPmos", 1, "inSource")
inv6.add_connection_xxx("innerCurrentBiasPmos", 1, "inner")


# --------------------

inv7 = Inverter(techtype="?", id=7)
inv7.ports = [
    "inCurrentBiasNmos",
    "inOutputCurrentBiasPmos",
    "inSourceCurrentBiasPmos",
    "innerCurrentBiasPmos",
    "output",
    "sourceCurrentBiasNmos",
    "sourceCurrentBiasPmos",
]

inv7.add_instance(cb_mng.getAllCurrentBiasesNmos()[0])
inv7.add_connection_xxx("inCurrentBiasNmos", 0, "in")
inv7.add_connection_xxx("output", 0, "out")
inv7.add_connection_xxx("sourceCurrentBiasNmos", 0, "source")


inv7.add_instance(cb_mng.getAllCurrentBiasesPmos()[1])
inv7.add_connection_xxx("output", 1, "out")
inv7.add_connection_xxx("sourceCurrentBiasPmos", 1, "source")
inv7.add_connection_xxx("inOutputCurrentBiasPmos", 1, "inOutput")
inv7.add_connection_xxx("inSourceCurrentBiasPmos", 1, "inSource")
inv7.add_connection_xxx("innerCurrentBiasPmos", 1, "inner")


# --------------------

inv8 = Inverter(techtype="?", id=8)
inv8.ports = [
    "inOutputCurrentBiasNmos",
    "inOutputCurrentBiasPmos",
    "inSourceCurrentBiasNmos",
    "inSourceCurrentBiasPmos",
    "innerCurrentBiasNmos",
    "innerCurrentBiasPmos",
    "output",
    "sourceCurrentBiasNmos",
    "sourceCurrentBiasPmos",
]

inv8.add_instance(cb_mng.getAllCurrentBiasesNmos()[2])
inv8.add_connection_xxx("output", 0, "out")
inv8.add_connection_xxx("sourceCurrentBiasNmos", 0, "source")
inv8.add_connection_xxx("inOutputCurrentBiasNmos", 0, "inOutput")
inv8.add_connection_xxx("inSourceCurrentBiasNmos", 0, "inSource")
inv8.add_connection_xxx("innerCurrentBiasNmos", 0, "inner")


inv8.add_instance(cb_mng.getAllCurrentBiasesPmos()[2])
inv8.add_connection_xxx("output", 1, "out")
inv8.add_connection_xxx("sourceCurrentBiasPmos", 1, "source")
inv8.add_connection_xxx("inOutputCurrentBiasPmos", 1, "inOutput")
inv8.add_connection_xxx("inSourceCurrentBiasPmos", 1, "inSource")
inv8.add_connection_xxx("innerCurrentBiasPmos", 1, "inner")


class InverterManager:
    def getAllInverters(self):
        return [inv1, inv2, inv3, inv4, inv5, inv6, inv7, inv8]
