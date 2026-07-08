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
    from core.circuit import Circuit
    from core.device import Device


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
    from core.device import DeviceType, PinType

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


def output_branches(
    circuit: "Circuit | None",
    output_net: str | None,
    known_names: Iterable[str] | None = None,
) -> list[tuple["Device", "Device | None"]]:
    """Output branches as ``(output_device, bottom_device_or_None)`` pairs.

    A branch is *cascoded* when the output device's source is an internal net
    carrying the drain of a same-tech transistor (the bottom device): its
    small-signal conductance is then ``gds_casc·gds_bottom/gm_casc`` instead
    of the raw ``gds`` — the composition acst's gain constraint uses, and the
    difference between ~38 dB and ~90 dB on a cascoded OTA.
    """
    from core.device import DeviceType, PinType

    branches: list[tuple[Device, Device | None]] = []
    if circuit is None:
        return branches
    names = set(known_names) if known_names is not None else None
    for casc in output_node_devices(circuit, output_net, known_names):
        bottom = None
        try:
            src_net = casc.get_net(PinType.SOURCE)
        except Exception:
            src_net = None
        if src_net is not None and not src_net.is_power():
            for dev in circuit.devices:
                if dev is casc or dev.device_type != DeviceType.MOSFET:
                    continue
                if names is not None and dev.name not in names:
                    continue
                if dev.tech_type != casc.tech_type:
                    continue
                try:
                    if dev.get_net(PinType.DRAIN).name == src_net.name:
                        bottom = dev
                        break
                except Exception:
                    continue
        branches.append((casc, bottom))
    return branches
