from __future__ import annotations

from typing import TYPE_CHECKING

from .device import PinType
from .net import Net

if TYPE_CHECKING:
    from .device import Device

class Terminal:
    """
    A terminal connects one device pin to one net.
    It is the edge in the bipartite Device–Net graph.

    Maps to Core::Terminal in C++.
    """
    def __init__(self, device: Device, pin_type: PinType, net: Net):
        self.device = device
        self.pin_type = pin_type
        self.net = net
