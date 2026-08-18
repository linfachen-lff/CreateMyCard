"""Search domain errors with stable machine-readable categories."""

from __future__ import annotations


class SearchError(Exception):
    """Base class for deterministic Search failures."""

    def __init__(self, code: str, message: str, *, pointer: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.pointer = pointer


class InvalidSearchRequest(SearchError):
    """The request is invalid and must be rejected at the API boundary."""


class ObservedShapeError(SearchError):
    """A JSON instance has no safe observable shape signature."""


class PayloadLimitError(SearchError):
    """A configured payload resource limit was exceeded."""


class TemplateValidationError(SearchError):
    """A Compact template is unsafe for its intended validation mode."""


class BindingError(SearchError):
    """A validated template cannot be bound to the current payload."""


class TemplateStoreError(SearchError):
    """A DAO could not read or update its SQLite template store."""
