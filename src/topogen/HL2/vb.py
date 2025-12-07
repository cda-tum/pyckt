import jsbeautifier
from src.topogen.common.circuit import *


vb_p_1 = VoltageBias(techtype="p", id=1)
vb_p_1.ports = ["in", "out", "source"]
vb_p_1.add_instance(NormalTransistor(techtype="p"))
vb_p_1.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_p_1.add_connection_xxx(port="out", instance_id=0, instance_port="gate")
vb_p_1.add_connection_xxx(port="source", instance_id=0, instance_port="source")


vb_p_2 = VoltageBias(techtype="p", id=2)
vb_p_2.ports = ["in", "out", "source"]
vb_p_2.add_instance(DiodeTransistor(techtype="p"))
vb_p_2.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_p_2.add_connection_xxx(port="out", instance_id=0, instance_port="gate")
vb_p_2.add_connection_xxx(port="source", instance_id=0, instance_port="source")


vb_p_3 = VoltageBias(techtype="p", id=3)
vb_p_3.ports = ["in", "inner", "outinput", "outsource", "source"]
vb_p_3.add_instance(DiodeTransistor(techtype="p"))
vb_p_3.add_instance(DiodeTransistor(techtype="p", id=2))

vb_p_3.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_p_3.add_connection_xxx(port="inner", instance_id=0, instance_port="source")
vb_p_3.add_connection_xxx(port="inner", instance_id=1, instance_port="drain")
vb_p_3.add_connection_xxx(port="outinput", instance_id=0, instance_port="gate")
vb_p_3.add_connection_xxx(port="outsource", instance_id=1, instance_port="gate")
vb_p_3.add_connection_xxx(port="source", instance_id=1, instance_port="source")


vb_p_4 = VoltageBias(techtype="p", id=4)
# vb_p_4.ports = ["in", "inner", "outinput", "outsource", "source"]
vb_p_4.ports = ["in", "inner", "outinput", "source"]
vb_p_4.add_instance(NormalTransistor(techtype="p"))
vb_p_4.add_instance(NormalTransistor(techtype="p", id=2))

vb_p_4.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_p_4.add_connection_xxx(port="inner", instance_id=0, instance_port="source")
vb_p_4.add_connection_xxx(port="inner", instance_id=1, instance_port="drain")
vb_p_4.add_connection_xxx(port="outinput", instance_id=0, instance_port="gate")
# vb_p_4.add_connection_xxx(port="outsource", instance_name="nt.2", instance_port="gate")
vb_p_4.add_connection_xxx(port="source", instance_id=1, instance_port="source")


vb_p_5 = VoltageBias(techtype="p", id=5)
vb_p_5.ports = ["in", "inner", "outinput", "outsource", "source"]
vb_p_5.add_instance(DiodeTransistor(techtype="p"))
vb_p_5.add_instance(NormalTransistor(techtype="p", id=1))

vb_p_5.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_p_5.add_connection_xxx(port="inner", instance_id=0, instance_port="source")
vb_p_5.add_connection_xxx(port="inner", instance_id=1, instance_port="drain")
vb_p_5.add_connection_xxx(port="outinput", instance_id=0, instance_port="gate")
vb_p_5.add_connection_xxx(port="outsource", instance_id=1, instance_port="gate")
vb_p_5.add_connection_xxx(port="source", instance_id=1, instance_port="source")


vb_p_6 = VoltageBias(techtype="p", id=6)
# vb_p_6.ports = ["in", "inner", "outinput", "outsource", "source"]
vb_p_6.ports = ["in", "inner", "outinput", "source"]

vb_p_6.add_instance(DiodeTransistor(techtype="p"))
vb_p_6.add_instance(NormalTransistor(techtype="p", id=1))

vb_p_6.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_p_6.add_connection_xxx(port="inner", instance_id=0, instance_port="source")
vb_p_6.add_connection_xxx(port="inner", instance_id=1, instance_port="drain")
vb_p_6.add_connection_xxx(port="outinput", instance_id=0, instance_port="gate")
# vb_p_6.add_connection_xxx(port="outsource", instance_name="nt.1", instance_port="gate")
vb_p_6.add_connection_xxx(port="source", instance_id=1, instance_port="source")


# ==============================
vb_n_1 = VoltageBias(techtype="n", id=1)
vb_n_1.ports = ["in", "out", "source"]
vb_n_1.add_instance(NormalTransistor(techtype="n"))
vb_n_1.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_n_1.add_connection_xxx(port="out", instance_id=0, instance_port="gate")
vb_n_1.add_connection_xxx(port="source", instance_id=0, instance_port="source")

vb_n_2 = VoltageBias(techtype="n", id=2)
vb_n_2.ports = ["in", "out", "source"]
vb_n_2.add_instance(DiodeTransistor(techtype="n"))
vb_n_2.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_n_2.add_connection_xxx(port="out", instance_id=0, instance_port="gate")
vb_n_2.add_connection_xxx(port="source", instance_id=0, instance_port="source")


vb_n_3 = VoltageBias(techtype="n", id=3)
vb_n_3.ports = ["in", "inner", "outinput", "outsource", "source"]
vb_n_3.add_instance(DiodeTransistor(techtype="n"))
vb_n_3.add_instance(DiodeTransistor(techtype="n", id=2))

vb_n_3.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_n_3.add_connection_xxx(port="inner", instance_id=0, instance_port="source")
vb_n_3.add_connection_xxx(port="inner", instance_id=1, instance_port="drain")
vb_n_3.add_connection_xxx(port="outinput", instance_id=0, instance_port="gate")
vb_n_3.add_connection_xxx(port="outsource", instance_id=1, instance_port="gate")
vb_n_3.add_connection_xxx(port="source", instance_id=1, instance_port="source")


vb_n_4 = VoltageBias(techtype="n", id=4)
vb_n_4.ports = ["in", "inner", "outinput", "outsource", "source"]
vb_n_4.add_instance(NormalTransistor(techtype="n"))
vb_n_4.add_instance(NormalTransistor(techtype="n", id=2))

vb_n_4.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_n_4.add_connection_xxx(port="inner", instance_id=0, instance_port="source")
vb_n_4.add_connection_xxx(port="inner", instance_id=1, instance_port="drain")
vb_n_4.add_connection_xxx(port="outinput", instance_id=0, instance_port="gate")
vb_n_4.add_connection_xxx(port="outsource", instance_id=1, instance_port="gate")
vb_n_4.add_connection_xxx(port="source", instance_id=1, instance_port="source")


vb_n_5 = VoltageBias(techtype="n", id=5)
vb_n_5.ports = ["in", "inner", "outinput", "outsource", "source"]
vb_n_5.add_instance(DiodeTransistor(techtype="n"))
vb_n_5.add_instance(NormalTransistor(techtype="n", id=1))

vb_n_5.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_n_5.add_connection_xxx(port="inner", instance_id=0, instance_port="source")
vb_n_5.add_connection_xxx(port="inner", instance_id=1, instance_port="drain")
vb_n_5.add_connection_xxx(port="outinput", instance_id=0, instance_port="gate")
vb_n_5.add_connection_xxx(port="outsource", instance_id=1, instance_port="gate")
vb_n_5.add_connection_xxx(port="source", instance_id=1, instance_port="source")


vb_n_6 = VoltageBias(techtype="n", id=6)
# vb_n_6.ports = ["in", "inner", "outinput", "outsource", "source"]
vb_n_6.ports = ["in", "inner", "outinput", "source"]
vb_n_6.add_instance(DiodeTransistor(techtype="n"))
vb_n_6.add_instance(NormalTransistor(techtype="n", id=1))

vb_n_6.add_connection_xxx(port="in", instance_id=0, instance_port="drain")
vb_n_6.add_connection_xxx(port="inner", instance_id=0, instance_port="source")
vb_n_6.add_connection_xxx(port="inner", instance_id=1, instance_port="drain")
vb_n_6.add_connection_xxx(port="outinput", instance_id=0, instance_port="gate")
# vb_p_6.add_connection_xxx(port="outsource", instance_name="nt.1", instance_port="gate")
vb_n_6.add_connection_xxx(port="source", instance_id=1, instance_port="source")


class VoltageBiasManager:
    """For voltage bias subcircuit, all transistors in the VB has the same type (NMOS, PMOS)"""

    def getAllVoltageBiasesPmos(self):
        return sorted(
            list(
                set(
                    self.getOneTransistorVoltageBiasesPmos()
                    + self.getTwoTransistorVoltageBiasesPmos()
                    + self.getDiodeTransistorVoltageBiasPmos()
                    + self.getTwoDiodeTransistorVoltageBiasPmos()
                )
            ),
            key=lambda x: x.name + str(x.id),
        )

    def getAllVoltageBiasesNmos(self):
        return sorted(
            list(
                set(
                    self.getOneTransistorVoltageBiasesNmos()
                    + self.getTwoTransistorVoltageBiasesNmos()
                    + self.getDiodeTransistorVoltageBiasNmos()
                    + self.getTwoDiodeTransistorVoltageBiasNmos()
                )
            ),
            key=lambda x: x.name + str(x.id),
        )

    def getOneTransistorVoltageBiasesPmos(self):
        return [vb_p_1, vb_p_2]

    def getTwoTransistorVoltageBiasesPmos(self):
        return [vb_p_3, vb_p_4, vb_p_5, vb_p_6]

    def getOneTransistorVoltageBiasesNmos(self):
        return [vb_n_1, vb_n_2]

    def getTwoTransistorVoltageBiasesNmos(self):
        return [vb_n_3, vb_n_4, vb_n_5, vb_n_6]

    def getDiodeTransistorVoltageBiasNmos(self):
        return [vb_n_2]

    def getDiodeTransistorVoltageBiasPmos(self):
        return [vb_p_2]

    def getTwoDiodeTransistorVoltageBiasNmos(self):
        return [vb_n_3]

    def getTwoDiodeTransistorVoltageBiasPmos(self):
        return [vb_p_3]


if __name__ == "__main__":
    vb_mng = VoltageBiasManager()
    all_vb = vb_mng.getAllVoltageBiasesNmos() + vb_mng.getAllVoltageBiasesPmos()

    for idx, circuit in enumerate(all_vb):
        if circuit != None:
            save_graphviz_figure(circuit, filename=f"gallery/HL2/vb-{idx}.dot")
