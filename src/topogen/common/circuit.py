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

    def graphviz(self, prefix=""):
        if prefix == "":
            prefix = self.label + "#" + self.name + str(self.id)
            techtype = self.techtype
        else:
            techtype = ""
        if self.__class__.__name__ == "NormalTransistor":
            content = (
                f""" subgraph "cluster_{prefix + "_" + self.name + "_" + str(self.id)}" """
                + "{"
                + "\n"
            )
            content += f"""label="{self.name+ str(self.id )}" """

            if self.techtype == "p":
                # content += f""" "{prefix+ '.' + self.name+str(self.id)}" [
                content += f""" "{prefix}" [

                    rankdir="TB"
                    label = "{{ <S> S↲| <G> G| <D> D }}"
                    shape="record"
                ]"""
            else:
                # content += f""" "{prefix+ '.' + self.name+str(self.id)}" [
                content += f""" "{prefix}" [

                    rankdir="TB"
                    label = "{{ <D> D| <G> G| <S> S⭢ }}"
                    shape="record"
                ]"""
            content += "\n}"
            # print("content: ", content)
            return content

        if self.__class__.__name__ == "DiodeTransistor":
            content = (
                f""" subgraph "cluster_{prefix + "_" + self.name + "_" + str(self.id)}" """
                + "{"
                + "\n"
            )
            content += f"""label="{self.name + str(self.id) }" """ + "\n"
            if self.techtype == "p":
                # content += f""" "{prefix+ '.' + self.name+str(self.id)}" [
                content += f""" "{prefix}" [

                    rankdir="TB"
                    label = "{{ <S> S↲| <G> G*| <D> D* }}"
                    shape="record"
                ]"""
            else:
                # content += f""" "{prefix+ '.' + self.name+str(self.id)}" [
                content += f""" "{prefix}" [

                    rankdir="TB"
                    label = "{{ <D> D*| <G> G*| <S> S⭢ }}"
                    shape="record"
                ]"""

            content += "}"
            # print("content: ", content)

            return content

        data = (
            f"""subgraph "cluster_{random.randint(10,99)}" """
            + "{\n "
            + """rankdir="TB" """
            + "\n"
            + f"""label="[{techtype}] {prefix}" """
            + "\n"
        )
        for inst in self.instances:
            data += inst.graphviz(prefix=prefix + "." + inst.name + str(inst.id)) + "\n"

        for conn, connval in self.connections.items():
            # add port pass
            # pass
            data += (
                f""" "{prefix}.{conn}" [shape=plaintext, width=0.1, label="{conn}", color="darkgoldenrod", style=filled, fontsize=10];    """
                + "\n"
            )

        for conn, connval in self.connections.items():
            A = f""" "{prefix}.{conn}" """
            for cv in connval:
                child = cv["child"]
                child[-1] = str(child[-1])
                _port = cv["port"]

                B = prefix + "." + "".join(child)
                _custom_port = _port

                if child[0] in ["dt", "nt"]:
                    map1 = {"source": "S", "drain": "D", "gate": "G"}
                    _custom_port = map1[_port]

                if _custom_port in ["D", "S", "G"]:
                    B = f""" "{B}": """ + _custom_port
                else:
                    B = f""" "{B}.{_custom_port}" """

                data += A + "->" + B + " [arrowhead=none]; \n"
        data += "\n}"
        # print("data: ", data)
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
        {"child": [sc2.name, sc2.id], "port": sc2_port}
    )
    return sc1, sc2


def assignInstanceIds(circuits: List[Circuit], start_idx=10):
    for circuit in circuits:
        circuit.id = start_idx
        start_idx += 1
