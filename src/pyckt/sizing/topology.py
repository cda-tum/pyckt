"""Shared amplifier-topology identification for sizing.

The gain constraint, the maximised gain objective, and the post-solve
performance estimate must all agree on two notions:

* the **input pair** — the first-stage transconductance (differential pair)
  devices that set ``gm_in``;
* the **output node** — the MOSFETs whose drain sits on the output net, which
  set the output small-signal conductance ``gds_out`` (and hence the gain).

Centralising them here keeps those three consumers consistent.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from pyckt.core.circuit import Circuit
    from pyckt.core.device import Device


def input_pair_devices(partition) -> list["Device"]:
    """First-stage transconductance (input differential pair) devices."""
    from partitioning.result import StageType

    devices: list[Device] = []
    for structure in partition.transconductance_parts(StageType.FIRST):
        devices.extend(structure.devices)
    return devices


def output_node_devices(
    circuit: "Circuit | None",
    output_net: str | None,
    known_names: Iterable[str] | None = None,
) -> list["Device"]:
    """MOSFETs whose drain is on *output_net* (they set the output resistance).

    *known_names*, when given, restricts the result to devices that have sizing
    variables (so callers don't reference unsized devices).
    """
    from pyckt.core.device import DeviceType, PinType

    if circuit is None or not output_net:
        return []
    names = set(known_names) if known_names is not None else None
    devices: list[Device] = []
    for dev in circuit.devices:
        if dev.device_type != DeviceType.MOSFET:
            continue
        if names is not None and dev.name not in names:
            continue
        try:
            if dev.get_net(PinType.DRAIN).name == output_net:
                devices.append(dev)
        except Exception:
            continue
    return devices
