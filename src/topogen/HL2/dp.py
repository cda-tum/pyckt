import jsbeautifier
from src.topogen.common.circuit import *


dp1 = DiffPair(techtype="p", id=1)
dp1.ports = (["input1", "input2", "output1", "output2", "source"],)
dp1.add_instance(NormalTransistor(techtype="p"))
dp1.add_instance(NormalTransistor(techtype="p"))
dp1.add_connection_xxx(port="output1", instance_id=0, instance_port="drain")
dp1.add_connection_xxx(port="input1", instance_id=0, instance_port="gate")
dp1.add_connection_xxx(port="source", instance_id=0, instance_port="source")
dp1.add_connection_xxx(port="output2", instance_id=1, instance_port="drain")
dp1.add_connection_xxx(port="input2", instance_id=1, instance_port="gate")
dp1.add_connection_xxx(port="source", instance_id=1, instance_port="source")

dp2 = DiffPair(techtype="n", id=2)
dp2.ports = (["input1", "input2", "output1", "output2", "source"],)
dp2.add_instance(NormalTransistor(techtype="n"))
dp2.add_instance(NormalTransistor(techtype="n"))
dp2.add_connection_xxx(port="output1", instance_id=0, instance_port="drain")
dp2.add_connection_xxx(port="input1", instance_id=0, instance_port="gate")
dp2.add_connection_xxx(port="source", instance_id=0, instance_port="source")
dp2.add_connection_xxx(port="output2", instance_id=1, instance_port="drain")
dp2.add_connection_xxx(port="input2", instance_id=1, instance_port="gate")
dp2.add_connection_xxx(port="source", instance_id=1, instance_port="source")


class DiffPairManager:
    def getAllDiffPairs(self):
        return [dp1, dp2]
