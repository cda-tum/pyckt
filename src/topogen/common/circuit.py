import json
from collections import defaultdict

import random


class Circuit:
    def __init__(self, name, id, techtype):
        self.name = name
        self.id = id
        self.techtype = techtype
        self.instances: list[Circuit] = []
        self.ports = []
        self.connections = defaultdict(list)

        # randomly generated name
        self.label = str(random.randint(100, 999))
        self.instance_id = self.id

    def add_instance(self, instance=None):
        # instance.instance_id = len(self.instances)
        self.instances.append(instance)

    def add_connection_xxx(self, port, instance_id, instance_port):
        assert port in self.ports, print(self.ports)
        top_level_port = port

        # __instance_name, __instance_id = instance_name.split(".")
        __instance_name, __instance_id = (
            self.instances[instance_id].name,
            self.instances[instance_id].id,
        )
        found = False
        for inst in self.instances:
            if inst.name == __instance_name and inst.instance_id == int(__instance_id):
                found = True
                break

        assert found == True

        assert instance_port in inst.ports, print(inst.ports)
        __instance_port = instance_port  # inst.get_port(instance_port)
        self.connections[top_level_port].append(
            {
                "child": [__instance_name, __instance_id],
                "port": __instance_port,
            }
        )

    def add_connection(self, port, instance_name, instance_port):
        assert port in self.ports, print(self.ports)
        top_level_port = port

        # get instance
        __instance_name, __instance_id = instance_name.split(".")
        # print(f"{__instance_name=}, {__instance_id=}")
        found = False
        for inst in self.instances:
            # print(inst.name, inst.id)
            # print(f"{inst.name=}, {inst.id=}")
            if inst.name == __instance_name and inst.instance_id == int(__instance_id):
                found = True
                # print("found....")
                break

        assert found == True

        assert instance_port in inst.ports, print(inst.ports)
        __instance_port = instance_port  # inst.get_port(instance_port)
        self.connections[top_level_port].append(
            {
                "child": [__instance_name, __instance_id],
                "port": __instance_port,
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


class DiffPair(Circuit):
    def __init__(self, *args, **kwargs):
        kwargs["name"] = "dp"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


