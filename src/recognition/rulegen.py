"""Sizing rule generation from recognised structures.

Extracts sizing constraints (equal W/L, matched pairs, etc.) implied by
the hierarchical structure overlay produced by the recognition engine.

C++ ref: ``Control/src/RuleGeneration.cpp``
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import StructureCircuits

# ── Rule dataclasses ─────────────────────────────────────────────────

@dataclass
class SizingRule:
    """Base sizing rule: structure name, type tag, device list, description."""
    structure_name: str
    rule_type: str
    devices: list[str]
    description: str

class EqualWLRule(SizingRule):
    """Transistors must have equal W/L ratios."""

class EqualLengthRule(SizingRule):
    """Transistors must have equal channel length."""

class EqualCurrentRule(SizingRule):
    """Transistors must carry equal current."""

class MatchedPairRule(SizingRule):
    """Transistors are matched (same dimensions, same orientation)."""


# ── Rule map ─────────────────────────────────────────────────────────

_RULE_MAP = {
    "CurrentMirror":     lambda n, d: [EqualLengthRule(n, "equal_length", d, f"{n}: equal L"),
                                        EqualWLRule(n, "equal_wl", d, f"{n}: equal W/L")],
    "DifferentialPair":  lambda n, d: [MatchedPairRule(n, "matched", d, f"{n}: matched pair")],
    "DifferentialStage": lambda n, d: [MatchedPairRule(n, "matched", d, f"{n}: matched pair")],
    "Cascode":           lambda n, d: [EqualLengthRule(n, "equal_length", d, f"{n}: equal L")],
    "VoltageBias":       lambda n, d: [EqualLengthRule(n, "equal_length", d, f"{n}: equal L")],
}


# ── Generator ────────────────────────────────────────────────────────

class RuleGenerator:
    """Extract sizing rules from recognised structures."""

    def generate(self, sc: StructureCircuits) -> list[SizingRule]:
        rules: list[SizingRule] = []
        for s in sc.structures_without_parents:
            devs = [d.name for d in s.devices]
            if not devs:
                continue
            for key, fn in _RULE_MAP.items():
                if key in s.name:
                    rules.extend(fn(s.name, devs)); break
        return self._deduplicate(rules)

    @staticmethod
    def _deduplicate(rules: list[SizingRule]) -> list[SizingRule]:
        seen: set[tuple] = set(); out: list[SizingRule] = []
        for r in rules:
            k = (r.rule_type, tuple(sorted(r.devices)))
            if k not in seen: seen.add(k); out.append(r)
        return out
