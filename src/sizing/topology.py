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


def first_stage_pieces(
    circuit: "Circuit | None",
    partition,
    known_names: Iterable[str] | None = None,
    output_net: str | None = None,
) -> tuple | None:
    """Resolve ``(input, tail, load diode, output cascode, its bias diode)``.

    All topological: the tail's drain sits on the input pair's common-source
    net; the load mirror diode is gate-and-drain-connected on an input-pair
    drain; the primary output branch is the opposite-tech cascode from
    :func:`output_branches`; its bias diode drives the cascode gate.  The
    last two require *output_net* and come back ``None`` without it.
    Returns ``None`` when the first-stage shape doesn't match.  Shared by the
    performance estimator (#50) and the CM-range spec constraints (#56).
    """
    from core.device import DeviceType, PinType

    if circuit is None:
        return None
    names = set(known_names) if known_names is not None else None

    def net(dev, pin):
        try:
            return dev.get_net(pin).name
        except Exception:
            return None

    ins = [d for d in input_pair_devices(partition)
           if names is None or d.name in names]
    if not ins:
        return None
    d_in = ins[0]
    mosfets = [d for d in circuit.devices
               if d.device_type == DeviceType.MOSFET
               and (names is None or d.name in names)]

    src_net = net(d_in, PinType.SOURCE)
    tail = next((d for d in mosfets
                 if d is not d_in and net(d, PinType.DRAIN) == src_net),
                None)

    pair_drains = {net(d, PinType.DRAIN) for d in ins}
    load = next((d for d in mosfets
                 if net(d, PinType.DRAIN) in pair_drains
                 and net(d, PinType.GATE) == net(d, PinType.DRAIN)),
                None)
    if tail is None or load is None:
        return None

    casc = bias2 = None
    if output_net:
        casc = next((c for c, _bottom in output_branches(
            circuit, output_net, known_names)
            if c.tech_type != d_in.tech_type), None)
        if casc is not None:
            casc_gate = net(casc, PinType.GATE)
            bias2 = next((d for d in mosfets
                          if net(d, PinType.DRAIN) == casc_gate
                          and net(d, PinType.GATE) == casc_gate),
                         None)
    return d_in, tail, load, casc, bias2
