"""Structural net-role inference for partitioning (issue #6).

acst's partitioner derives every net role it needs from the recognised
structure hierarchy and never reads a ``CircuitParameterAndSpecifications.xml``
(``Partitioning::compute`` takes only the StructRec result).  pyckt's
partitioners are seeded with four net roles instead, so this module infers
those same roles from the flat circuit's connectivity:

* **inputs** — the gate nets of a differential pair that no drain drives
  (externally driven nets; acst's first-stage differential pair is likewise
  the one whose gates are not shared with other differential pairs,
  ``Partitioning::partitioningDifferentialPairs``).
* **output** — a non-supply net whose MOSFET pins are all drains (at least
  two): the op-amp output drives no internal gate/source.  A capacitor from
  such a net to a rail (acst's load-capacitor rule,
  ``Partitioning::partitioningCapacitances``) confirms the choice when
  several candidates exist.
* **bias** — a non-supply net whose only drain belongs to a diode-connected
  transistor (gate = drain): a current-mirror reference with no internal
  driver must be fed externally (the ``ibias`` pin).  Internally-derived
  mirror references have a second drain on their net.

C++ ref: ``Partitioning::Partitioning::compute`` (no circuit parameters),
``partitioningDifferentialPairs``, ``partitioningCapacitances``.
"""

from __future__ import annotations

import logging

from ckt_io.circuit_info_parser import CircuitParameter
from core.device import PinType

_log = logging.getLogger(__name__)


def infer_circuit_parameters(circuit) -> CircuitParameter:
    """Derive partitioner net roles from *circuit*'s connectivity.

    Parameters
    ----------
    circuit : core.Circuit
        The parsed flat circuit (supply nets already flagged via
        ``supplyNets.xcat``).

    Returns
    -------
    CircuitParameter
        With ``input_plus``/``input_minus``/``output_net``/``bias_current``
        net names filled in (voltages/currents stay at their defaults — the
        partitioner only consumes the net names) and the supply/ground net
        names taken from the circuit's rails.
    """
    inputs = _infer_input_nets(circuit)
    output = _infer_output_net(circuit)
    bias = _infer_bias_net(circuit)

    vdd = next((n.name for n in circuit.nets if n.is_supply() and n.is_vdd()), "")
    gnd = next(
        (n.name for n in circuit.nets if n.is_supply() and not n.is_vdd()), ""
    )

    params = CircuitParameter(
        supply_voltage=(vdd, 0.0),
        ground=(gnd, 0.0),
        bias_current=(bias, 0.0),
        input_plus=(inputs[0] if inputs else "", 0.0),
        input_minus=(inputs[1] if len(inputs) > 1 else "", 0.0),
        output_net=output,
    )
    _log.info(
        "Inferred net roles: inputs=%s output=%r bias=%r vdd=%r gnd=%r",
        inputs, output, bias, vdd, gnd,
    )
    return params


# ── input nets ─────────────────────────────────────────────────────────────


def _infer_input_nets(circuit) -> list[str]:
    """Gate nets of a differential pair that no drain drives.

    A differential pair here is two same-tech MOSFETs sharing a source net,
    with distinct drains and distinct gate nets.  Only pairs whose *both*
    gate nets are undriven (no MOSFET drain on them) and non-supply qualify —
    those gates can only be the op-amp inputs.
    """
    by_source: dict = {}
    for m in circuit.mosfets:
        src = m.get_net(PinType.SOURCE)
        if src is None or src.is_supply():
            continue
        by_source.setdefault((src.name, m.tech_type), []).append(m)

    for devices in by_source.values():
        for i, a in enumerate(devices):
            for b in devices[i + 1:]:
                gates = [a.get_net(PinType.GATE), b.get_net(PinType.GATE)]
                drains = [a.get_net(PinType.DRAIN), b.get_net(PinType.DRAIN)]
                if any(g is None for g in gates) or any(
                    d is None for d in drains
                ):
                    continue
                if gates[0].name == gates[1].name:
                    continue
                if drains[0].name == drains[1].name:
                    continue
                if all(
                    not g.is_supply() and not _has_drain(g) for g in gates
                ):
                    return sorted(g.name for g in gates)
    return []


# ── output net ─────────────────────────────────────────────────────────────


def _infer_output_net(circuit) -> str:
    """A non-supply net whose MOSFET pins are all drains (two or more).

    When several candidates exist, a capacitor tying the candidate to a rail
    (the load capacitor) breaks the tie.
    """
    candidates = []
    for net in circuit.nets:
        if net.is_supply():
            continue
        drains = net.get_terminals_by_type(PinType.DRAIN)
        if len(drains) < 2:
            continue
        if net.get_terminals_by_type(PinType.GATE):
            continue
        if net.get_terminals_by_type(PinType.SOURCE):
            continue
        candidates.append(net.name)

    if len(candidates) > 1:
        for cap in circuit.capacitors:
            plus = cap.get_net(PinType.PLUS)
            minus = cap.get_net(PinType.MINUS)
            if plus is None or minus is None:
                continue
            for a, b in ((plus, minus), (minus, plus)):
                if a.name in candidates and b.is_supply():
                    return a.name
    return candidates[0] if candidates else ""


# ── bias net ───────────────────────────────────────────────────────────────


def _infer_bias_net(circuit) -> str:
    """A non-supply net whose only drain is a diode-connected transistor's own.

    Such a current-mirror reference has no internal driver, so its current
    must come from outside — the ``ibias`` pin.  Internally-derived mirror
    references carry a second drain (the feeding current source) on the net.
    """
    for m in circuit.mosfets:
        drain = m.get_net(PinType.DRAIN)
        gate = m.get_net(PinType.GATE)
        if drain is None or gate is None or drain.name != gate.name:
            continue  # not diode-connected
        if drain.is_supply():
            continue
        if len(drain.get_terminals_by_type(PinType.DRAIN)) == 1:
            return drain.name
    return ""


def _has_drain(net) -> bool:
    return bool(net.get_terminals_by_type(PinType.DRAIN))
