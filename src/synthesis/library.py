"""Topology library data structures for synthesis.

Provides:
  - ``TopologySpec``  — metadata record for one op-amp topology
  - ``TopologyLibrary`` — keyed collection of specs + circuits, with
    filtering, serialisation (to/from directory), and lookup helpers.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.device import TechType

# ---------------------------------------------------------------------------
# TopologySpec
# ---------------------------------------------------------------------------

@dataclass
class TopologySpec:
    """Immutable metadata record for a single op-amp topology.

    Attributes
    ----------
    id:
        Unique integer identifier, assigned by :class:`TopologyLibrary` when
        the topology is added (or set explicitly during deserialisation).
    name:
        Human-readable name, e.g. ``"one_stage_nmos_simple"``.
    num_stages:
        Number of amplification stages — ``1`` or ``2``.
    is_complementary:
        ``True`` when the input differential pair uses NMOS transistors
        (complementary input).  ``False`` for PMOS input (non-complementary).
    is_fully_differential:
        ``True`` for fully-differential output; ``False`` for single-ended.
    input_tech:
        Technology type of the input differential pair.  One of
        :attr:`~core.device.TechType.N` or
        :attr:`~core.device.TechType.P`.
    has_cascode:
        Per-block cascode flag dict, e.g.
        ``{"tc1": True, "load1": False, "tc2": False, "load2": True}``.
        An absent key means *not cascoded* for that block.
    """

    id: int
    name: str
    num_stages: int
    is_complementary: bool
    is_fully_differential: bool
    input_tech: TechType
    has_cascode: dict[str, bool] = field(default_factory=dict)
    is_symmetrical: bool = False

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return {
            "id": self.id,
            "name": self.name,
            "num_stages": self.num_stages,
            "is_complementary": self.is_complementary,
            "is_fully_differential": self.is_fully_differential,
            "input_tech": self.input_tech.value,
            "has_cascode": self.has_cascode,
            "is_symmetrical": self.is_symmetrical,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TopologySpec":
        """Reconstruct a ``TopologySpec`` from a serialised dict."""
        return cls(
            id=d["id"],
            name=d["name"],
            num_stages=d["num_stages"],
            is_complementary=d["is_complementary"],
            is_fully_differential=d["is_fully_differential"],
            input_tech=TechType(d["input_tech"]),
            has_cascode=d.get("has_cascode", {}),
            is_symmetrical=d.get("is_symmetrical", False),
        )

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def category(self) -> str:
        """Return the output-directory category name for this topology.

        Used by :meth:`TopologyLibrary.to_directory` to place each
        ``.ckt`` file in the correct sub-directory.

        Returns one of:
          * ``"one_stage_single_output"``
          * ``"one_stage_fully_differential"``
          * ``"two_stage_single_output"``
          * ``"two_stage_fully_differential"``
        """
        stages = "one_stage" if self.num_stages == 1 else "two_stage"
        output = "fully_differential" if self.is_fully_differential else "single_output"
        return f"{stages}_{output}"

    def acst_category(self) -> str:
        """Return the ACST output-directory name for this topology.

        ACST's ``TopologyLibraryGeneration`` splits the library into three
        top-level buckets (independent of stage count):

          * ``"ComplementaryOpAmps"``      — complementary (NMOS+PMOS) input pair
          * ``"FullyDifferentialOpAmps"``  — fully-differential output
          * ``"SingleOutputOpAmps"``       — everything else (incl. symmetrical)

        Used by :meth:`TopologyLibrary.to_acst_directory`.
        """
        if self.is_complementary:
            return "ComplementaryOpAmps"
        if self.is_fully_differential:
            return "FullyDifferentialOpAmps"
        return "SingleOutputOpAmps"

    def acst_name_prefix(self) -> str:
        """Return the ACST file-name prefix for this topology.

        Mirrors ACST's per-category naming, e.g.
        ``one_stage_single_output_op_amp`` /
        ``two_stage_fully_differential_op_amp`` / ``complementary_op_amp``.
        :meth:`TopologyLibrary.to_acst_directory` appends a per-prefix running
        index to form the full name (``…_op_amp1``, ``…_op_amp2``, …).

        .. note::
            ACST distinguishes a two-stage op-amp's first/second stage indices
            (``…_op_amp_N_M``) and a ``symmetrical_op_amp`` sub-family; pyckt's
            :class:`TopologySpec` does not carry those, so a single running
            index is used and symmetrical stages fold into ``single_output``.
        """
        if self.is_complementary:
            return "complementary_op_amp"
        if self.is_symmetrical:
            return "symmetrical_op_amp"
        stage = "one_stage" if self.num_stages == 1 else "two_stage"
        kind = "fully_differential" if self.is_fully_differential else "single_output"
        return f"{stage}_{kind}_op_amp"

    def __repr__(self) -> str:
        return (
            f"TopologySpec(id={self.id}, name={self.name!r}, "
            f"num_stages={self.num_stages}, "
            f"complementary={self.is_complementary}, "
            f"fully_diff={self.is_fully_differential}, "
            f"input_tech={self.input_tech.value!r})"
        )


# ---------------------------------------------------------------------------
# TopologyLibrary
# ---------------------------------------------------------------------------

_SPEC_FILENAME = "topology_{id:04d}.json"
_CKT_FILENAME  = "topology_{id:04d}.ckt"

_CKT_TEMPLATE = """\
** Name: {name}
** Id: {id}
** Stages: {num_stages}
** Complementary: {is_complementary}
** FullyDifferential: {is_fully_differential}
** InputTech: {input_tech}
** Cascode: {has_cascode}

.MACRO {name} ibias in1 in2 out sourceNmos sourcePmos
** (placeholder — implement in Phase 2 with real netlist)
.EOM {name}
"""


class TopologyLibrary:
    """Keyed collection of op-amp topologies.

    Maps to the C++ ``Synthesis::Library``.

    Each topology is stored under its :attr:`TopologySpec.id` key.  The
    library can be populated programmatically via :meth:`add`, filtered by
    structural attributes via :meth:`filter`, saved to a directory of HSpice
    files via :meth:`to_directory`, and reloaded via
    :meth:`from_directory`.

    Parameters
    ----------
    (none)

    Examples
    --------
    >>> lib = TopologyLibrary()
    >>> spec = TopologySpec(id=1, name="simple_ota", num_stages=1,
    ...                     is_complementary=False, is_fully_differential=False,
    ...                     input_tech=TechType.N)
    >>> lib.add(spec, circuit=None)
    >>> lib.size()
    1
    >>> lib.filter(num_stages=1)
    [TopologySpec(id=1, ...)]
    """

    def __init__(self) -> None:
        self.topologies: dict[int, TopologySpec] = {}
        # ``circuits`` holds the associated topogen Circuit (or None for
        # stubs / loaded-from-directory entries).
        self.circuits: dict[int, Any] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, spec: TopologySpec, circuit: Any = None) -> None:
        """Add *spec* (and optional *circuit*) to the library.

        Parameters
        ----------
        spec:
            Topology metadata.  ``spec.id`` must be unique within this
            library; a duplicate id will silently overwrite the old entry.
        circuit:
            Associated topogen :class:`~topogen.common.circuit.Circuit`
            object, or ``None`` when the circuit is not yet available
            (e.g. entries loaded from directory).
        """
        self.topologies[spec.id] = spec
        self.circuits[spec.id] = circuit

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def size(self) -> int:
        """Return the number of topologies in the library."""
        return len(self.topologies)

    def get_circuit(self, topology_id: int) -> Any:
        """Return the topogen Circuit for *topology_id*.

        Raises
        ------
        KeyError
            If *topology_id* is not in the library.
        """
        return self.circuits[topology_id]

    def filter(self, **criteria) -> list[TopologySpec]:
        """Filter topologies by one or more exact-match criteria.

        All supplied keyword arguments must match the corresponding
        :class:`TopologySpec` attribute.  Unknown keys are silently ignored
        (``getattr`` returns ``None`` which won't match any value).

        Parameters
        ----------
        **criteria:
            Attribute-name / value pairs, e.g.
            ``num_stages=2``, ``is_complementary=False``.

        Returns
        -------
        list[TopologySpec]
            Matching specs in ascending ``id`` order.

        Examples
        --------
        >>> lib.filter(num_stages=2, is_complementary=False)
        """
        results: list[TopologySpec] = list(self.topologies.values())
        for key, value in criteria.items():
            results = [t for t in results if getattr(t, key, None) == value]
        return sorted(results, key=lambda s: s.id)

    def ids(self) -> list[int]:
        """Return all topology IDs in ascending order."""
        return sorted(self.topologies.keys())

    # ------------------------------------------------------------------
    # Serialisation: to_directory / from_directory
    # ------------------------------------------------------------------

    def to_directory(self, dir_path: str) -> None:
        """Write every topology to *dir_path* as a ``.ckt`` + ``.json`` pair.

        The directory is created if it does not exist.  Topologies are
        grouped into category sub-directories (see
        :meth:`TopologySpec.category`):

        .. code-block:: text

            dir_path/
            ├── one_stage_single_output/
            │   ├── topology_0001.ckt
            │   ├── topology_0001.json
            │   └── ...
            ├── one_stage_fully_differential/
            │   └── ...
            ├── two_stage_single_output/
            │   └── ...
            └── two_stage_fully_differential/
                └── ...

        Parameters
        ----------
        dir_path:
            Root directory for the output.
        """
        root = Path(dir_path)
        root.mkdir(parents=True, exist_ok=True)

        for spec in self.topologies.values():
            cat_dir = root / spec.category()
            cat_dir.mkdir(parents=True, exist_ok=True)

            # --- HSpice stub netlist ---
            ckt_path = cat_dir / _CKT_FILENAME.format(id=spec.id)
            ckt_content = _CKT_TEMPLATE.format(
                name=spec.name,
                id=spec.id,
                num_stages=spec.num_stages,
                is_complementary=spec.is_complementary,
                is_fully_differential=spec.is_fully_differential,
                input_tech=spec.input_tech.value,
                has_cascode=json.dumps(spec.has_cascode),
            )
            ckt_path.write_text(ckt_content)

            # --- JSON metadata sidecar ---
            json_path = cat_dir / _SPEC_FILENAME.format(id=spec.id)
            json_path.write_text(json.dumps(spec.to_dict(), indent=2))

    def to_acst_directory(self, dir_path: str) -> dict[str, int]:
        """Write the library in ACST topology-library format.

        Emits one ``.ckt`` netlist per topology (via
        :class:`~ckt_io.hspice_writer.AcstNetlistWriter`) grouped into ACST's
        three category directories::

            dir_path/
            ├── SingleOutputOpAmps/
            │   ├── one_stage_single_output_op_amp1.ckt
            │   ├── two_stage_single_output_op_amp1.ckt
            │   └── ...
            ├── FullyDifferentialOpAmps/
            │   └── ...
            └── ComplementaryOpAmps/
                └── ...

        Per-topology file names use :meth:`TopologySpec.acst_name_prefix` plus a
        running index assigned in ascending ``id`` order.  Topologies whose
        circuit failed to convert (``circuit is None``) are skipped.

        Parameters
        ----------
        dir_path:
            Root directory for the output (created if absent).

        Returns
        -------
        dict[str, int]
            Number of netlists written per ACST category directory.
        """
        from ckt_io.hspice_writer import AcstNetlistWriter

        root = Path(dir_path)
        root.mkdir(parents=True, exist_ok=True)
        writer = AcstNetlistWriter()

        per_prefix: Counter[str] = Counter()
        per_category: Counter[str] = Counter()

        for spec in sorted(self.topologies.values(), key=lambda s: s.id):
            circuit = self.circuits.get(spec.id)
            if circuit is None:
                continue  # unconverted topology — nothing to serialise

            prefix = spec.acst_name_prefix()
            per_prefix[prefix] += 1
            name = f"{prefix}{per_prefix[prefix]}"

            cat = spec.acst_category()
            cat_dir = root / cat
            cat_dir.mkdir(parents=True, exist_ok=True)
            writer.write(circuit, cat_dir / f"{name}.ckt", name=name)
            per_category[cat] += 1

        return dict(per_category)

    @classmethod
    def from_directory(cls, dir_path: str) -> "TopologyLibrary":
        """Load a :class:`TopologyLibrary` from a directory written by
        :meth:`to_directory`.

        Reads every ``topology_NNNN.json`` sidecar file found under
        *dir_path* (recursively).  The associated ``topology_NNNN.ckt``
        files are verified to exist but their content is not parsed in
        Phase 1 (the circuit field is set to ``None``).

        Parameters
        ----------
        dir_path:
            Root directory previously written by :meth:`to_directory`.

        Returns
        -------
        TopologyLibrary
            Populated library with ``circuit=None`` for every entry.

        Raises
        ------
        FileNotFoundError
            If *dir_path* does not exist.
        """
        root = Path(dir_path)
        if not root.exists():
            raise FileNotFoundError(f"Library directory not found: {dir_path}")

        lib = cls()
        for json_path in sorted(root.rglob("topology_*.json")):
            spec = TopologySpec.from_dict(json.loads(json_path.read_text()))
            lib.add(spec, circuit=None)

        return lib

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return self.size()

    def __repr__(self) -> str:
        return f"TopologyLibrary(size={self.size()})"
