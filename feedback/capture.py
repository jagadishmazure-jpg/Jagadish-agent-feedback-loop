"""Feedback event capture: explicit ratings/corrections plus implicit signals.

Every event carries session_id, timestamp, agent_version and the triggering
turn_id so feedback can be linked back to the exact production interaction
that produced it.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field


EXPLICIT_TYPES = ("rating", "correction", "thumbs")
IMPLICIT_TYPES = ("rephrase_detected", "tool_override", "session_abandoned")
ALL_TYPES = EXPLICIT_TYPES + IMPLICIT_TYPES


@dataclass
class FeedbackEvent:
    event_type: str
    session_id: str
    turn_id: str
    agent_version: str
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    # explicit payloads
    rating: int | None = None        # "rating": 1..5
    correction: str | None = None    # "correction": the right answer
    up: bool | None = None           # "thumbs": True/False
    # context for corrections / implicit signals
    user_query: str = ""
    agent_answer: str = ""
    detail: str = ""                 # free text, mostly for implicit events

    def __post_init__(self) -> None:
        if self.event_type not in ALL_TYPES:
            raise ValueError(f"unknown event_type {self.event_type!r}; "
                             f"expected one of {ALL_TYPES}")
        if not self.session_id:
            raise ValueError("session_id is required")
        if not self.turn_id:
            raise ValueError("turn_id is required")
        if self.event_type == "rating":
            if self.rating is None or not 1 <= self.rating <= 5:
                raise ValueError("rating events need rating in 1..5")
        if self.event_type == "correction":
            if not (self.correction or "").strip():
                raise ValueError("correction events need non-empty correction text")
        if self.event_type == "thumbs":
            if self.up is None:
                raise ValueError("thumbs events need up=True/False")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "FeedbackEvent":
        return cls(**d)


def capture_rating(session_id: str, turn_id: str, agent_version: str,
                   rating: int, user_query: str = "",
                   agent_answer: str = "") -> FeedbackEvent:
    """Explicit 1-5 star rating on a turn."""
    return FeedbackEvent("rating", session_id, turn_id, agent_version,
                         rating=rating, user_query=user_query,
                         agent_answer=agent_answer)


def capture_correction(session_id: str, turn_id: str, agent_version: str,
                       user_query: str, agent_answer: str,
                       correction: str) -> FeedbackEvent:
    """Explicit user correction: the agent said agent_answer, the user says
    the right answer is correction."""
    return FeedbackEvent("correction", session_id, turn_id, agent_version,
                         user_query=user_query, agent_answer=agent_answer,
                         correction=correction)


def capture_thumbs(session_id: str, turn_id: str, agent_version: str,
                   up: bool, user_query: str = "",
                   agent_answer: str = "") -> FeedbackEvent:
    """Explicit thumbs up/down on a turn."""
    return FeedbackEvent("thumbs", session_id, turn_id, agent_version, up=up,
                         user_query=user_query, agent_answer=agent_answer)


def capture_rephrase(session_id: str, turn_id: str, agent_version: str,
                     user_query: str, detail: str = "") -> FeedbackEvent:
    """Implicit signal: the user rephrased the question, i.e. the first
    answer did not satisfy them."""
    return FeedbackEvent("rephrase_detected", session_id, turn_id,
                         agent_version, user_query=user_query, detail=detail)


def capture_tool_override(session_id: str, turn_id: str, agent_version: str,
                          detail: str = "") -> FeedbackEvent:
    """Implicit signal: the user overrode / undid a tool call the agent made."""
    return FeedbackEvent("tool_override", session_id, turn_id, agent_version,
                         detail=detail)


def capture_abandonment(session_id: str, turn_id: str, agent_version: str,
                        detail: str = "") -> FeedbackEvent:
    """Implicit signal: the session was abandoned right after this turn."""
    return FeedbackEvent("session_abandoned", session_id, turn_id,
                         agent_version, detail=detail)
