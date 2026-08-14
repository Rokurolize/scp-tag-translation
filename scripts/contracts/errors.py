"""Stable exception categories for validated input and mapping conflicts."""

from __future__ import annotations


class InvalidDomainInputError(ValueError):
    """Input or configuration data failed a domain validation rule."""


class MappingConflictError(ValueError):
    """Two valid mapping records resolve to incompatible targets."""


__all__ = ["InvalidDomainInputError", "MappingConflictError"]
