import json
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

    def add_instance(self, instance: Union[Callable, None] = None) -> None:
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


class NormalTransistor(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "nt"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)
        self.ports = ["drain", "gate", "source"]


class DiodeTransistor(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "dt"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)
        self.ports = ["drain", "gate", "source"]


class VoltageBias(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "vb"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class CurrentBias(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "cb"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class Inverter(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "inv"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class TransistorStack(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "ts"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class LoadPart(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "lp"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)

    @property
    def ts1(self) -> Circuit:
        return self.instances[0]

    @property
    def ts2(self) -> Circuit:
        return self.instances[1]


class Load(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "l"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class DiffPair(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "dp"
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


def assignInstanceIds(circuits: List[Circuit], start_idx=10):
    for circuit in circuits:
        circuit.id = start_idx
        start_idx += 1
