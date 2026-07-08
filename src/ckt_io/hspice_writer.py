"""
HSpice netlist writer.

Writes a :class:`~core.Circuit` (with optional sizing results) to
HSpice format using ``.MACRO`` / ``.EOM`` syntax, compatible with the
topology-library-generation and synthesis output flows.

Output example::

    ** Name: two_stage_single_output_op_amp_1_1

    .MACRO two_stage_single_output_op_amp_1_1 ibias in1 in2 out sourceNmos sourcePmos
    m1 FirstStageYout1 FirstStageYout1 sourceNmos sourceNmos nmos4 L=4e-6 W=53e-6
    Capacitor1 out sourceNmos 20e-12
    .EOM two_stage_single_output_op_amp_1_1

    ** Expected Performance Values:
    ** Gain: 83 dB
    ** Power consumption: 0.809001 mW
    ** ...

Maps to ``HSpice::OutputFile`` in the C++ ACST code.
"""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

from core import (
    Circuit,
    Device,
    DeviceType,
    PinType,
    TechType,
)

# ── Canonical pin orderings per device type ───────────────────────────────
# Mirrors the C++ write order for each device family.

_PIN_ORDER: dict[DeviceType, list[PinType]] = {
    DeviceType.MOSFET: [PinType.DRAIN, PinType.GATE, PinType.SOURCE, PinType.BULK],
    DeviceType.BIPOLAR: [PinType.COLLECTOR, PinType.BASE, PinType.EMITTER],
    DeviceType.CAPACITOR: [PinType.PLUS, PinType.MINUS],
    DeviceType.RESISTOR: [PinType.PLUS, PinType.MINUS],
    DeviceType.INDUCTOR: [PinType.PLUS, PinType.MINUS],
    DeviceType.DIODE: [PinType.CATHODE, PinType.ANODE],
}

# ── Model-name mapping (synthesis convention: level-4 models) ─────────────

_MODEL_NAME: dict[tuple[DeviceType, TechType], str] = {
    (DeviceType.MOSFET, TechType.N): "nmos4",
    (DeviceType.MOSFET, TechType.P): "pmos4",
    (DeviceType.BIPOLAR, TechType.N): "npn",
    (DeviceType.BIPOLAR, TechType.P): "pnp",
}

# Device types that include a model-name token on the line.
_MODEL_DEVICES: frozenset[DeviceType] = frozenset({DeviceType.MOSFET, DeviceType.BIPOLAR})


class HSpiceWriter:
    """Write a :class:`~core.Circuit` to HSpice ``.ckt`` format.

    Usage::

        writer = HSpiceWriter()
        writer.write(circuit, "output.ckt",
                     performance={"Gain": "83 dB", "Power": "0.809 mW"})
    """

    # ── public entry point ────────────────────────────────────────────

    def write(
        self,
        circuit: Circuit,
        filepath: str | Path,
        *,
        performance: dict[str, str] | None = None,
        voltages: dict[str, float] | None = None,
        currents: dict[str, float] | None = None,
    ) -> None:
        """Write *circuit* to *filepath* in HSpice format.

        Parameters
        ----------
        circuit : Circuit
            The circuit to serialize.
        filepath : str | Path
            Output file path.
        performance : dict[str, str] | None
            Optional performance metrics to append as comments.
        voltages : dict[str, float] | None
            Optional net voltages to append as comments.
        currents : dict[str, float] | None
            Optional device currents to append as comments.
        """
        with Path(filepath).open("w", encoding="utf-8") as f:
            self._write_header(f, circuit)
            self._write_macro_header(f, circuit)
            self._write_devices(f, circuit)
            self._write_macro_footer(f, circuit)
            if performance:
                self._write_performance(f, performance)
            if voltages:
                self._write_voltages(f, voltages)
            if currents:
                self._write_currents(f, currents)

    # ── internal helpers ──────────────────────────────────────────────

    def _write_header(self, f: TextIO, circuit: Circuit) -> None:
        """Write the ``** Name: …`` comment header.

        Parameters
        ----------
        f : TextIO
            Open file handle.
        circuit : Circuit
            Circuit being written.
        """
        f.write(f"** Name: {circuit.name}\n\n")

    def _write_macro_header(self, f: TextIO, circuit: Circuit) -> None:
        """Write the ``.MACRO`` line with circuit name and port list.

        Parameters
        ----------
        f : TextIO
            Open file handle.
        circuit : Circuit
            Circuit being written.  Port names come from ``circuit.ports``.
        """
        parts = [".MACRO", circuit.name]
        for port in circuit.ports:
            parts.append(port.name)
        f.write(" ".join(parts) + "\n")

    def _write_devices(self, f: TextIO, circuit: Circuit) -> None:
        """Write one device instantiation line per device.

        Format depends on device type:
          - Mosfet: ``m1 drain gate source bulk nmos4 [L=… W=…]``
          - Capacitor: ``Capacitor1 plus minus [value]``
          - etc.

        Parameters
        ----------
        f : TextIO
            Open file handle.
        circuit : Circuit
            Circuit being written.
        """
        for device in circuit.devices:
            f.write(self._format_device_line(device) + "\n")

    @staticmethod
    def _format_device_line(device: Device) -> str:
        """Format a single device as an HSpice instantiation line.

        Parameters
        ----------
        device : Device
            Device to serialize.

        Returns
        -------
        str
            Formatted HSpice line (without trailing newline).
        """
        parts: list[str] = [device.name]

        # Append pin nets in canonical order
        pin_order = _PIN_ORDER.get(device.device_type, [])
        for pin_type in pin_order:
            if pin_type in device.terminals:
                parts.append(device.get_net(pin_type).name)

        # Append model name for model-based devices
        if device.device_type in _MODEL_DEVICES:
            key = (device.device_type, device.tech_type)
            model = _MODEL_NAME.get(key)
            if model is not None:
                parts.append(model)

        # Append sizing parameters (L=, W=, etc.)
        for param_name, param_value in device.parameters.items():
            parts.append(f"{param_name}={param_value}")

        return " ".join(parts)

    def _write_macro_footer(self, f: TextIO, circuit: Circuit) -> None:
        """Write the ``.EOM`` closing line.

        Parameters
        ----------
        f : TextIO
            Open file handle.
        circuit : Circuit
            Circuit being written.
        """
        f.write(f".EOM {circuit.name}\n")

    def _write_performance(
        self, f: TextIO, performance: dict[str, str]
    ) -> None:
        """Append performance metrics as ``** Key: Value`` comments.

        Parameters
        ----------
        f : TextIO
            Open file handle.
        performance : dict[str, str]
            Metric name → formatted value string.
        """
        f.write("\n** Expected Performance Values:\n")
        for key, value in performance.items():
            f.write(f"** {key}: {value}\n")

    def _write_voltages(
        self, f: TextIO, voltages: dict[str, float]
    ) -> None:
        """Append net voltages as ``** Net <name>: <voltage> V`` comments.

        Parameters
        ----------
        f : TextIO
            Open file handle.
        voltages : dict[str, float]
            Net name → voltage [V].
        """
        f.write("\n** Expected Voltages:\n")
        for name, voltage in voltages.items():
            f.write(f"** {name}: {voltage} V\n")

    def _write_currents(
        self, f: TextIO, currents: dict[str, float]
    ) -> None:
        """Append device currents as ``** Component <name>: <current> muA`` comments.

        Parameters
        ----------
        f : TextIO
            Open file handle.
        currents : dict[str, float]
            Device name → current [µA].
        """
        f.write("\n** Expected Currents:\n")
        for name, current in currents.items():
            f.write(f"** {name}: {current} muA\n")


# ── ACST-compatible topology-library netlist writer ───────────────────────


class AcstNetlistWriter:
    """Write a :class:`~core.Circuit` to ACST topology-library ``.ckt`` format.

    Mirrors the unsized netlists ACST's ``TopologyLibraryGeneration`` emits
    under ``SingleOutputOpAmps/`` / ``FullyDifferentialOpAmps/`` /
    ``ComplementaryOpAmps/``::

        .suckt  one_stage_single_output_op_amp1 ibias in1 in2 out source_nmos source_pmos
        M1 FirstStageYout1 FirstStageYout1 source_nmos source_nmos nmos
        ...
        .end one_stage_single_output_op_amp1

    Differences from the native :class:`HSpiceWriter` (``.MACRO``/``.EOM``):

    * ``.suckt`` / ``.end`` keywords instead of ``.MACRO`` / ``.EOM``;
    * short ``nmos`` / ``pmos`` model tokens (ACST level-1 names) instead of
      ``nmos4`` / ``pmos4``;
    * an explicit *bulk* column that defaults to the source net (the topogen
      model carries no bulk pin), matching ACST's ``drain gate source bulk``;
    * no sizing parameters — the generated library is unsized.

    Pins absent from a device (the topogen connectivity is still partial for
    some generated stages) are skipped, mirroring :class:`HSpiceWriter`.
    """

    #: Canonical op-amp interface ports, in ACST's ``.suckt`` order.
    DEFAULT_PORTS: tuple[str, ...] = (
        "ibias", "in1", "in2", "out", "source_nmos", "source_pmos",
    )

    _MODEL_NAME: dict[TechType, str] = {TechType.N: "nmos", TechType.P: "pmos"}

    def write(
        self,
        circuit: Circuit,
        filepath: str | Path,
        *,
        name: str | None = None,
        ports: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        """Write *circuit* to *filepath* as an ACST ``.ckt`` topology netlist.

        Parameters
        ----------
        circuit : Circuit
            The (unsized) topology to serialise.
        filepath : str | Path
            Output ``.ckt`` path.
        name : str | None
            Macro/subcircuit name written on the ``.suckt`` / ``.end`` lines
            and expected to match the file stem.  Defaults to ``circuit.name``.
        ports : sequence[str] | None
            Interface port list for the ``.suckt`` header.  Defaults to
            :attr:`DEFAULT_PORTS`.
        """
        macro_name = name or circuit.name
        key = self.content_key(circuit, ports=ports)

        lines: list[str] = [f".suckt  {macro_name} {key[0]}"]
        lines.extend(key[1:])
        lines.append(f".end {macro_name}")
        Path(filepath).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def content_key(
        self,
        circuit: Circuit,
        *,
        ports: tuple[str, ...] | list[str] | None = None,
    ) -> tuple[str, ...]:
        """Name-independent serialisation of *circuit*.

        The first element is the joined port list, the rest are the device
        lines — exactly the netlist :meth:`write` emits minus the
        ``.suckt``/``.end`` name lines.  Two topologies with equal keys
        serialise to identical netlists up to the macro name, which is how
        :meth:`~synthesis.library.TopologyLibrary.to_acst_directory`
        de-duplicates structural duplicates at emission (issue #48).
        """
        port_list = list(ports) if ports is not None else list(self.DEFAULT_PORTS)
        return (" ".join(port_list),
                *(self._format_device_line(d) for d in circuit.devices))

    def _format_device_line(self, device: Device) -> str:
        """Format one device line.

        MOSFETs render as ``name drain gate source bulk model`` (bulk defaults
        to the source net — the topogen model has no bulk pin); capacitors as
        ``name plus minus`` (no model token), matching acst's
        ``c_…_Capacitor_N out sourceNmos``.  Missing pins are skipped — the same
        graceful behaviour as :meth:`HSpiceWriter._format_device_line`.
        """
        def net_of(pin: PinType) -> str | None:
            return device.get_net(pin).name if pin in device.terminals else None

        if device.device_type == DeviceType.CAPACITOR:
            plus, minus = net_of(PinType.PLUS), net_of(PinType.MINUS)
            return " ".join([device.name, *(c for c in (plus, minus) if c is not None)])

        drain = net_of(PinType.DRAIN)
        gate = net_of(PinType.GATE)
        source = net_of(PinType.SOURCE)
        bulk = net_of(PinType.BULK) or source

        parts: list[str] = [device.name]
        parts += [col for col in (drain, gate, source, bulk) if col is not None]

        if device.device_type == DeviceType.MOSFET:
            model = self._MODEL_NAME.get(device.tech_type)
            if model is not None:
                parts.append(model)
        return " ".join(parts)
