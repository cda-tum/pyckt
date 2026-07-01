"""Canonical, name-independent topology signatures for toplibgen parity (issue #3).

Parses an ACST-format ``.ckt`` netlist (``.suckt`` / ``.end``, one MOSFET or
capacitor per line) into a flat device/net graph and computes a canonical
Weisfeiler-Lehman-style hash that is invariant to internal-net renaming and
device ordering.  Two netlists that describe the *same* op-amp topology (up to
naming) get the same signature, so pyckt's generated set can be compared
device-for-device against acst's reference set rather than only by count.

Boundary nets (the op-amp ports: ``in1``/``in2``/``out``/``ibias``/
``sourceNmos``/``sourcePmos`` and the FD/complementary output variants) keep
their identity; every other net is treated as an anonymous internal node.

Usage
-----
    from comparison.topology_signature import signature_of_file, signatures_in_dir
    sig = signature_of_file("one_stage_single_output_op_amp1.ckt")
    sigs = signatures_in_dir("…/SingleOutputOpAmps")   # Counter[signature] -> count
"""
from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path

# Canonical boundary (port) net names.  Everything else is internal/anonymous.
# Lower-cased on read so acst's ``sourceNmos`` and any case variant collapse.
_BOUNDARY_NETS = {
    "in1", "in2", "out", "out1", "out2", "ibias",
    "sourcenmos", "sourcepmos", "vdd", "gnd", "vss",
}


def _tokenize(line: str) -> list[str]:
    return line.strip().split()


def parse_ckt(path: str | Path) -> tuple[list[tuple], set[str]]:
    """Parse an ACST ``.ckt`` netlist.

    Returns ``(devices, nets)`` where each device is
    ``(kind, model, [(terminal_role, net), …])`` and *nets* is the full net set.
    MOSFET lines are ``name drain gate source bulk model``; capacitor lines
    (``c_…``) are ``name n1 n2``.
    """
    def norm(net: str) -> str:
        # normalise so pyckt's ``source_nmos`` and acst's ``sourceNmos`` collapse
        # to the same boundary token; internal nets are anonymised anyway.
        return net.lower().replace("_", "")

    devices: list[tuple] = []
    nets: set[str] = set()
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(".suckt") or line.startswith(".end"):
            continue
        tok = _tokenize(line)
        name = tok[0].lower()
        if name.startswith("m"):  # MOSFET: name d g s b model
            if len(tok) < 6:
                continue
            d, g, s, b, model = norm(tok[1]), norm(tok[2]), norm(tok[3]), norm(tok[4]), tok[5].lower()
            terms = [("d", d), ("g", g), ("s", s), ("b", b)]
            devices.append(("mos", model, terms))
            nets.update([d, g, s, b])
        elif name.startswith("c"):  # capacitor: name n1 n2
            if len(tok) < 3:
                continue
            n1, n2 = norm(tok[1]), norm(tok[2])
            devices.append(("cap", "cap", [("c", n1), ("c", n2)]))
            nets.update([n1, n2])
    return devices, nets


def _wl_signature(devices: list[tuple], nets: set[str], rounds: int = 4) -> str:
    """Weisfeiler-Lehman refinement of the device/net bipartite graph.

    Net colours seed from boundary identity; device colours seed from
    ``kind+model``.  Each round, a net's colour absorbs its incident
    (device-colour, terminal-role) multiset and vice-versa.  The final
    signature is the sorted device-colour multiset (net colours fold in
    through the devices), hashed — invariant to internal-net renaming and
    device order.
    """
    net_color: dict[str, str] = {
        n: (n if n in _BOUNDARY_NETS else "_int") for n in nets
    }
    dev_color: list[str] = [f"{kind}:{model}" for kind, model, _ in devices]

    def h(s: str) -> str:
        return hashlib.blake2b(s.encode(), digest_size=8).hexdigest()

    for _ in range(rounds):
        # refine device colours from incident net colours + terminal roles
        new_dev = []
        for (kind, model, terms), dc in zip(devices, dev_color):
            incident = sorted(f"{role}={net_color[net]}" for role, net in terms)
            new_dev.append(h(f"{dc}|{'|'.join(incident)}"))
        # refine net colours from incident device colours + terminal roles
        net_incident: dict[str, list[str]] = {n: [] for n in nets}
        for (kind, model, terms), dc in zip(devices, new_dev):
            for role, net in terms:
                net_incident[net].append(f"{role}={dc}")
        new_net = {}
        for n in nets:
            base = n if n in _BOUNDARY_NETS else "_int"
            new_net[n] = h(f"{base}|{'|'.join(sorted(net_incident[n]))}")
        dev_color, net_color = new_dev, new_net

    return h("|".join(sorted(dev_color)) + "#" + str(len(nets)))


def signature_of_file(path: str | Path) -> str:
    """Canonical topology signature for one ACST ``.ckt`` netlist."""
    devices, nets = parse_ckt(path)
    return _wl_signature(devices, nets)


def signatures_in_dir(directory: str | Path) -> Counter:
    """Return ``Counter[signature] -> count`` over all ``*.ckt`` in *directory*."""
    counter: Counter = Counter()
    for ckt in sorted(Path(directory).glob("*.ckt")):
        counter[signature_of_file(ckt)] += 1
    return counter


if __name__ == "__main__":
    import sys

    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        "/home/jrad/acst/InputFileExamples/TopologyLibraryGeneration/Netlists"
    )
    for cat in ("SingleOutputOpAmps", "FullyDifferentialOpAmps", "CommplementaryOpAmps"):
        d = base / cat
        if not d.is_dir():
            continue
        sigs = signatures_in_dir(d)
        print(f"{cat}: {sum(sigs.values())} files, {len(sigs)} distinct signatures")
