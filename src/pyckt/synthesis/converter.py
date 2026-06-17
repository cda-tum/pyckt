"""Topogen → core Circuit converter.

Provides :class:`TopologyConverter`, which takes a hierarchy-level
``topogen.common.circuit.Circuit`` (typically an ``OpAmp``) and returns
a flat :class:`pyckt.core.Circuit` containing one :class:`~pyckt.core.Device`
per leaf transistor, with D/G/S pins connected to named :class:`~pyckt.core.Net`
objects.

Usage
-----
>>> from topogen.HL5.opamps import createSimpleOneStageOpAmps
>>> from pyckt.synthesis.converter import TopologyConverter
>>> opamps = list(createSimpleOneStageOpAmps())
>>> converter = TopologyConverter()
>>> core_ckt = converter.convert(opamps[0])
>>> len(core_ckt.mosfets)
4
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from pyckt.core.circuit import Circuit as CoreCircuit
from pyckt.core.device import Device, DeviceType, PinType, TechType
from pyckt.core.terminal import Terminal


class TopologyConverter:
    """Convert a *topogen* ``Circuit`` hierarchy to a flat ``core.Circuit``.

    The conversion proceeds in three steps:

    1. **Deep-copy** the source circuit so the original library is not mutated.
    2. Call :meth:`~topogen.common.circuit.Circuit.flatten` on the copy, which
       collapses the hierarchy into a list of leaf
       :class:`~topogen.common.circuit.NormalTransistor` /
       :class:`~topogen.common.circuit.DiodeTransistor` objects, each with
       ``gate``, ``drain``, and ``source`` attributes set to net-name strings.
    3. Create a :class:`~pyckt.core.Device` for every leaf transistor, look up
       (or create) the corresponding :class:`~pyckt.core.Net`, and wire them
       together via :class:`~pyckt.core.Terminal` objects.

    The resulting :class:`~pyckt.core.Circuit` has:
    - One ``Device`` per transistor, named ``M1``, ``M2``, …
    - ``TechType.N`` for NMOS (``techtype == "n"``) and ``TechType.P`` for PMOS.
    - A ``Net`` per unique net-name string found in the flat circuit.
    - ``Terminal`` objects wiring each ``D/G/S`` pin to the appropriate net.

    .. note::

        The *bulk* terminal is not present in the topogen model, so it is
        omitted from the converted ``core.Circuit``.  If bulk connections are
        needed they must be added by the caller.

    Maps conceptually to the C++ ``Synthesis::TopologyConverter``.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def convert(self, topogen_circuit: Any) -> CoreCircuit:
        """Convert *topogen_circuit* to a flat :class:`~pyckt.core.Circuit`.

        Parameters
        ----------
        topogen_circuit:
            Any :class:`topogen.common.circuit.Circuit` subclass (typically
            an ``OpAmp``).  The object is **not** mutated; a deep-copy is
            made internally before flattening.

        Returns
        -------
        CoreCircuit
            A new :class:`~pyckt.core.Circuit` containing one
            :class:`~pyckt.core.Device` per leaf transistor.

        Raises
        ------
        ValueError
            If the flattened circuit contains no transistors.
        """
        # Step 1 — deep-copy so the original is not mutated
        flat = deepcopy(topogen_circuit)

        # Step 2 — flatten the hierarchy; sets .gate/.drain/.source on each leaf
        flat.flatten()

        if not flat.instances:
            raise ValueError(
                f"Flattened circuit '{topogen_circuit.name}' has no transistors."
            )

        # Step 3 — build core.Circuit
        core_circuit = CoreCircuit(name=topogen_circuit.name)

        for idx, transistor in enumerate(flat.instances, start=1):
            device = self._make_device(f"M{idx}", transistor)
            core_circuit.add_device(device)

            for pin_type, net_name in (
                (PinType.DRAIN, transistor.drain),
                (PinType.GATE, transistor.gate),
                (PinType.SOURCE, transistor.source),
            ):
                if net_name is None:
                    continue  # unconnected pin — skip gracefully
                net = core_circuit.find_or_create_net(str(net_name))
                terminal = Terminal(device=device, pin_type=pin_type, net=net)
                device.add_terminal(terminal)
                core_circuit.add_terminal(terminal)

        return core_circuit

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_device(self, name: str, transistor: Any) -> Device:
        """Create a :class:`~pyckt.core.Device` from a leaf topogen transistor.

        Parameters
        ----------
        name:
            Unique device name (e.g. ``"M1"``).
        transistor:
            A :class:`~topogen.common.circuit.NormalTransistor` or
            :class:`~topogen.common.circuit.DiodeTransistor`.

        Returns
        -------
        Device
            A MOSFET device with the appropriate :class:`~pyckt.core.device.TechType`.
        """
        tech_type = TechType.P if transistor.techtype == "p" else TechType.N
        return Device(
            name=name,
            device_type=DeviceType.MOSFET,
            tech_type=tech_type,
        )
