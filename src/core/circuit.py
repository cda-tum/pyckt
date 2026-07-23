from __future__ import annotations

from typing import TYPE_CHECKING

from .common import (
    DuplicateDeviceError,
    DuplicateNetError,
    DuplicatePortError,
    UnknownDeviceError,
    UnknownNetError,
    UnknownPortError,
)
from .device import Device, DeviceType
from .net import Net, NetId
from .port import Port

if TYPE_CHECKING:
    from .instance import Instance
    from .terminal import Terminal


class Circuit:
    """
    Top-level circuit container holding all devices, nets, terminals,
    and instances.

    Maps to Core::Circuit in C++.
    This is the primary data structure that all analysis modules consume.
    """
    def __init__(self, name: str = ""):
        self.name = name
        self._devices: dict[str, Device] = {}       # name → Device
        self._nets: dict[str, Net] = {}              # name → Net
        self._terminals: list[Terminal] = []          # all pin-connections
        self._instances: dict[str, Instance] = {}    # name → Instance
        self._ports: dict[str, Port] = {}            # name → Port

    # ── Devices ───────────────────────────────────────────────────────────
    def add_device(self, device: Device) -> None:
        if device.name in self._devices:
            raise DuplicateDeviceError(
                f"Duplicate device name: {device.name}"
            )
        self._devices[device.name] = device

    def find_device(self, name: str) -> Device:
        try:
            return self._devices[name]
        except KeyError as exc:
            raise UnknownDeviceError(f"Unknown device: {name}") from exc

    def has_device(self, name: str) -> bool:
        return name in self._devices

    @property
    def devices(self) -> list[Device]:
        return list(self._devices.values())

    @property
    def mosfets(self) -> list[Device]:
        return [d for d in self.devices if d.device_type == DeviceType.MOSFET]

    @property
    def capacitors(self) -> list[Device]:
        return [d for d in self.devices if d.device_type == DeviceType.CAPACITOR]

    # ── Nets ──────────────────────────────────────────────────────────────
    def add_net(self, net: Net) -> None:
        if net.name in self._nets:
            raise DuplicateNetError(f"Duplicate net name: {net.name}")
        self._nets[net.name] = net

    def find_net(self, name: str) -> Net:
        try:
            return self._nets[name]
        except KeyError as exc:
            raise UnknownNetError(f"Unknown net: {name}") from exc

    def find_or_create_net(self, name: str) -> Net:
        if name not in self._nets:
            self._nets[name] = Net(NetId(name))
        return self._nets[name]

    def has_net(self, name: str) -> bool:
        return name in self._nets

    @property
    def nets(self) -> list[Net]:
        return list(self._nets.values())

    def get_supply_nets(self) -> list[Net]:
        return [n for n in self.nets if n.is_supply()]

    def get_ground_nets(self) -> list[Net]:
        return [n for n in self.nets if n.is_ground()]

    # ── Terminals (pin connections) ───────────────────────────────────────
    def add_terminal(self, terminal: Terminal) -> None:
        self._terminals.append(terminal)

    @property
    def terminals(self) -> list[Terminal]:
        return list(self._terminals)

    def has_terminals(self) -> bool:
        return len(self._terminals) > 0

    # ── Instances (hierarchical cells) ────────────────────────────────────
    def add_instance(self, instance: Instance) -> None:
        self._instances[instance.name] = instance

    def find_instance(self, name: str) -> Instance | None:
        return self._instances.get(name)

    def has_instance(self, name: str) -> bool:
        return name in self._instances

    def has_instances(self) -> bool:
        return len(self._instances) > 0

    @property
    def instances(self) -> list[Instance]:
        return list(self._instances.values())

    # ── Ports (circuit-level I/O) ─────────────────────────────────────────
    def add_port(self, port: Port) -> None:
        if port.name in self._ports:
            raise DuplicatePortError(
                f"Duplicate port name: {port.name}"
            )
        self._ports[port.name] = port

    def find_port(self, name: str) -> Port:
        try:
            return self._ports[name]
        except KeyError as exc:
            raise UnknownPortError(f"Unknown port: {name}") from exc

    def has_port(self, name: str) -> bool:
        return name in self._ports

    @property
    def ports(self) -> list[Port]:
        return list(self._ports.values())

    def has_ports(self) -> bool:
        return len(self._ports) > 0

    # ── Net merging ───────────────────────────────────────────────────────
    def merge_nets(self, target_name: str, source_name: str) -> Net:
        """Merge *source* net into *target* net.

        All terminals on the source net are reassigned to the target net.
        The source net is removed from the circuit.  Returns the target net.

        Mirrors C++ Circuit::shortenNets / Net::mergePins.
        """
        target = self.find_net(target_name)
        source = self.find_net(source_name)
        if target is source:
            return target
        # reassign every terminal from source → target
        for terminal in source.terminals:
            terminal.net = target
            target.add_terminal(terminal)
        source.clear_terminals()
        # propagate supply if target has none
        if not target.is_supply() and source.is_supply():
            target.supply = source.supply
        del self._nets[source_name]
        return target
