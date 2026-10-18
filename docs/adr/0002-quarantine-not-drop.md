# ADR 0002: Orphan events are quarantined to disk, not dropped

Status: accepted (2026-10-18)

## Context
Feedback can arrive before the session it belongs to is registered, for
example with a late session sync or a different ingestion path. Dropping it
loses signal. Keeping it only in memory loses it on restart, which is what
the first version did.

## Decision
Events for unknown sessions go to a `.quarantine` JSONL file next to the
store. `adopt(event_id, session_id)` moves an event into the main store once
the session is known.

## Consequences
- No feedback is lost to ordering problems or restarts.
- Quarantine can grow without bound, so production needs a retention rule and
  an alert on its size.
