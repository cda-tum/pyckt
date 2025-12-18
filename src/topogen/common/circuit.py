from __future__ import annotations
from collections import defaultdict

import random
import os
from typing import List, Union, Callable, Tuple
from pathlib import Path


class Circuit:
    def __init__(self, name: str, id: int, techtype: str):

        # circuit name in abbreviation (e.g., nt, dt, inv, ts, dp, l, lp, vb, cb)
        self.name: str = name

        # unique id for each circuit instance in isolation.
        self.id: int = id

        self.techtype: str = techtype
        self.instances: list[Circuit] = []
        self.ports: list[str] = []
        self.connections: dict[str, list[dict]] = defaultdict(list)

        # randomly generated name (not used for now)
        self.label = str(random.randint(100, 999))

        # instance id within parent circuit
        self.instance_id: int = -1

    def add_instance(self, instance: Circuit) -> None:
        # automatically assign instance id as the current index in the instances list
        instance.instance_id = len(self.instances)
        self.instances.append(instance)

    def add_connection_xxx(self, port: str, instance_id: int, instance_port: str):
        assert port in self.ports, print(self.ports)
        _name, _id, _instance_id = (
            self.instances[instance_id].name,
            self.instances[instance_id].id,
            self.instances[instance_id].instance_id,
        )
        inst = self.instances[instance_id]
        assert instance_port in inst.ports, print(inst.ports)
        self.connections[port].append(
            {
                "child": [_name, _id, _instance_id],
                "port": instance_port,
            }
        )

    def get_port(self, name):
        return self.ports.get(name)

    def get_instance_by_name(self, name: str) -> List[Callable]:
        return [inst for inst in self.instances if inst.name == name]

    # -----------------------------------------------------
    # JSON SERIALIZATION SUPPORT
    # -----------------------------------------------------
    def to_dict(self):
        """Recursively convert this object into a serializable dict."""
        if self.name in ["dt", "nt"]:
            assert len(self.instances) == 0

        return {
            "__class__": self.__class__.__name__,
            "name": self.name,
            "id": self.id,
            "instance_id": self.instance_id,
            "techtype": self.techtype,
            "ports": self.ports,
            "connections": self.connections,
            "instances": [inst.to_dict() for inst in self.instances],
        }

    @property
    def tech(self) -> str:
        """Count the total number of components in the circuit, including nested instances."""

        # fmt: off
        if self.__class__.__name__ == "NormalTransistor":
            return self.techtype
        elif self.__class__.__name__ == "DiodeTransistor":
            return self.techtype
        else:
            _techlist = ""
            for inst in self.instances:
                _techlist += inst.tech
            if "p" in _techlist and "n" not in _techlist:
                return "p"
            if "n" in _techlist and "p" not in _techlist:
                return "n"
            
            raise NotImplementedError("unknown techtype.")  

    @property
    def component_count(self) -> int:
        """Count the total number of components in the circuit, including nested instances."""

        # fmt: off
        if self.__class__.__name__ == "NormalTransistor":
            return 1
        elif self.__class__.__name__ == "DiodeTransistor":
            return 1
        else:
            num_components = 0
            for inst in self.instances:
                num_components += inst.component_count
            return num_components

    def graphviz(self, prefix: Union[str, None] = None) -> str:
        """Generate Graphviz representation of the circuit.

        Args:
            prefix (str): Prefix for naming nodes in the graph.
            Returns:
            str: Graphviz representation of the circuit.
        """

        # fmt: off
        # if no prefix, we are at the top level circuit
        if prefix is None:
            prefix = f"top.([{self.instance_id}].{self.name}{self.id})" # e.g., top.0.inv1


        def get_pmos_def(prefix):
            content = f""" "{prefix}" [
                rankdir="TB"
                label = "{{ <S> S↲| <G> G| <D> D }}"
                shape="record"
            ]"""
            return content
        def get_nmos_def(prefix):
            content = f""" "{prefix}" [
                rankdir="TB"
                label = "{{ <D> D| <G> G| <S> S⭢ }}"
                shape="record"
            ]"""
            return content
        
        def get_diode_pmos_def(prefix):
            content = f""" "{prefix}" [
                rankdir="TB"
                label = "{{ <S> S↲| <G> G*| <D> D* }}"
                shape="record"
            ]"""
            return content
        def get_diode_nmos_def(prefix):
            content = f""" "{prefix}" [
                rankdir="TB"
                label = "{{ <D> D*| <G> G*| <S> S⭢ }}"
                shape="record"
            ]"""
            return content

        if self.__class__.__name__ == "NormalTransistor":
            content = (
                f""" subgraph "cluster_{prefix}" """
                + "{"
                + "\n"
            )
            content += f"""label="{self.name+ str(self.instance_id )}" """
            content += get_pmos_def(prefix) if self.techtype == "p" else get_nmos_def(prefix)
            content += "\n}"
            return content

        if self.__class__.__name__ == "DiodeTransistor":
            content = (
                f""" subgraph "cluster_{prefix}" """
                + "{"
                + "\n"
            )
            content += f"""label="{self.name + str(self.instance_id) }" """ + "\n"
            content += get_diode_pmos_def(prefix) if self.techtype == "p" else get_diode_nmos_def(prefix)
            content += "}"
            return content

        _techtype = self.techtype if self.techtype != "" else "-"
        data = (
            f"""subgraph "cluster_{random.randint(10,99)}" """
            + "{\n "
            + """rankdir="TB" """
            + "\n"
            + f"""label="[{_techtype}]  ([{self.instance_id}].{self.name}{self.id})" """
            + "\n"
        )
        for inst in self.instances:
            data += inst.graphviz(prefix=f"{prefix}.([{inst.instance_id}].{inst.name}{inst.id})") + "\n"

        # build terminals for current level
        for current_level_terminal, _ in self.connections.items():
            data += (
                f""" "{prefix}.{current_level_terminal}" [shape=plaintext, width=0.1, label="{current_level_terminal}", color="darkgoldenrod", style=filled, fontsize=10];    """
                + "\n"
            )

        # build connections based on connections dict
        for (
            current_level_terminal,
            connected_child_terminals,
        ) in self.connections.items():
            A = f""" "{prefix}.{current_level_terminal}" """
            for connection in connected_child_terminals:
                child = connection["child"]  # e.g., ["nt", 1]
                assert len(child) == 3

                child[-1] = str(child[-1])
                child[-2] = str(child[-2])

                _custom_port = connection["port"]  # e.g., "drain", "gate", "source"
                B = f"{prefix}.([{child[-1]}].{''.join(child[:2])})"

                if child[0] in ["dt", "nt"]:
                    port_mapping = {"source": "S", "drain": "D", "gate": "G"}
                    _custom_port = port_mapping[_custom_port]
                    B = f""" "{B}": """ + _custom_port
                else:
                    B = f""" "{B}.{_custom_port}" """

                data += A + "->" + B + " [arrowhead=none]; \n"
        data += "\n}"
        return data

    @staticmethod
    def from_dict(d):
        """Reconstruct Circuit (or subclass) from a dict."""

        class_map = {
            "Circuit": Circuit,
            "NormalTransistor": NormalTransistor,
            "DiodeTransistor": DiodeTransistor,
            "VoltageBias": VoltageBias,
        }

        cls = class_map[d["__class__"]]
        obj = cls(name=d["name"], id=d["id"], techtype=d["techtype"])

        obj.ports = d["ports"]
        obj.connections = d["connections"]

        for inst_dict in d["instances"]:
            obj.instances.append(Circuit.from_dict(inst_dict))

        return obj

    def _add_instances_to_flat_circuit(self, connections={}, instances=[]) -> None:

        if self.__class__.__name__ == "NormalTransistor":
            instances.append(self)

        if self.__class__.__name__ == "DiodeTransistor":
            instances.append(self)

        for inst in self.instances:
            inst._add_instances_to_flat_circuit(
                connections,
                instances,
            )

    def flatten(self):
        from collections import OrderedDict

        connections = OrderedDict()
        instances = []
        self._add_instances_to_flat_circuit(connections, instances)

        def set_terminal(
            top_current_terminal: str, looking_terminal: str, instance: Circuit
        ):
            if instance.name not in ["dt", "nt"]:
                for conn in instance.connections[looking_terminal]:
                    obtained_inst_id = int(conn["child"][-1])
                    obtained_inst = instance.instances[obtained_inst_id]
                    set_terminal(top_current_terminal, conn["port"], obtained_inst)
            else:
                if looking_terminal == "gate":
                    instance.gate = top_current_terminal
                if looking_terminal == "drain":
                    instance.drain = top_current_terminal
                if looking_terminal == "source":
                    instance.source = top_current_terminal

        for top_current_terminal, conn_list in self.connections.items():
            for conn in conn_list:
                obtained_inst_id = int(conn["child"][-1])
                obtained_inst = self.instances[obtained_inst_id]
                set_terminal(top_current_terminal, conn["port"], obtained_inst)

        from copy import deepcopy

        self.instances = deepcopy(instances)
        self.connections = {}
        return self


class NormalTransistor(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "nt"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)
        self.ports = ["drain", "gate", "source"]

        self.drain = None
        self.gate = None
        self.source = None


class DiodeTransistor(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "dt"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)
        self.ports = ["drain", "gate", "source"]
        self.drain = None
        self.gate = None
        self.source = None


class VoltageBias(Circuit):
    IN = "in"
    SOURCE = "source"
    OUT = "out"

    INNER = "inner"
    OUTINPUT = "out_input"
    OUTSOURCE = "out_source"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "vb"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class CurrentBias(Circuit):
    IN = "in"
    SOURCE = "source"
    OUT = "out"

    INNER = "inner"
    INOUTPUT = "in_output"
    INSOURCE = "in_source"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "cb"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class Inverter(Circuit):
    OUTPUT = "output"

    SOURCE_CURRENTBIASNMOS = "source_nmos"
    SOURCE_CURRENTBIASPMOS = "source_pmos"

    IN_CURRENTBIASNMOS = "in_curent_bias_nmos"
    IN_CURRENTBIASPMOS = "in_curent_bias_pmos"

    INSOURCE_CURRENTBIASNMOS = "in_source_current_bias_nmos"
    INOUTPUT_CURRENTBIASNMOS = "in_output_current_bias_nmos"
    INSOURCE_CURRENTBIASPMOS = "in_source_current_bias_pmos"
    INOUTPUT_CURRENTBIASPMOS = "in_output_current_bias_pmos"

    INNER_CURRENTBIASNMOS = "inner_current_bias_nmos"
    INNER_CURRENTBIASPMOS = "inner_current_bias_pmos"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "inv"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class TransistorStack(Circuit):
    IN = "in"
    SOURCE = "source"
    OUT = "out"

    INNER = "inner"
    INOUTPUT = "in_output"
    INSOURCE = "in_source"

    # INNER = "inner"
    OUTINPUT = "out_input"
    OUTSOURCE = "out_source"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "ts"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class LoadPart(Circuit):
    OUT1 = "out1"
    OUT2 = "out2"
    SOURCE = "source"

    SOURCE1 = "source1"
    SOURCE2 = "source2"
    INNER = "inner"

    INNEROUTPUT = "inner_output"
    INNERSOURCE = "inner_source"

    OUTOUTPUT1 = "out_output1"
    OUTOUTPUT2 = "out_output2"
    OUTSOURCE1 = "out_source1"
    OUTSOURCE2 = "out_source2"

    INNERTRANSISTORSTACK1 = "inner_transistorstack1"
    INNERTRANSISTORSTACK2 = "inner_transistorstack2"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "lp"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)

    @property
    def ts1(self) -> TransistorStack:
        return self.instances[0]

    @property
    def ts2(self) -> TransistorStack:
        return self.instances[1]

    @property
    def bothTransistorStacksAreVoltageBiases(self) -> bool:
        return self.ts1.instances[0].name.startswith("vb") and self.ts2.instances[
            0
        ].name.startswith("vb")


class Load(Circuit):
    OUT1 = "out1"
    OUT2 = "out2"

    SOURCELOAD1 = "source_load1"
    SOURCELOAD2 = "source_load2"

    SOURCEGCC1 = "source_gcc1"
    SOURCEGCC2 = "source_gcc2"

    INNERLOAD1 = "inner_load1"
    INNERLOAD2 = "inner_load2"

    INNERGCC = "inner_gcc"
    INNERBIASGCC = "inner_bias_gcc"

    INNERSOURCELOAD1 = "inner_source_load1"
    INNEROUTPUTLOAD1 = "inner_output_load1"
    INNERSOURCELOAD2 = "inner_source_load2"
    INNEROUTPUTLOAD2 = "inner_output_load2"

    INNERTRANSISTORSTACK1LOAD1 = "inner_transistorstack1_load1"
    INNERTRANSISTORSTACK2LOAD1 = "inner_transistorstack2_load1"
    INNERTRANSISTORSTACK1LOAD2 = "inner_transistorstack1_load2"
    INNERTRANSISTORSTACK2LOAD2 = "inner_transistorstack2_load2"

    OUTOUTPUT1LOAD1 = "out_output1_load1"
    OUTOUTPUT2LOAD1 = "out_output2_load1"
    OUTSOURCE1LOAD1 = "out_source_load1"
    OUTSOURCE2LOAD1 = "out_source_load2"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "l"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class DiffPair(Circuit):
    OUTPUT1 = "out1"
    OUTPUT2 = "out2"

    INPUT1 = "input1"
    INPUT2 = "input2"

    SOURCE = "source"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "dp"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class StageBias(Circuit):
    IN = "in"
    SOURCE = "source"
    OUT = "out"

    INNER = "inner"
    INOUTPUT = "in_output"
    INSOURCE = "in_source"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "sb"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class Transconductance(Circuit):

    INPUT1 = "input1"
    INPUT2 = "input2"
    INNER = "inner"

    OUT1 = "out1"
    OUT2 = "out2"

    OUT1NMOS = "out1_nmos"
    OUT2NMOS = "out2_nmos"
    OUT1PMOS = "out1_pmos"
    OUT2PMOS = "out2_pmos"

    #  "SimpleTransconductance"
    SOURCE = "source"

    # "FeedbackTransconductance"
    SOURCE_1 = "source_1"
    SOURCE_2 = "source_2"

    # "ComplementaryTransconductance"
    SOURCE_NMOS = "source_nmos"
    SOURCE_PMOS = "source_pmos"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "tc"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class NonInvertingStage(Circuit):

    IN1 = "in1"
    IN2 = "in2"
    OUT1 = "out1"
    OUT2 = "out2"

    SOURCETRANSCONDUCTANCE = "SourceTransconductance"

    SOURCETRANSCONDUCTANCE1 = "SourceTransconductance1"
    SOURCETRANSCONDUCTANCE2 = "SourceTransconductance2"
    INNERTRANSCONDUCTANCE = "InnerTransconductance"

    SOURCETRANSCONDUCTANCEPMOS = "SourceTransconductancePmos"
    SOURCETRANSCONDUCTANCENMOS = "SourceTransconductanceNmos"

    SOURCENMOS = "SourceNmos"
    SOURCEPMOS = "SourcePmos"

    INPUTSTAGEBIAS = "InputStageBias"
    INSOURCESTAGEBIAS = "InSourceStageBias"
    INOUTPUTSTAGEBIAS = "InOutputStageBias"
    INNERSTAGEBIAS = "InnerStageBias"

    INNERSTAGEBIAS1 = "InnerStageBias1"
    INNERSTAGEBIAS2 = "InnerStageBias2"

    INPUTSTAGEBIASPMOS = "InputStageBiasPmos"
    INSOURCESTAGEBIASPMOS = "InSourceStageBiasPmos"
    INOUTPUTSTAGEBIASPMOS = "InOutputStageBiasPmos"
    INNERSTAGEBIASPMOS = "InnerStageBiasPmos"

    INPUTSTAGEBIASNMOS = "InputStageBiasNmos"
    INSOURCESTAGEBIASNMOS = "InSourceStageBiasNmos"
    INOUTPUTSTAGEBIASNMOS = "InOutputStageBiasNmos"
    INNERSTAGEBIASNMOS = "InnerStageBiasNmos"

    SOURCEGCC1 = "SourceGCC1"
    SOURCEGCC2 = "SourceGCC2"

    INNERLOAD1 = "InnerLoad1"
    INNERLOAD2 = "InnerLoad2"
    INNERGCC = "InnerGCC"
    INNERBIASGCC = "InnerBiasGCC"
    INNERSOURCELOAD1 = "InnerSourceLOad1"
    INNEROUTPUTLOAD1 = "InnerOutputLoad1"
    INNERSOURCELOAD2 = "InnerSourceLoad2"
    INNEROUTPUTLOAD2 = "InnerOutputLoad2"
    INNERTRANSISTORSTACK1LOAD1 = "InnerTransistorStack1Load1"
    INNERTRANSISTORSTACK2LOAD1 = "InnerTransistorStack2Load1"
    INNERTRANSISTORSTACK1LOAD2 = "InnerTransistorStack1Load2"
    INNERTRANSISTORSTACK2LOAD2 = "InnerTransistorStack2Load2"

    INNERSOURCELOADNMOS = "InnerSourceLoadNmos"
    INNEROUTPUTLOADNMOS = "InnerOutputLoadNmos"
    INNERSOURCELOADPMOS = "InnerSourceLoadPmos"
    INNEROUTPUTLOADPMOS = "InnerOutputLoadPmos"
    INNERTRANSISTORSTACK1LOADNMOS = "InnerTransistorStack1LoadNmos"
    INNERTRANSISTORSTACK2LOADNMOS = "InnerTransistorStack2LoadNmos"
    INNERTRANSISTORSTACK1LOADPMOS = "InnerTransistorStack1LoadPmos"
    INNERTRANSISTORSTACK2LOADPMOS = "InnerTransistorStack2LoadPmos"

    OUTOUTPUT1LOAD1 = "OutOutput1Load1"
    OUTOUTPUT2LOAD1 = "OutOutput2Load1"
    OUTSOURCE1LOAD1 = "OutSource1Load1"
    OUTSOURCE2LOAD1 = "OutSource2Load1"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "non_inv"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


def save_graphviz_figure(circuit: Circuit, filename: Path):
    with open(filename, "w") as fw:

        fw.write("digraph g { \n")
        fw.write("""fontname="Helvetica,Arial,sans-serif" \n""")
        fw.write("""node [fontname="Helvetica,Arial,sans-serif"] \n""")
        fw.write("""edge [fontname="Helvetica,Arial,sans-serif"] \n""")

        fw.write(circuit.graphviz())
        fw.write("} \n")


def convert_dot_to_png(dot_filename: Path, png_filename: Path):
    os.system(f"dot -Tpng {dot_filename} > {png_filename}")


def createTransistorStack(id=1, instance: Circuit = None):
    ts = TransistorStack(id=id, techtype="?")
    ts.add_instance(instance)
    ts.ports = instance.ports
    # fmt: off
    for port in ts.ports:
        ts.add_connection_xxx(port=port, instance_id=0, instance_port=port)
    return ts


def connectInstanceTerminal(
    sc1: Circuit, sc2: Circuit, sc1_port_or_net: str, sc2_port: str
) -> tuple[Circuit, Circuit]:
    sc1_port_key = sc1_port_or_net
    sc1.connections[sc1_port_key].append(
        {"child": [sc2.name, sc2.id, sc2.instance_id], "port": sc2_port}
    )
    return sc1, sc2


def connectInstanceTerminalInOrder(
    instance1: Tuple[Circuit, str], instance2: Tuple[Circuit, str]
) -> Tuple[Circuit, Circuit]:
    sc1, sc1_port_or_net = instance1
    sc2, sc2_port = instance2
    return connectInstanceTerminal(sc1, sc2, sc1_port_or_net, sc2_port)


def connect(
    instance1: Tuple[Circuit, str], instance2: Tuple[Circuit, str]
) -> Tuple[Circuit, Circuit]:
    return connectInstanceTerminalInOrder(instance1, instance2)


def assignInstanceIds(circuits: List[Circuit], start_idx=10):
    for circuit in circuits:
        circuit.id = start_idx
        start_idx += 1


def hasGCC(load: Load) -> bool:
    assert load.name == "l"
    return "inner_gcc" in load.ports


def sourceTransistorIsDiodeTransistor(cb: CurrentBias) -> bool:
    if cb.component_count == 1:
        inst = cb.instances[0]
        return inst.name == "dt"
    else:
        # source transistor is the first one!
        source_transistor = cb.instances[0]
        return source_transistor.name == "dt"


def everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType(
    circuit: Circuit,
) -> bool:

    flatCircuit = deepcopy(circuit).flatten()

    drain_nets = defaultdict(list)
    gate_nets = defaultdict(list)

    for inst in flatCircuit.instances:
        gate_nets[inst.gate].append(inst)
        drain_nets[inst.drain].append(inst)

    def gatePinsAreOnlyNDoped(inst_list):
        isTrue = True
        for inst in inst_list:
            if inst.tech == "p":
                isTrue = False
        return isTrue

    def moreThanOneNDopdedDrainPin(inst_list):
        isTrue = False
        count = 0
        for inst in inst_list:
            if inst.tech == "n":
                count += 1
            if count >= 2:
                isTrue = True
                break
        return isTrue

    def moreThanOnePDopdedDrainPin(inst_list):
        isTrue = False
        count = 0
        for inst in inst_list:
            if inst.tech == "p":
                count += 1
            if count >= 2:
                isTrue = True
                break
        return isTrue

    def gatePinsAreOnlyPDoped(inst_list):
        for inst in inst_list:
            if inst.tech == "n":
                return False
        return True

    for net in list(set(gate_nets.keys()).intersection(drain_nets.keys())):
        logger.debug(f"{net=}")
        if gatePinsAreOnlyNDoped(gate_nets[net]):
            if moreThanOneNDopdedDrainPin(drain_nets[net]):
                return False
        elif gatePinsAreOnlyPDoped(gate_nets[net]):
            if moreThanOnePDopdedDrainPin(drain_nets[net]):
                return False
        else:
            if moreThanOnePDopdedDrainPin(
                drain_nets[net]
            ) or moreThanOneNDopdedDrainPin(drain_nets[net]):
                return False

    return True
