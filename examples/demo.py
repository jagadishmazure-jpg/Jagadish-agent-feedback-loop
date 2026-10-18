"""Feedback flywheel end to end on synthetic data: capture, store, mine golden cases, gate a change."""
import tempfile
from pathlib import Path

from feedback.capture import (
    capture_abandonment,
    capture_correction,
    capture_rephrase,
    capture_thumbs,
)
from feedback.gate import RegressionGate
from feedback.miner import CorrectionMiner, GoldenCase
from feedback.store import FeedbackStore

store = FeedbackStore(Path(tempfile.mkdtemp()) / "feedback.jsonl")
for s, u in (("s1", "u1"), ("s2", "u2"), ("s3", "u3")):
    store.register_session(s, u)

events = [
    capture_correction("s1", "t1", "agent-v1", user_query="what is the refund window for damaged items",
                       agent_answer="No refunds.", correction="30 days for damaged items"),
    capture_correction("s2", "t4", "agent-v1", user_query="refund window for damaged items please",
                       agent_answer="7 days.", correction="30 days for damaged items"),
    capture_correction("s3", "t2", "agent-v1", user_query="how do I reset my account password",
                       agent_answer="Call support.", correction="Use the reset link on the sign-in page"),
    capture_rephrase("s1", "t2", "agent-v1", user_query="refund window damaged items"),
    capture_thumbs("s2", "t5", "agent-v1", up=False),
    capture_abandonment("s3", "t3", "agent-v1"),
    capture_thumbs("s-unknown", "t1", "agent-v1", up=True),  # orphan: no registered session
]
outcomes = [store.append(e) for e in events]
print(f"Captured {len(events)} events: {outcomes.count('stored')} stored, "
      f"{outcomes.count('quarantined')} quarantined (unknown session, kept for adoption)")

existing = [GoldenCase(input="what are your opening hours", expected="9 to 5 on weekdays", case_id="faq-hours")]
mined = CorrectionMiner().mine(store.query(event_type="correction"), existing=existing)
for c in mined:
    print(f"Mined {c.case_id}: {c.input!r} -> {c.expected!r} (from {len(c.source_event_ids)} correction(s), "
          f"needs review: {c.needs_review})")
golden = existing + mined

ANSWERS_V1 = {"what are your opening hours": "9 to 5 on weekdays"}
ANSWERS_V2 = {"what is the refund window for damaged items": "30 days for damaged items",
              "how do I reset my account password": "Use the reset link on the sign-in page"}


def baseline(q):
    return ANSWERS_V1.get(q, "I am not sure.")


def candidate_good(q):
    return {**ANSWERS_V1, **ANSWERS_V2}.get(q, "I am not sure.")


def candidate_bad(q):  # fixes the mined cases but breaks opening hours
    return {**ANSWERS_V2, "what are your opening hours": "Open 24/7"}.get(q, "I am not sure.")


gate = RegressionGate()
for name, cand in (("candidate A", candidate_good), ("candidate B", candidate_bad)):
    print(f"\n{name}:\n{gate.evaluate(baseline, cand, golden).summary()}")
