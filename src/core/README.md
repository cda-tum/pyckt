# Core Package: Status & Next Steps

This file tracks what is done in `pyckt/src/pyckt/core/` and what remains.

## Current status snapshot

✅ Done:
- `common.py`: exception hierarchy + validation helpers + `__all__`
  (`DuplicatePortError`, `UnknownPortError`, `UnknownParameterError` added)
- `instance.py`: `CellTripleId`, `Instance` (with validated `connect()`,
  `set_param()`, `get_parameter()`)
- `device.py`: enums (`DeviceType` incl. `WIRE`, `TechType`, `PinType`),
  typed `PinTypeInfo` / `DeviceTypeInfo`, `DeviceTypeRegister`, `Device`
  with `cell_triple_id`, `InvalidPinError` on missing pin, `parameters`
  with `set_parameter()` / `get_parameter()`
- `net.py`: `SupplyType` enum, `Supply` dataclass (with VDD/GND/level),
  `NetId`, `Net` with typed supply, pin-type query methods, `clear_terminals()`
- `terminal.py`: `Terminal` (maps to C++ `Pin`, device-net edge)
- `port.py`: `PortType` enum (INPUT/OUTPUT/INOUT), `Port` class
  (circuit-boundary I/O, maps to C++ `Terminal`)
- `circuit.py`: holds devices, nets, terminals, instances, ports; duplicate
  checks (`DuplicateDeviceError`, `DuplicateNetError`, `DuplicatePortError`),
  unknown checks (`UnknownDeviceError`, `UnknownNetError`, `UnknownPortError`),
  `has_*` / `find_*` queries, `merge_nets()` for net shortening
- `__init__.py`: re-exports full public API including `Port`, `PortType`,
  `Supply`, `SupplyType`, `DeviceTypeInfo`, all exception types
- All imports are package-relative and cycle-safe (`TYPE_CHECKING`)
- `setup.cfg`: `package_dir = src` so `pip install -e .` works
- End-to-end integration test passes
- `tests/test_core.py` implemented and passing (34 tests)

## C++ cross-validation status

| Python file | C++ counterpart | Alignment status |
|---|---|---|
| `common.py` | `BacktraceAssert.h` | ✅ Exception hierarchy matches assert-style checks |
| `device.py` | `Device.h`, `DeviceType.h`, `TechType.h`, `PinType.h`, `DeviceTypeNames.h` | ✅ All device types incl. Wire; PinType matches xcat; typed `auto_connection`; `cell_triple_id` added; `parameters` added |
| `net.py` | `Net.h`, `Supply.h`, `NetId.h` | ✅ `Supply` with type + level; pin-type query methods; `clear_terminals()` for merge |
| `terminal.py` | `Pin.h` (NOT `Terminal.h`) | ✅ Correctly maps to C++ Pin (device↔net edge) |
| `port.py` | `Terminal.h`, `TerminalType.h` | ✅ Maps to C++ `Terminal` (circuit-boundary port with direction) |
| `circuit.py` | `Circuit.h` | ✅ Stores devices, nets, terminals, instances, ports; has_*/find_* methods; `merge_nets()` |
| `instance.py` | `Instance.h`, `CellTripleId.h` | ✅ Name + CellTripleId + connections + parameters with get/set |

> **Naming note:** Python `Terminal` = C++ `Pin` (the device-to-net connection).
> Python `Port` = C++ `Terminal` (circuit-level I/O port with direction).

---

## Priority: remaining work

All three planned enhancements are now complete. No blocking work remains.

---

## File-by-file status

### `common.py` ✅
- Lowest-level module; no sibling imports
- `__all__` in place
- Exceptions: `CoreError`, `DuplicateDeviceError`, `DuplicateNetError`,
  `DuplicatePortError`, `UnknownDeviceError`, `UnknownNetError`,
  `UnknownPortError`, `UnknownParameterError`, `InvalidPinError`,
  `ValidationError`

### `instance.py` ✅
- `connect()` validates non-empty pin/net names
- `set_param()` / `get_parameter()` for parameter storage
- `get_parameter()` raises `UnknownParameterError` on missing key

### `terminal.py` ✅
- Relative imports; `TYPE_CHECKING` for `Device`
- Runtime imports: `Net`, `PinType`

### `port.py` ✅ (NEW)
- `PortType` enum: `INPUT`, `OUTPUT`, `INOUT`
- `Port` class: `name`, `port_type`, optional `net`
- Convenience properties: `is_input`, `is_output`, `is_inout`

### `net.py` ✅
- `Supply` dataclass with `SupplyType` enum replaces loose `str`
- `get_terminals_by_type()`, `has_terminal_type()`, `has_terminals()`
- `clear_terminals()` for net merge support
- TYPE_CHECKING imports: `Terminal`, `PinType`

### `device.py` ✅
- `DeviceType.WIRE` added (matches C++ `DeviceTypeNames`)
- `PinTypeInfo.auto_connection` typed as `PinType | None`
- `DeviceTypeInfo` dataclass replaces loose `dict` in register
- `Device.cell_triple_id` optional field (matches C++ `Device::cellTripleId_`)
- `get_terminal()` raises `InvalidPinError` on missing pin
- `set_parameter()` / `get_parameter()` / `parameters` property
- `get_parameter()` raises `UnknownParameterError` on missing key

### `circuit.py` ✅
- `_terminals` list + `_instances` dict + `_ports` dict
- `add_device` / `add_net` / `add_port` raise on duplicates
- `find_device` / `find_net` / `find_port` raise on unknown
- `has_device` / `has_net` / `has_instance` / `has_port` / `has_terminals` / `has_instances` / `has_ports`
- `merge_nets(target, source)`: reassigns terminals, propagates supply, removes source

### `__init__.py` ✅
- Exports: `Circuit`, `Device`, `DeviceType`, `TechType`, `PinType`,
  `PinTypeInfo`, `DeviceTypeInfo`, `DeviceTypeRegister`, `Net`, `NetId`,
  `Supply`, `SupplyType`, `Terminal`, `Port`, `PortType`, `Instance`,
  `CellTripleId`, all exception types

---

## Cross-file import rules (enforced)

- **Inside `pyckt/core` files**: only relative imports (`from .device import ...`)
- For type-only references: `TYPE_CHECKING` + `from __future__ import annotations`
- Keep `common.py` dependency-free from sibling modules

---

## Tests status

`tests/test_core.py` is complete and passing.

Covered and validated:

1. Device/net/terminal wiring round-trip
2. Duplicate device/net/port errors
3. Unknown device/net/port errors
4. `find_or_create_net` idempotency
5. Missing pin handling (`InvalidPinError`)
6. `Device.get_net()` lookup after wiring
7. Supply flags and enum usage (`SupplyType` + `Supply`)
8. Net pin-type filtering helpers
9. `Instance.connect()` validation for empty/whitespace
10. Convenience filters and `has_*` query methods
11. Port model: add, find, types, duplicate/unknown errors
12. Device parameters: set, get, overwrite, unknown error
13. Instance parameters: set, get, unknown error
14. Net merge: terminal reassignment, supply propagation, self-merge noop, unknown error

Current result: ✅ `34 passed`

---

## Future work (beyond core)

- **Net global flag**: C++ Net has `isGlobal_` for global nets in hierarchy.
  Python has the field but no logic yet — add when hierarchical flattening needs it.
- **PropertyValue typing**: C++ has typed `PropertyValue` / `PropertyAssignment`.
  Python uses `str | float | int` which covers most cases but could be extended.

---

## Definition of done for core package

- ✅ All imports are relative and cycle-safe
- ✅ `__init__.py` exports the full public API
- ✅ Duplicate and unknown lookups raise core exceptions
- ✅ `Device.get_terminal()` raises `InvalidPinError` on missing pin
- ✅ Types aligned with C++ ACST (cross-validated)
- ✅ `pip install -e .` works (`setup.cfg` fixed)
- ✅ End-to-end integration test passes
- ✅ `tests/test_core.py` implemented and passing (34 tests)
- ✅ Circuit-level ports model (`Port` + `PortType`)
- ✅ Device/Instance parameter maps with get/set + error handling
- ✅ Net merge operations (`merge_nets` + `clear_terminals`)
