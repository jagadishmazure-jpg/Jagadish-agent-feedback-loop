"""Feedback taxonomy as code: event types, severity mapping, retention hooks.

Centralizes the vocabulary so capture, store, miner and gate all agree on
what each signal means, how urgently it should be triaged, and how long the
raw event may be kept.
"""

from __future__ import annotations

EVENT_TYPES: dict[str, dict] = {
    "rating": {
        "kind": "explicit",
        "description": "1-5 star rating on a turn.",
        "severity": "low",
        "retention_days": 365,
    },
    "correction": {
        "kind": "explicit",
        "description": "User supplied the right answer; feeds the miner.",
        "severity": "high",
        "retention_days": 730,
    },
    "thumbs": {
        "kind": "explicit",
        "description": "Thumbs up/down on a turn.",
        "severity": "low",
        "retention_days": 365,
    },
    "rephrase_detected": {
        "kind": "implicit",
        "description": "User rephrased the question; the first answer failed.",
        "severity": "medium",
        "retention_days": 365,
    },
    "tool_override": {
        "kind": "implicit",
        "description": "User overrode or undid an agent tool call.",
        "severity": "high",
        "retention_days": 730,
    },
    "session_abandoned": {
        "kind": "implicit",
        "description": "Session ended right after this turn.",
        "severity": "medium",
        "retention_days": 180,
    },
}

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}


def _entry(event_type: str) -> dict:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event_type {event_type!r}")
    return EVENT_TYPES[event_type]


def describe(event_type: str) -> str:
    return _entry(event_type)["description"]


def kind_of(event_type: str) -> str:
    """'explicit' or 'implicit'."""
    return _entry(event_type)["kind"]


def severity_of(event_type: str) -> str:
    return _entry(event_type)["severity"]


def more_severe(a: str, b: str) -> str:
    """Return the more severe of two event types."""
    return a if SEVERITY_ORDER[severity_of(a)] >= SEVERITY_ORDER[severity_of(b)] else b


def retention_days(event_type: str, overrides: dict[str, int] | None = None) -> int:
    """Retention hook: per-type default, overridable by deployment policy."""
    if overrides and event_type in overrides:
        return overrides[event_type]
    return _entry(event_type)["retention_days"]
