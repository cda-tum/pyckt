import jsbeautifier
from src.topogen.common.circuit import *


cb_p_1 = CurrentBias(techtype="p", id=1)
cb_p_1.ports = ["in", "out", "source"]
cb_p_1.add_instance(NormalTransistor(techtype="p"))
cb_p_1.add_connection(port="in", instance_name="nt.1", instance_port="drain")
cb_p_1.add_connection(port="out", instance_name="nt.1", instance_port="gate")
cb_p_1.add_connection(port="source", instance_name="nt.1", instance_port="source")


cb_p_2 = CurrentBias(techtype="p", id=2)
cb_p_2.ports = ["out", "source", "inOutput", "inSource", "inner"]
cb_p_2.add_instance(NormalTransistor(techtype="p"))
cb_p_2.add_instance(NormalTransistor(techtype="p", id=2))

cb_p_2.add_connection(port="out", instance_name="nt.1", instance_port="drain")
cb_p_2.add_connection(port="inOutput", instance_name="nt.1", instance_port="gate")
cb_p_2.add_connection(port="inner", instance_name="nt.1", instance_port="source")
cb_p_2.add_connection(port="inner", instance_name="nt.2", instance_port="drain")
cb_p_2.add_connection(port="inSource", instance_name="nt.2", instance_port="gate")
cb_p_2.add_connection(port="source", instance_name="nt.2", instance_port="source")


cb_p_3 = CurrentBias(techtype="p", id=3)
cb_p_3.ports = ["out", "source", "inOutput", "inSource", "inner"]
cb_p_3.add_instance(NormalTransistor(techtype="p"))
cb_p_3.add_instance(DiodeTransistor(techtype="p", id=1))

cb_p_3.add_connection(port="out", instance_name="nt.1", instance_port="drain")
cb_p_3.add_connection(port="inOutput", instance_name="nt.1", instance_port="gate")
cb_p_3.add_connection(port="inner", instance_name="nt.1", instance_port="source")
cb_p_3.add_connection(port="inner", instance_name="dt.1", instance_port="drain")
cb_p_3.add_connection(port="inSource", instance_name="dt.1", instance_port="gate")
cb_p_3.add_connection(port="source", instance_name="dt.1", instance_port="source")


# === N type


cb_n_1 = CurrentBias(techtype="n", id=1)
cb_n_1.ports = ["in", "out", "source"]
cb_n_1.add_instance(NormalTransistor(techtype="n"))
cb_n_1.add_connection(port="in", instance_name="nt.1", instance_port="drain")
cb_n_1.add_connection(port="out", instance_name="nt.1", instance_port="gate")
cb_n_1.add_connection(port="source", instance_name="nt.1", instance_port="source")


cb_n_2 = CurrentBias(techtype="n", id=2)
cb_n_2.ports = ["out", "source", "inOutput", "inSource", "inner"]
cb_n_2.add_instance(NormalTransistor(techtype="n"))
cb_n_2.add_instance(NormalTransistor(techtype="n", id=2))

cb_n_2.add_connection(port="out", instance_name="nt.1", instance_port="drain")
cb_n_2.add_connection(port="inOutput", instance_name="nt.1", instance_port="gate")
cb_n_2.add_connection(port="inner", instance_name="nt.1", instance_port="source")
cb_n_2.add_connection(port="inner", instance_name="nt.2", instance_port="drain")
cb_n_2.add_connection(port="inSource", instance_name="nt.2", instance_port="gate")
cb_n_2.add_connection(port="source", instance_name="nt.2", instance_port="source")


cb_n_3 = CurrentBias(techtype="p", id=3)
cb_n_3.ports = ["out", "source", "inOutput", "inSource", "inner"]
cb_n_3.add_instance(NormalTransistor(techtype="p"))
cb_n_3.add_instance(DiodeTransistor(techtype="p", id=1))

cb_n_3.add_connection(port="out", instance_name="nt.1", instance_port="drain")
cb_n_3.add_connection(port="inOutput", instance_name="nt.1", instance_port="gate")
cb_n_3.add_connection(port="inner", instance_name="nt.1", instance_port="source")
cb_n_3.add_connection(port="inner", instance_name="dt.1", instance_port="drain")
cb_n_3.add_connection(port="inSource", instance_name="dt.1", instance_port="gate")
cb_n_3.add_connection(port="source", instance_name="dt.1", instance_port="source")


class CurrentBiasManager:

    def getAllCurrentBiasesPmos(self):
        return [cb_p_1, cb_p_2, cb_p_3]

    def getAllCurrentBiasesNmos(self):
        return [cb_n_1, cb_n_2, cb_n_3]
