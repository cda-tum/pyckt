"""Output writers for sizing results.

Provides XML serialisation for solver results and a lightweight HSpice netlist
rewriter that substitutes solved transistor dimensions into an existing input
netlist.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement, indent, tostring

from ckt_io.acst_xml import make_root, slash, write_tree

from .result import DeviceSizing, ExpectedPerformance, SizingResult


class SizingXMLWriter:
	"""Write a :class:`SizingResult` to an ACST-style XML file."""

	def __init__(self, result: SizingResult) -> None:
		self._result = result

	def build_tree(self) -> Element:
		"""Build and return the root ``<SizingResult>`` element."""
		attrs: dict[str, str] = {
			"status": self._result.solver_status,
			"iterations": str(self._result.iterations),
			"solve_time_seconds": f"{self._result.solve_time_seconds:.6g}",
		}
		if self._result.objective_value is not None:
			attrs["objective_value"] = f"{self._result.objective_value:.6g}"
		root = Element("SizingResult", **attrs)

		if not self._result.devices:
			# Infeasible / timeout — emit an explanatory element instead of an
			# empty Devices block so downstream tools get a clear signal.
			SubElement(
				root,
				"NoSolution",
				reason=self._result.solver_status,
			)
			return root

		devices = SubElement(root, "Devices")
		for name in self._result.device_names:
			self._add_device(devices, self._result.get_device(name))

		self._add_performance(root, self._result.performance)
		return root

	def write(self, path: str | Path) -> None:
		"""Write the XML representation to *path*."""
		root = self.build_tree()
		indent(root, space="  ")
		tree = ElementTree(root)
		tree.write(str(path), encoding="unicode", xml_declaration=True)

	def to_string(self) -> str:
		"""Return the XML representation as a string."""
		root = self.build_tree()
		indent(root, space="  ")
		return tostring(root, encoding="unicode")

	@staticmethod
	def _add_device(parent: Element, device: DeviceSizing) -> None:
		element = SubElement(parent, "Device", name=device.name)
		SubElement(element, "Width", unit="um").text = str(device.width)
		SubElement(element, "Length", unit="um").text = str(device.length)
		SubElement(element, "Current", unit="nA").text = str(device.current)
		SubElement(element, "Vgs", unit="mV").text = str(device.vgs)
		SubElement(element, "Vds", unit="mV").text = str(device.vds)
		SubElement(element, "Vov", unit="mV").text = str(device.vov)
		SubElement(element, "Gm", unit="nA/V").text = str(device.gm)
		SubElement(element, "Gds", unit="nA/V").text = str(device.gds)
		SubElement(element, "Area", unit="um2").text = str(device.area)

	@staticmethod
	def _add_performance(parent: Element, perf: ExpectedPerformance) -> None:
		element = SubElement(parent, "ExpectedPerformance")
		SubElement(element, "Gain", unit="dB").text = f"{perf.gain_db:.6g}"
		SubElement(element, "TransitFrequency", unit="MHz").text = (
			f"{perf.transit_freq_mhz:.6g}"
		)
		SubElement(element, "SlewRate", unit="V/us").text = (
			f"{perf.slew_rate:.6g}"
		)
		SubElement(element, "Power", unit="mW").text = f"{perf.power_mw:.6g}"
		SubElement(element, "TotalArea", unit="um2").text = (
			f"{perf.total_area_um2:.6g}"
		)
		SubElement(element, "PhaseMargin", unit="deg").text = (
			f"{perf.phase_margin_deg:.6g}"
		)
		SubElement(element, "VoutMin", unit="V").text = f"{perf.vout_min_v:.6g}"
		SubElement(element, "VoutMax", unit="V").text = f"{perf.vout_max_v:.6g}"


class AcstSizingXMLWriter:
	"""Write a :class:`SizingResult` in the C++ ACST XML schema.

	Mirrors ``acst``'s ``<acst_results>/<automatic_sizing-results>`` output so
	the two tools can be diffed:

	* ``<ExpectedPerformance>`` with acst element names + unit spellings
	  (``Gain`` dB, ``Power`` m_W, ``Area`` (mu_m)^2, ``TransitFrequency`` M_Hz,
	  ``SlewRate`` V/mum_s, ``PhaseMargin`` degree, Max/MinimumOutputVoltage V);
	* per-device drain current under a separate ``<Currents unit="mu_A">``
	  (converted nA → µA);
	* ``<Dimensions><Transistors><Transistor>`` with ``<Width>``/``<Length>``
	  in ``mu_m``, and ``<Dimensions><Capacitors><Capacitor>`` with a
	  ``<Value>`` in ``p_F``;
	* a per-net ``<Voltages unit="V">`` section;
	* leading-slash component/transistor names.

	``ExpectedPerformance`` carries acst's full field set:
	``TransitFrequencyWithErrorFactor`` (always), and — when the result
	provides them — ``CMRR``, ``negPSRR``, ``posPSRR`` and the common-mode
	input range (acst emits these under ``if(hasCMRR())`` guards, so they are
	written only when populated).  ``<Voltages>`` and ``<Capacitors>`` are
	always emitted as section shells, matching acst even when empty.
	"""

	def __init__(self, result: SizingResult) -> None:
		self._result = result

	def build_tree(self) -> Element:
		root, results = make_root("automatic_sizing-results")
		if not self._result.devices:
			SubElement(results, "NoSolution", reason=self._result.solver_status)
			return root
		self._add_performance(results, self._result.performance)
		self._add_voltages(results)
		self._add_currents(results)
		self._add_dimensions(results)
		return root

	def write(self, path: str | Path) -> None:
		write_tree(self.build_tree(), path)

	def to_string(self) -> str:
		root = self.build_tree()
		indent(root, space="\t")
		return tostring(root, encoding="unicode")

	@staticmethod
	def _num(value: float) -> str:
		return f"{value:.6g}"

	def _add_performance(self, parent: Element, perf: ExpectedPerformance) -> None:
		el = SubElement(parent, "ExpectedPerformance")
		SubElement(el, "Gain", unit="dB").text = self._num(perf.gain_db)
		SubElement(el, "Power", unit="m_W").text = self._num(perf.power_mw)
		SubElement(el, "Area", unit="(mu_m)^2").text = self._num(perf.total_area_um2)
		SubElement(el, "TransitFrequency", unit="M_Hz").text = (
			self._num(perf.transit_freq_mhz)
		)
		# acst always emits this node; when the error-derated value is not
		# computed it collapses to the nominal transit frequency.
		tf_ef = (perf.transit_freq_error_factor_mhz
				 if perf.transit_freq_error_factor_mhz is not None
				 else perf.transit_freq_mhz)
		SubElement(el, "TransitFrequencyWithErrorFactor", unit="M_Hz").text = (
			self._num(tf_ef)
		)
		SubElement(el, "SlewRate", unit="V/mum_s").text = self._num(perf.slew_rate)
		SubElement(el, "PhaseMargin", unit="degree").text = (
			self._num(perf.phase_margin_deg)
		)
		# acst's units verbatim: CMRR in dB, PSRR nodes carry "degree".
		if perf.cmrr_db is not None:
			SubElement(el, "CMRR", unit="dB").text = self._num(perf.cmrr_db)
		if perf.neg_psrr_deg is not None:
			SubElement(el, "negPSRR", unit="degree").text = self._num(perf.neg_psrr_deg)
		if perf.pos_psrr_deg is not None:
			SubElement(el, "posPSRR", unit="degree").text = self._num(perf.pos_psrr_deg)
		SubElement(el, "MaximumOutputVoltage", unit="V").text = (
			self._num(perf.vout_max_v)
		)
		SubElement(el, "MinimumOutputVoltage", unit="V").text = (
			self._num(perf.vout_min_v)
		)
		if perf.max_cm_input_v is not None:
			SubElement(el, "maxCommonModeInputVoltage", unit="V").text = (
				self._num(perf.max_cm_input_v)
			)
		if perf.min_cm_input_v is not None:
			SubElement(el, "minCommonModeInputVoltage", unit="V").text = (
				self._num(perf.min_cm_input_v)
			)

	def _add_voltages(self, parent: Element) -> None:
		el = SubElement(parent, "Voltages", unit="V")
		for name in sorted(self._result.net_voltages):
			SubElement(el, "Net", name=slash(name)).text = (
				self._num(self._result.net_voltages[name])
			)

	def _add_currents(self, parent: Element) -> None:
		el = SubElement(parent, "Currents", unit="mu_A")
		for name in self._result.device_names:
			dev = self._result.get_device(name)
			SubElement(el, "Component", name=slash(name)).text = (
				self._num(dev.current_ua)
			)

	def _add_dimensions(self, parent: Element) -> None:
		dims = SubElement(parent, "Dimensions")
		transistors = SubElement(dims, "Transistors")
		for name in self._result.device_names:
			dev = self._result.get_device(name)
			t = SubElement(transistors, "Transistor", name=slash(name))
			SubElement(t, "Width", unit="mu_m").text = str(dev.width)
			SubElement(t, "Length", unit="mu_m").text = str(dev.length)
		capacitors = SubElement(dims, "Capacitors")
		for name in sorted(self._result.capacitors):
			c = SubElement(capacitors, "Capacitor", name=slash(name))
			SubElement(c, "Value", unit="p_F").text = (
				self._num(self._result.capacitors[name])
			)


class SizedCircuitWriter:
	"""Rewrite an HSpice netlist with solved transistor widths and lengths."""

	def __init__(self, result: SizingResult) -> None:
		self._result = result

	def write(self, input_netlist: str | Path, output_netlist: str | Path) -> None:
		"""Read *input_netlist*, substitute solved W/L values, write output."""
		input_path = Path(input_netlist)
		output_path = Path(output_netlist)
		text = input_path.read_text(encoding="utf-8", errors="ignore")
		output_path.write_text(self.render(text), encoding="utf-8")

	def render(self, netlist_text: str) -> str:
		"""Return the sized version of *netlist_text*."""
		lines = netlist_text.splitlines()
		rewritten = [self._rewrite_line(line) for line in lines]
		trailing = "\n" if netlist_text.endswith("\n") else ""
		return "\n".join(rewritten) + trailing

	def _rewrite_line(self, line: str) -> str:
		stripped = line.strip()
		if not stripped:
			return line
		if stripped.startswith(("*", ".", "+")):
			return line

		parts = stripped.split()
		device_name = parts[0]
		if device_name not in self._result.devices:
			return line

		sizing = self._result.get_device(device_name)
		updated = line
		updated = self._replace_or_append_parameter(
			updated, "W", self._format_um_as_meter(sizing.width)
		)
		updated = self._replace_or_append_parameter(
			updated, "L", self._format_um_as_meter(sizing.length)
		)
		return updated

	@staticmethod
	def _replace_or_append_parameter(line: str, name: str, value: str) -> str:
		pattern = re.compile(rf"\b{name}\s*=\s*[^\s]+", flags=re.IGNORECASE)
		replacement = f"{name}={value}"
		if pattern.search(line):
			return pattern.sub(replacement, line, count=1)
		return f"{line} {replacement}"

	@staticmethod
	def _format_um_as_meter(value_um: int) -> str:
		return f"{value_um}e-6"
