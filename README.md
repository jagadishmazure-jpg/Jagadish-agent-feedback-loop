# Agent Feedback Loop — the Product→Data→Model flywheel, executable

Every enterprise agent deployment decays without a feedback loop: user
corrections evaporate, the same mistakes repeat, and regressions ship
silently because nothing turns production experience into eval cases.
This repo makes the loop executable in four stages:

**Problem.** Production agents are evaluated once (before launch) and never
again. Users correct bad answers, rephrase failed questions, and override
bad tool calls — and all of that signal is thrown away.

**Approach.** Capture every signal (explicit ratings/corrections *and*
implicit rephrases/overrides/abandonments) into a session-linked store,
cluster corrections into golden eval cases with a miner, and run every
config or model change through a regression gate that fails the change if
any previously-passing case regresses.

**Outcome.** Corrections become evals automatically; regressions are caught
in CI instead of by customers. The flywheel turns: product usage → data
(feedback) → model/config improvements → product.

> Synthetic data only. Independent project, not affiliated with or endorsed
> by any vendor or employer.

## Modules

| Module | Responsibility |
|---|---|
| `feedback/capture.py` | `FeedbackEvent` + helpers: explicit (rating 1–5, correction, thumbs) and implicit (rephrase, tool override, abandonment) signals, each with session_id, turn_id, agent_version |
| `feedback/store.py` | Append-only JSONL store; query by session/user/time/type; orphan events quarantined (never silently dropped), adoptable later |
| `feedback/miner.py` | Hand-rolled TF-IDF + threshold clustering turns correction events into `GoldenCase`s with source-event citations; dedups against the existing golden set |
| `feedback/gate.py` | `RegressionGate`: runs baseline vs candidate over golden cases; fails only on true regressions; per-case report with diffs |
| `feedback/taxonomy.py` | Taxonomy as code: event types, severity mapping, retention-policy hooks |

## Quickstart

```python
from feedback.capture import capture_correction
from feedback.store import FeedbackStore
from feedback.miner import CorrectionMiner
from feedback.gate import RegressionGate

store = FeedbackStore("feedback.jsonl")
store.register_session("sess-1", "user-7")
store.append(capture_correction("sess-1", "turn-3", "agent-v2",
                                user_query="refund policy for damaged items?",
                                agent_answer="No refunds, sorry.",
                                correction="Full refund within 30 days."))

miner = CorrectionMiner()
golden = miner.mine(store.query(event_type="correction"))

gate = RegressionGate()
report = gate.evaluate(old_config, new_config, golden)
print(report.summary())   # FAIL lists regressions with diffs
assert report.gate_passed  # wire this into CI
```

Run the tests:

```bash
python -m pytest tests/ -q
```

## Production path

| Demo (this repo) | Production |
|---|---|
| In-code `capture_*` helpers | Feedback widgets in the product UI, instrumentation in the agent runtime |
| JSONL file store | Warehouse-backed store (e.g. Delta/BigQuery) with the same append/query contract |
| TF-IDF clustering | Embedding-based clustering at scale; human review queue for mined cases |
| `RegressionGate` in tests | Gate as a CI check on every prompt/config/model change |
| Fixed retention table | `taxonomy.retention_days` overrides wired to company data-retention policy |

## Knowledge

- [knowledge/flywheel.md](knowledge/flywheel.md) — the Product→Data→Model loop, why deployments decay, explicit vs implicit signals
- [knowledge/architecture.md](knowledge/architecture.md) — architecture diagrams (Mermaid)
