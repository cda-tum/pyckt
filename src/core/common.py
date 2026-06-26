from __future__ import annotations


class CoreError(Exception):
  """Base exception for all core errors."""


class DuplicateDeviceError(CoreError):
  pass


class DuplicateNetError(CoreError):
  pass


class UnknownDeviceError(CoreError):
  pass


class UnknownNetError(CoreError):
  pass


class InvalidPinError(CoreError):
  pass


class ValidationError(CoreError):
  pass


class DuplicatePortError(CoreError):
  pass


class UnknownPortError(CoreError):
  pass


class UnknownParameterError(CoreError):
  pass


def require(condition: bool, message: str, exc_type: type[CoreError] = ValidationError) -> None:
  """Raise a core exception if condition is not satisfied."""
  if not condition:
    raise exc_type(message)


def require_non_empty(value: str, field_name: str) -> None:
  require(bool(value and value.strip()), f"{field_name} must be non-empty")


import argparse  # noqa: E402


class AbstractAnalysis:
    """
    Base class for all analysis types.
    Mirrors Control::AbstractAnalysis / Control::CircuitAnalysis.

    Every analysis follows the three-phase pattern:
      initialize() → compute() → write()
    """

    def __init__(self, args: argparse.Namespace):
        self.args = args

    def initialize(self) -> None:
        raise NotImplementedError(f"{type(self).__name__}.initialize()")

    def compute(self) -> None:
        raise NotImplementedError(f"{type(self).__name__}.compute()")

    def write(self) -> None:
        raise NotImplementedError(f"{type(self).__name__}.write()")


__all__ = [
    "AbstractAnalysis",
    "CoreError",
    "DuplicateDeviceError",
    "DuplicateNetError",
    "UnknownDeviceError",
    "UnknownNetError",
    "InvalidPinError",
    "ValidationError",
    "DuplicatePortError",
    "UnknownPortError",
    "UnknownParameterError",
    "require",
    "require_non_empty",
]
