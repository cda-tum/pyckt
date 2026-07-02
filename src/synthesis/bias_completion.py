"""Bias-network completion for generated op-amp topologies (issue #3, Fix 2b).

After :meth:`topogen.common.circuit.Circuit.flatten`, a generated op-amp's
current-source / cascode reference gates are left *floating* — they are gate
nets that no transistor drain drives (the tail current source, cascode biases,
…).  acst's ``OpAmps::buildAndConnectedBias`` synthesises a bias network for
these: it groups the floating gates by tech and by whether their transistors sit
on a supply rail (*source* biases) or an internal node (*output*/cascode
biases), attaches a diode-connected voltage-bias reference to each group, and
ties the master reference to the ``ibias`` pin.

This ports the **simple** path of that algorithm (a single diode-connected
reference per source/output group, `connectRemainingGateTerminals`'s ``else``
branch + `connectIbiasTerminal`), operating directly on the flat leaf
transistors.  The two-transistor cascode voltage bias and the improved-Wilson
current-mirror path are not yet reproduced — those topologies keep their
floating references for now and simply won't match acst until a later pass.

C++ ref: ``Synthesis::OpAmps::buildAndConnectedBias`` /
``connectRemainingGateTerminals`` / ``connectIbiasTerminal``.
"""
from __future__ import annotations

from topogen.common.circuit import NormalTransistor

_RAILS = {"source_nmos", "source_pmos"}
_INPUTS = {"in1", "in2", "vref"}
_IBIAS = "ibias"
_RAIL_OF = {"n": "source_nmos", "p": "source_pmos"}


def _diode_reference(tech: str, node: str, source: str | None = None) -> NormalTransistor:
    """A diode-connected voltage-bias reference transistor (gate = drain = *node*,
    source on *source* — defaulting to *tech*'s supply rail)."""
    t = NormalTransistor(techtype=tech, id=1)
    t.drain = node
    t.gate = node
    t.source = source if source is not None else _RAIL_OF[tech]
    return t


def _forms_cascode(source_gates: list, output_gates: list, leaves: list) -> bool:
    """True if the *output* (cascode) floating gates stack on the *source*
    (rail) floating gates — every output-gate transistor's source sits on a
    source-gate transistor's drain, one-to-one.  This is acst's
    ``allInstanceTerminalsArePartOfNotGateDrainConnectedTwoTransistorStacks``
    condition selecting a two-transistor cascode voltage bias.
    """
    if not source_gates or len(source_gates) != len(output_gates):
        return False
    src_drains = {t.drain for t in leaves if t.gate in source_gates}
    for g in output_gates:
        devs = [t for t in leaves if t.gate == g]
        if not all(t.source in src_drains for t in devs):
            return False
    return True


def complete_bias_network(leaves: list, input_tech: str) -> list:
    """Return *leaves* augmented with a bias network for its floating gates.

    Parameters
    ----------
    leaves:
        Flat leaf transistors (``.drain``/``.gate``/``.source`` net-name strings,
        ``.techtype`` ``"n"``/``"p"``).
    input_tech:
        Tech of the differential input pair (``"n"``/``"p"``) — decides which
        rail's bias reference receives ``ibias`` when both techs have one.

    Notes
    -----
    Mutates the leaves' net names in place (they belong to a flattened copy) and
    appends the new reference transistors.
    """
    drains = {t.drain for t in leaves}
    gates = {t.gate for t in leaves}
    floating = [
        g for g in gates
        if g is not None and g not in drains and g not in _INPUTS and g != _IBIAS
    ]
    if not floating:
        return leaves

    def devs_of(g):
        return [t for t in leaves if t.gate == g]

    def techs_of(g):
        return {t.techtype for t in devs_of(g)}

    def is_source(g):
        return all(t.source in _RAILS for t in devs_of(g))

    rename: dict[str, str] = {}
    new_devs: list = []
    idx = 0
    ibias_node: dict[str, str] = {}
    # rail-connected reference gate for each tech's source bias (the node a
    # cross-tech current mirror must sense): the node itself for a single-diode
    # reference, the *bottom* (rail) node for a cascode reference.
    rail_ref: dict[str, str] = {}
    # single-diode *output* (cascode-gate) references — (tech, node).  Each needs
    # an opposite-tech current-source leg mirroring the ibias reference (acst
    # ``addCurrentBiasesToCircuit`` — a diode reference alone carries no bias
    # current, so its node floats without the paired current source).
    output_refs: list = []
    # improved-Wilson references — tech → (top diode node, sensed stage diode
    # node).  Built for a floating cascode gate whose transistor stacks on a
    # diode (acst ``connectCurrentBiasOfImprovedWilsonCurrentMirror``).
    wilson_refs: dict[str, tuple[str, str]] = {}

    for tech in ("n", "p"):
        # single-tech floating gates only (mixed-tech gates are a more complex
        # case handled by acst's Wilson/cascode paths, not yet ported)
        group = [g for g in floating if techs_of(g) == {tech}]
        source_gates = [g for g in group if is_source(g)]
        output_gates = [g for g in group if not is_source(g)]

        # cascode-GCC (acst ``connectCascodeGCC``): a pair of same-tech cascode
        # transistors sharing one floating gate and riding on the differential
        # pair's drains (the folded gate-connected cascode, input tech == cascode
        # tech) gets a diode reference riding on the pair's common-source (tail)
        # node instead of the rail (``addOneTransistorVoltageBiasToCircuit``'s
        # INNERGCC special case).
        for g in list(output_gates):
            devs = devs_of(g)
            if len(devs) != 2:
                continue
            input_devs = [t for t in leaves if t.gate in ("in1", "in2")]
            if not input_devs or {t.techtype for t in input_devs} != {tech}:
                continue
            in_drains = {t.drain for t in input_devs}
            tails = {t.source for t in input_devs}
            if len(tails) == 1 and all(t.source in in_drains for t in devs):
                new_devs.append(_diode_reference(tech, g, source=next(iter(tails))))
                output_refs.append((tech, g))
                output_gates.remove(g)

        # improved-Wilson current mirror (acst connectCurrentBiasOfImproved-
        # WilsonCurrentMirror, runs before the remaining-gate handling): a
        # floating cascode gate driven by exactly one transistor that stacks on
        # a diode gets a two-transistor voltage bias — a diode on the gate node
        # (an ibias candidate) over a transistor sensing the stage's own diode
        # node (VB ``OUTSOURCE`` → the stage's ``INSOURCESTAGEBIAS``).
        for g in list(output_gates):
            devs = devs_of(g)
            if len(devs) != 1:
                continue
            src_net = devs[0].source
            if any(
                d.drain == src_net and d.gate == src_net and d.techtype == tech
                for d in leaves
            ):
                idx += 1
                mid = f"bias_{tech}_{idx}m"
                new_devs.append(_diode_reference(tech, g, source=mid))
                bottom = NormalTransistor(techtype=tech, id=1)
                bottom.drain = mid
                bottom.gate = src_net
                bottom.source = _RAIL_OF[tech]
                new_devs.append(bottom)
                wilson_refs[tech] = (g, src_net)
                output_gates.remove(g)

        if _forms_cascode(source_gates, output_gates, leaves):
            # Two-transistor cascode voltage bias: a stacked diode reference —
            # bottom diode on the rail, top diode on the bottom's node. The
            # cascode (output) gates take the top node (which becomes ibias);
            # the rail (source) gates take the intermediate node.  Matches acst
            # StageBias_3(gate=ibias)/StageBias_4(gate=inner) + the paired
            # MainBias cascode (connectRemainingGateTerminals two-transistor path).
            idx += 1
            bottom = f"bias_{tech}_{idx}b"
            top = f"bias_{tech}_{idx}t"
            new_devs.append(_diode_reference(tech, bottom))
            new_devs.append(_diode_reference(tech, top, source=bottom))
            for g in source_gates:
                rename[g] = bottom
            for g in output_gates:
                rename[g] = top
            ibias_node[tech] = top
            rail_ref[tech] = bottom
        else:
            for gates_subset, is_src in ((output_gates, False), (source_gates, True)):
                if not gates_subset:
                    continue
                idx += 1
                node = f"bias_{tech}_{idx}"
                new_devs.append(_diode_reference(tech, node))
                for g in gates_subset:
                    rename[g] = node
                if is_src:
                    ibias_node[tech] = node
                    rail_ref[tech] = node
                else:
                    output_refs.append((tech, node))

    # A Wilson reference is a two-transistor voltage bias: an ibias candidate
    # for a tech with no rail (source) reference (acst ``connectIbiasTerminal``'s
    # two-transistor fallback), sensed at its OUTSOURCE — the stage's own diode
    # node.  With a rail reference present it is just another non-ibias
    # reference needing an opposite-tech current leg on its IN (top) node.
    for tech, (top, src_net) in wilson_refs.items():
        if tech not in ibias_node:
            ibias_node[tech] = top
            rail_ref[tech] = src_net
        else:
            output_refs.append((tech, top))

    # tie the master source reference to the ibias pin
    if ibias_node:
        if len(ibias_node) == 1:
            master_tech = next(iter(ibias_node))
        else:
            master_tech = input_tech if input_tech in ibias_node else next(iter(ibias_node))
        rename[ibias_node[master_tech]] = _IBIAS

        # Every reference not tied to ibias gets an opposite-tech current-source
        # leg (acst ``addCurrentBiasesToCircuit``): a diode reference alone
        # carries no bias current.  A leg of tech T mirrors a reference of its
        # *own* tech T — the master for the master's tech; for the other tech,
        # its rail (source) reference if it has one, else a freshly created
        # intermediate diode (acst ``findReferenceVoltageBias``'s create-new
        # branch), which then needs its own master-tech leg (the chained
        # MainBias_17/MainBias_2 pattern in acst netlists).
        master_gate = rail_ref[master_tech]
        other_tech = "p" if master_tech == "n" else "n"

        legs_needed = [
            (tech, node) for tech, node in ibias_node.items() if tech != master_tech
        ]
        legs_needed.extend(output_refs)

        ref_gate = {master_tech: master_gate}
        if any(tech == master_tech for tech, _ in legs_needed):
            if other_tech in rail_ref:
                ref_gate[other_tech] = rail_ref[other_tech]
            else:
                idx += 1
                intermediate = f"bias_{other_tech}_{idx}"
                new_devs.append(_diode_reference(other_tech, intermediate))
                ref_gate[other_tech] = intermediate
                legs_needed.append((other_tech, intermediate))

        for tech, node in legs_needed:
            leg_tech = "p" if tech == "n" else "n"
            leg = NormalTransistor(techtype=leg_tech, id=1)
            leg.gate = ref_gate[leg_tech]
            leg.drain = node
            leg.source = _RAIL_OF[leg_tech]
            new_devs.append(leg)

    def resolve(net):
        seen: set = set()
        while net in rename and net not in seen:
            seen.add(net)
            net = rename[net]
        return net

    for t in [*leaves, *new_devs]:
        t.drain = resolve(t.drain)
        t.gate = resolve(t.gate)
        t.source = resolve(t.source)

    return [*leaves, *new_devs]
