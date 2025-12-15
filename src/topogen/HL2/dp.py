import jsbeautifier
from src.topogen.common.circuit import *


dp1 = DiffPair(techtype="p", id=1)
dp1.ports = [
    DiffPair.INPUT1,
    DiffPair.INPUT2,
    DiffPair.OUTPUT1,
    DiffPair.OUTPUT2,
    DiffPair.SOURCE,
]
dp1.add_instance(NormalTransistor(techtype="p"))
dp1.add_instance(NormalTransistor(techtype="p"))
dp1.add_connection_xxx(port=DiffPair.OUTPUT1, instance_id=0, instance_port="drain")
dp1.add_connection_xxx(port=DiffPair.INPUT1, instance_id=0, instance_port="gate")
dp1.add_connection_xxx(port=DiffPair.SOURCE, instance_id=0, instance_port="source")
dp1.add_connection_xxx(port=DiffPair.OUTPUT2, instance_id=1, instance_port="drain")
dp1.add_connection_xxx(port=DiffPair.INPUT2, instance_id=1, instance_port="gate")
dp1.add_connection_xxx(port=DiffPair.SOURCE, instance_id=1, instance_port="source")

dp2 = DiffPair(techtype="n", id=2)
dp2.ports = [
    DiffPair.INPUT1,
    DiffPair.INPUT2,
    DiffPair.OUTPUT1,
    DiffPair.OUTPUT2,
    DiffPair.SOURCE,
]
dp2.add_instance(NormalTransistor(techtype="n"))
dp2.add_instance(NormalTransistor(techtype="n"))
dp2.add_connection_xxx(port=DiffPair.OUTPUT1, instance_id=0, instance_port="drain")
dp2.add_connection_xxx(port=DiffPair.INPUT1, instance_id=0, instance_port="gate")
dp2.add_connection_xxx(port=DiffPair.SOURCE, instance_id=0, instance_port="source")
dp2.add_connection_xxx(port=DiffPair.OUTPUT2, instance_id=1, instance_port="drain")
dp2.add_connection_xxx(port=DiffPair.INPUT2, instance_id=1, instance_port="gate")
dp2.add_connection_xxx(port=DiffPair.SOURCE, instance_id=1, instance_port="source")


class DiffPairManager:
    def getAllDiffPairs(self):
        return [dp1, dp2]

    def getDifferentialPairPmos(self):
        return dp1

    def getDifferentialPairNmos(self):
        return dp2
