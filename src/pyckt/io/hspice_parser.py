"""
HSpice circuit netlist parser.

Reads an ``.hspice`` file and produces a fully-wired :class:`~pyckt.core.Circuit`
by combining three configuration sources:

  - :class:`~pyckt.io.hspice_mapping.HSpiceMapping` — device-line interpretation
  - :class:`~pyckt.io.supply_nets_parser.SupplyNetConfig` — supply/ground labels
  - :class:`~pyckt.core.DeviceTypeRegister` — pin metadata (optional pins, etc.)

Algorithm (mirrors ``HSpice::InputFile`` in C++ ACST):

  1. Read file line-by-line.
  2. Skip comments (``**``), directives (``.TEMP``, ``.OPTION``, ``+``).
  3. Parse ``.GLOBAL`` → register global nets.
  4. For each device line (first char matches a mapping identifier):
     a. Look up the :class:`DeviceLineMapping` for the identifier.
     b. Extract device name, pin nets, and (optional) model name.
     c. Handle optional pins (Bulk auto-connection).
     d. Create :class:`Device`, find-or-create :class:`Net` objects,
        create :class:`Terminal` edges, wire everything together.
  5. Apply supply-net classification.
  6. Return completed :class:`Circuit`.

Maps to ``HSpice::InputFile::readFile`` in the C++ ACST code.
"""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from pyckt.core import (
    Circuit,
    Device,
    DeviceTypeRegister,
    PinType,
    Supply,
    TechType,
    Terminal,
)
from pyckt.io.hspice_mapping import HSpiceMapping
from pyckt.io.supply_nets_parser import SupplyNetConfig


class HSpiceParser:
    """Parse an HSpice circuit netlist into a :class:`~pyckt.core.Circuit`.

    Parameters
    ----------
    mapping : HSpiceMapping
        Device-line interpretation rules (from ``HSpiceMapping.xcat``).
    supply_nets : SupplyNetConfig
        Supply / ground net classification (from ``supplyNets.xcat``).
    device_types : DeviceTypeRegister
        Pin metadata per device type (from ``deviceTypes.xcat``).
    """

    def __init__(
        self,
        mapping: HSpiceMapping,
        supply_nets: SupplyNetConfig,
        device_types: DeviceTypeRegister,
    ) -> None:
        self.mapping = mapping
        self.supply_nets = supply_nets
        self.device_types = device_types

    # ── public entry point ────────────────────────────────────────────

    def parse(self, filepath: str | Path) -> Circuit:
        """Parse *filepath* and return a fully-wired :class:`Circuit`.

        Parameters
        ----------
        filepath : str | Path
            Path to an ``.hspice`` netlist file.

        Returns
        -------
        Circuit
            Populated with devices, nets, terminals, and supply annotations.

        Raises
        ------
        FileNotFoundError
            If *filepath* does not exist.
        KeyError
            If a device identifier has no mapping.
        """
        filepath = Path(filepath)
        circuit = Circuit(name=filepath.stem)

        with filepath.open("r", encoding="utf-8", errors="ignore") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue

                # Comments — extract design cell name if present
                if line.startswith("**"):
                    parsed_name = self._extract_circuit_name_from_comment(line)
                    if parsed_name:
                        circuit.name = parsed_name
                    continue

                upper = line.upper()

                # Skip directives and continuation lines
                if line.startswith("+") or upper.startswith((".TEMP", ".OPTION")):
                    continue

                # Skip subcircuit markers (must precede .END check)
                if upper.startswith((".MACRO", ".EOM", ".SUBCKT", ".ENDS")):
                    continue

                # Global nets
                if upper.startswith(".GLOBAL"):
                    self._parse_global_line(line, circuit)
                    continue

                # End of netlist
                if upper.startswith(".END"):
                    break

                # Device instantiation
                self._parse_device_line(line, circuit)

        self._apply_supply_classification(circuit)
        return circuit

    @staticmethod
    def _extract_circuit_name_from_comment(line: str) -> str | None:
        """Extract a circuit name from a comment line if present.

        Supports flexible, case-insensitive variants such as::

            ** Design cell name: my_opamp
            ** design-cell-name = my_opamp
        """
        comment = line.lstrip("*").strip()
        match = re.search(
            r"design\s*[-_ ]*cell\s*[-_ ]*name\s*[:=]\s*(.+)$",
            comment,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        name = match.group(1).strip().strip('"').strip()
        return name or None

    # ── internal helpers ──────────────────────────────────────────────

    def _parse_global_line(self, line: str, circuit: Circuit) -> None:
        """Parse a ``.GLOBAL vdd! gnd!`` line.

        Creates each global net (via ``find_or_create_net``) and marks its
        ``is_global`` flag as ``True``.

        Parameters
        ----------
        line : str
            The full ``.GLOBAL …`` line (already stripped).
        circuit : Circuit
            Circuit being constructed.
        """
        tokens = line.split()
        for token in tokens[1:]:
            net = circuit.find_or_create_net(token)
            net.is_global = True

    def _parse_device_line(self, line: str, circuit: Circuit) -> None:
        """Parse a single device instantiation line.

        For example: ``m17 net30 ibias gnd! gnd! nmos``

        Steps:
          1. Tokenise the line.
          2. Extract the identifier (first char of token 0, lowered).
          3. Look up the :class:`DeviceLineMapping`.
          4. Extract pin-net names by position.
          5. Handle optional pins / auto-connection (Bulk → Source).
          6. Determine :class:`TechType` from model name or fixed_tech.
          7. Create :class:`Device`, find-or-create :class:`Net` objects.
          8. Create :class:`Terminal` edges and register everything in *circuit*.

        Parameters
        ----------
        line : str
            A device instantiation line (already stripped).
        circuit : Circuit
            Circuit being constructed.
        """
        tokens = line.split()
        if not tokens:
            return

        device_name = tokens[0]
        identifier = device_name[0].lower()
        try:
            rule = self.mapping.get_mapping(identifier)
        except KeyError:
            # Unmapped device identifier (e.g. an 'i' current source with no
            # mapping entry). The C++ ACST parser tolerates these; we skip the
            # line with a warning rather than aborting the whole parse.
            logger.warning(
                "Skipping device line with unmapped identifier {!r}: {}",
                identifier, line,
            )
            return

        # Drop trailing "key=value" parameters (e.g. inline "W=..", "L=..",
        # "M=..").  The model name — when present — is the last *non-parameter*
        # token, so params must be removed before locating it; otherwise an
        # inline parameter would be mistaken for the model name.
        content_tokens = [t for t in tokens if "=" not in t]

        # When has_model the last content token is the model name; everything
        # before it (after the device name) is pin data.
        if rule.has_model:
            pin_boundary = len(content_tokens) - 1    # model is last token
        else:
            pin_boundary = len(content_tokens)

        # First pass: read pin nets from available token positions
        pin_nets: dict[PinType, str] = {}
        for pin_type, position in rule.pin_positions.items():
            if position < pin_boundary:
                pin_nets[pin_type] = content_tokens[position]

        # Second pass: auto-connect missing optional pins
        for pin_type in rule.pin_positions:
            if pin_type not in pin_nets:
                for pi in self.device_types.get_pin_types(rule.device_type):
                    if (
                        pi.pin_type == pin_type
                        and pi.optional
                        and pi.auto_connection is not None
                    ):
                        auto_net = pin_nets.get(pi.auto_connection)
                        if auto_net is not None:
                            pin_nets[pin_type] = auto_net
                        break

        # Determine tech type
        if rule.has_model:
            model_name = content_tokens[-1]
            tech_type = (rule.model_map or {}).get(model_name.casefold())
            if tech_type is None:
                # Unknown model string — don't abort the parse; tag the device
                # UNDEFINED and warn (mirrors the C++ parser's tolerance).
                logger.warning(
                    "Unknown model {!r} for device {!r}; tagging UNDEFINED",
                    model_name, device_name,
                )
                tech_type = TechType.UNDEFINED
        else:
            tech_type = (
                rule.fixed_tech
                if rule.fixed_tech is not None
                else TechType.UNDEFINED
            )

        # Create device and wire terminals
        device = Device(device_name, rule.device_type, tech_type)
        circuit.add_device(device)

        for pin_type, net_name in pin_nets.items():
            net = circuit.find_or_create_net(net_name)
            terminal = Terminal(device, pin_type, net)
            device.add_terminal(terminal)
            net.add_terminal(terminal)
            circuit.add_terminal(terminal)

    def _apply_supply_classification(self, circuit: Circuit) -> None:
        """Tag nets with :class:`~pyckt.core.Supply` based on :class:`SupplyNetConfig`.

        Iterates every net in the circuit and checks whether the supply-net
        config recognises it as ground or VDD.  If so, the net's ``supply``
        attribute is set with the correct :class:`SupplyType` and level.
        """
        for net in circuit.nets:
            if self.supply_nets.classify(net.name) is None:
                continue
            level = self.supply_nets.supply_level(net.name)
            if self.supply_nets.is_ground(net.name):
                net.supply = Supply.gnd(level)
            else:
                net.supply = Supply.vdd(level)
