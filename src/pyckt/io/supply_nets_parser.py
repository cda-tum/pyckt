"""
Supply-net configuration parser.

Reads ``supplyNets.xcat`` (plain-text key-value format) and builds a lookup
table that classifies net names as ground (``GND_1``, ``GND_2``) or supply
(``VDD_1``, ``VDD_2``).

The file format is one entry per line::

    GND_1 "gnd!"
    VDD_2 "vdd!"

Used by the :class:`HSpiceParser` to tag nets with the correct
:class:`~pyckt.core.Supply` after circuit construction.

Maps to ``HSpice::SupplyNetConfig`` / ``CircuitInformation::SupplyNets``
in the C++ ACST code.
"""

from __future__ import annotations

from pathlib import Path


class SupplyNetConfig:
    """Configuration mapping supply / ground labels to net names.

    Attributes
    ----------
    ground_nets : dict[str, set[str]]
        ``"GND_1"`` → ``{"gnd!", "vss!", …}``.
    supply_nets : dict[str, set[str]]
        ``"VDD_2"`` → ``{"vdd!", "vddp!", …}``.
    """

    def __init__(self) -> None:
        self.ground_nets: dict[str, set[str]] = {}
        self.supply_nets: dict[str, set[str]] = {}
        self._label_by_net: dict[str, str] = {}

    # ── construction ──────────────────────────────────────────────────

    @classmethod
    def from_file(cls, filepath: str | Path) -> SupplyNetConfig:
        """Parse *filepath* (``supplyNets.xcat``) and return a populated config.

        Parameters
        ----------
        filepath : str | Path
            Path to a ``supplyNets.xcat`` plain-text file.

        Returns
        -------
        SupplyNetConfig

        Raises
        ------
        FileNotFoundError
            If *filepath* does not exist.
        """
        config = cls()

        with Path(filepath).open("r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue

                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    # ignore malformed lines without net token
                    continue

                label_raw, net_raw = parts[0].strip(), parts[1].strip()
                label_upper = label_raw.upper()

                # strip quotes on either side; handles unterminated quote cases too
                net_name = net_raw.strip().strip('"').strip()
                if not net_name:
                    continue

                if label_upper.startswith("GND"):
                    config.ground_nets.setdefault(label_upper, set()).add(net_name)
                elif label_upper.startswith("VDD"):
                    config.supply_nets.setdefault(label_upper, set()).add(net_name)
                else:
                    # Unknown label family: skip for now.
                    continue

                config._label_by_net[net_name.casefold()] = label_upper

        return config

    # ── classification queries ────────────────────────────────────────

    def classify(self, net_name: str) -> str | None:
        """Return the label (e.g. ``"GND_1"``, ``"VDD_2"``) or ``None``.

        Parameters
        ----------
        net_name : str
            Name of the net to look up.
        """
        return self._label_by_net.get(net_name.casefold())

    def is_ground(self, net_name: str) -> bool:
        """Return ``True`` if *net_name* is a recognized ground net."""
        label = self.classify(net_name)
        return bool(label and label.startswith("GND"))

    def is_supply(self, net_name: str) -> bool:
        """Return ``True`` if *net_name* is a recognized VDD net."""
        label = self.classify(net_name)
        return bool(label and label.startswith("VDD"))

    def is_power(self, net_name: str) -> bool:
        """Return ``True`` if *net_name* is any power/supply net."""
        return self.is_ground(net_name) or self.is_supply(net_name)

    def supply_level(self, net_name: str) -> int:
        """Extract the numeric supply level from the label.

        ``"GND_1"`` → ``1``, ``"VDD_2"`` → ``2``.
        Returns ``0`` if the net is not a power net.
        """
        label = self.classify(net_name)
        if label is None:
            return 0
        # label format: "GND_1", "VDD_2" → split on "_" and take last part
        try:
            return int(label.rsplit("_", maxsplit=1)[1])
        except (IndexError, ValueError):
            return 0
