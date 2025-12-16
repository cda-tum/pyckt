from src.topogen.common.circuit import *


cb_p_1 = CurrentBias(techtype="p", id=1)
cb_p_1.ports = [CurrentBias.IN, CurrentBias.OUT, CurrentBias.SOURCE]
cb_p_1.add_instance(NormalTransistor(techtype="p"))
cb_p_1.add_connection_xxx(port=CurrentBias.IN, instance_id=0, instance_port="drain")
cb_p_1.add_connection_xxx(port=CurrentBias.OUT, instance_id=0, instance_port="gate")
cb_p_1.add_connection_xxx(
    port=CurrentBias.SOURCE, instance_id=0, instance_port="source"
)


cb_p_2 = CurrentBias(techtype="p", id=2)
cb_p_2.ports = [
    CurrentBias.OUT,
    CurrentBias.SOURCE,
    CurrentBias.INOUTPUT,
    CurrentBias.INSOURCE,
    CurrentBias.INNER,
]
cb_p_2.add_instance(NormalTransistor(techtype="p"))
cb_p_2.add_instance(NormalTransistor(techtype="p", id=2))

# fmt: off
cb_p_2.add_connection_xxx(port=CurrentBias.OUT, instance_id=0, instance_port="drain")
cb_p_2.add_connection_xxx(port=CurrentBias.INOUTPUT, instance_id=0, instance_port="gate")
cb_p_2.add_connection_xxx(port=CurrentBias.INNER, instance_id=0, instance_port="source")
cb_p_2.add_connection_xxx(port=CurrentBias.INNER, instance_id=1, instance_port="drain")
cb_p_2.add_connection_xxx(port=CurrentBias.INSOURCE, instance_id=1, instance_port="gate")
cb_p_2.add_connection_xxx(port=CurrentBias.SOURCE, instance_id=1, instance_port="source")


cb_p_3 = CurrentBias(techtype="p", id=3)
cb_p_3.ports = [
    CurrentBias.OUT,
    CurrentBias.SOURCE,
    CurrentBias.INOUTPUT,
    CurrentBias.INSOURCE,
    CurrentBias.INNER,
]
cb_p_3.add_instance(NormalTransistor(techtype="p"))
cb_p_3.add_instance(DiodeTransistor(techtype="p", id=1))

cb_p_3.add_connection_xxx(port=CurrentBias.OUT, instance_id=0, instance_port="drain")
cb_p_3.add_connection_xxx(port=CurrentBias.INOUTPUT, instance_id=0, instance_port="gate")
cb_p_3.add_connection_xxx(port=CurrentBias.INNER, instance_id=0, instance_port="source")
cb_p_3.add_connection_xxx(port=CurrentBias.INNER, instance_id=1, instance_port="drain")
cb_p_3.add_connection_xxx(port=CurrentBias.INSOURCE, instance_id=1, instance_port="gate")
cb_p_3.add_connection_xxx(port=CurrentBias.SOURCE, instance_id=1, instance_port="source")


# === N type


cb_n_1 = CurrentBias(techtype="n", id=1)
cb_n_1.ports = [CurrentBias.IN, CurrentBias.OUT, CurrentBias.SOURCE]
cb_n_1.add_instance(NormalTransistor(techtype="n"))
cb_n_1.add_connection_xxx(port=CurrentBias.IN, instance_id=0, instance_port="drain")
cb_n_1.add_connection_xxx(port=CurrentBias.OUT, instance_id=0, instance_port="gate")
cb_n_1.add_connection_xxx(port=CurrentBias.SOURCE, instance_id=0, instance_port="source")


cb_n_2 = CurrentBias(techtype="n", id=2)
cb_n_2.ports = [
    CurrentBias.OUT,
    CurrentBias.SOURCE,
    CurrentBias.INOUTPUT,
    CurrentBias.INSOURCE,
    CurrentBias.INNER,
]
cb_n_2.add_instance(NormalTransistor(techtype="n"))
cb_n_2.add_instance(NormalTransistor(techtype="n", id=2))

cb_n_2.add_connection_xxx(port=CurrentBias.OUT, instance_id=0, instance_port="drain")
cb_n_2.add_connection_xxx(port=CurrentBias.INOUTPUT, instance_id=0, instance_port="gate")
cb_n_2.add_connection_xxx(port=CurrentBias.INNER, instance_id=0, instance_port="source")
cb_n_2.add_connection_xxx(port=CurrentBias.INNER, instance_id=1, instance_port="drain")
cb_n_2.add_connection_xxx(port=CurrentBias.INSOURCE, instance_id=1, instance_port="gate")
cb_n_2.add_connection_xxx(port=CurrentBias.SOURCE, instance_id=1, instance_port="source")


cb_n_3 = CurrentBias(techtype="p", id=3)
cb_n_3.ports = [
    CurrentBias.OUT,
    CurrentBias.SOURCE,
    CurrentBias.INOUTPUT,
    CurrentBias.INSOURCE,
    CurrentBias.INNER,
]
cb_n_3.add_instance(NormalTransistor(techtype="p"))
cb_n_3.add_instance(DiodeTransistor(techtype="p", id=1))

cb_n_3.add_connection_xxx(port=CurrentBias.OUT, instance_id=0, instance_port="drain")
cb_n_3.add_connection_xxx(port=CurrentBias.INOUTPUT, instance_id=0, instance_port="gate")
cb_n_3.add_connection_xxx(port=CurrentBias.INNER, instance_id=0, instance_port="source")
cb_n_3.add_connection_xxx(port=CurrentBias.INNER, instance_id=1, instance_port="drain")
cb_n_3.add_connection_xxx(port=CurrentBias.INSOURCE, instance_id=1, instance_port="gate")
cb_n_3.add_connection_xxx(port=CurrentBias.SOURCE, instance_id=1, instance_port="source")


class CurrentBiasManager:

    def getAllCurrentBiasesPmos(self):
        return [cb_p_1, cb_p_2, cb_p_3]

    def getAllCurrentBiasesNmos(self):
        return [cb_n_1, cb_n_2, cb_n_3]

    def getOneTransistorCurrentBiasesPmos(self):
        return [cb_p_1]

    def getOneTransistorCurrentBiasesNmos(self):
        return [cb_n_1]

    def getTwoTransistorCurrentBiasesPmos(self):
        return [cb_p_2, cb_p_3]

    def getTwoTransistorCurrentBiasesNmos(self):
        return [cb_n_2, cb_n_3]


if __name__ == "__main__":

    cb_mng = CurrentBiasManager()
    all_cb = cb_mng.getAllCurrentBiasesNmos() + cb_mng.getAllCurrentBiasesPmos()

    for idx, circuit in enumerate(all_cb):
        if circuit != None:
            save_graphviz_figure(circuit, filename=Path(f"gallery/HL2/cb-{idx}.dot"))
