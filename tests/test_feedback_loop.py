import json

import pytest

from feedback.capture import (
    ALL_TYPES,
    FeedbackEvent,
    capture_abandonment,
    capture_correction,
    capture_rating,
    capture_rephrase,
    capture_thumbs,
    capture_tool_override,
)
from feedback.gate import GateReport, RegressionGate
from feedback.miner import CorrectionMiner, GoldenCase
from feedback.store import FeedbackStore
from feedback.taxonomy import (
    EVENT_TYPES,
    describe,
    kind_of,
    more_severe,
    retention_days,
    severity_of,
)

# ---------- helpers ----------

def _correction(eid, query, correction, session="s1"):
    e = capture_correction(session, f"t-{eid}", "v1", query, "wrong answer",
                           correction)
    e.event_id = eid  # deterministic ids for assertions
    return e


class FakeModel:
    """Test double for a model/config: maps inputs to canned outputs."""

    def __init__(self, mapping, default="???"):
        self.mapping = dict(mapping)
        self.default = default

    def __call__(self, prompt: str) -> str:
        return self.mapping.get(prompt, self.default)


def _golden():
    return [
        GoldenCase("capital of France", "Paris", ["e1"], "g1"),
        GoldenCase("2+2", "4", ["e2"], "g2"),
        GoldenCase("sky color", "blue", ["e3"], "g3"),
    ]


# ---------- capture ----------

def test_rating_event_valid():
    e = capture_rating("s1", "t1", "v3", 4, "q", "a")
    assert e.rating == 4 and e.event_type == "rating"
    assert e.agent_version == "v3" and e.turn_id == "t1"


def test_rating_out_of_range_rejected():
    with pytest.raises(ValueError):
        capture_rating("s1", "t1", "v1", 0)
    with pytest.raises(ValueError):
        capture_rating("s1", "t1", "v1", 6)


def test_correction_requires_text():
    with pytest.raises(ValueError):
        capture_correction("s1", "t1", "v1", "q", "a", "   ")


def test_correction_carries_context():
    e = capture_correction("s1", "t1", "v1", "my query", "bad answer",
                           "good answer")
    assert e.user_query == "my query"
    assert e.agent_answer == "bad answer"
    assert e.correction == "good answer"


def test_thumbs_requires_bool():
    e = capture_thumbs("s1", "t1", "v1", True)
    assert e.up is True
    with pytest.raises(ValueError):
        FeedbackEvent("thumbs", "s1", "t1", "v1")


def test_unknown_event_type_rejected():
    with pytest.raises(ValueError):
        FeedbackEvent("nope", "s1", "t1", "v1")


def test_session_id_required():
    with pytest.raises(ValueError):
        FeedbackEvent("rating", "", "t1", "v1", rating=3)


def test_implicit_events_carry_detail():
    e1 = capture_rephrase("s1", "t1", "v1", "q", detail="user reworded twice")
    e2 = capture_tool_override("s1", "t2", "v1", detail="undid refund call")
    e3 = capture_abandonment("s1", "t3", "v1")
    assert e1.event_type == "rephrase_detected" and e1.detail
    assert e2.event_type == "tool_override" and e2.detail
    assert e3.event_type == "session_abandoned"


def test_event_serialization_roundtrip():
    e = capture_correction("s1", "t9", "v2", "q", "bad", "good")
    d = e.to_dict()
    assert json.loads(json.dumps(d))["correction"] == "good"
    e2 = FeedbackEvent.from_dict(d)
    assert e2.event_id == e.event_id and e2.correction == "good"


def test_event_ids_unique():
    ids = {capture_rating("s1", "t1", "v1", 5).event_id for _ in range(50)}
    assert len(ids) == 50


# ---------- store ----------

def test_store_append_and_count(tmp_path):
    st = FeedbackStore(tmp_path / "f.jsonl")
    st.register_session("s1", "u1")
    assert st.append(capture_rating("s1", "t1", "v1", 5)) == "stored"
    assert st.count() == 1


def test_orphan_events_quarantined_not_dropped(tmp_path):
    st = FeedbackStore(tmp_path / "f.jsonl")
    e = capture_rating("ghost", "t1", "v1", 2)
    assert st.append(e) == "quarantined"
    assert st.count() == 0  # not in the store
    q = st.quarantined()
    assert len(q) == 1 and q[0].event_id == e.event_id  # but not lost


def test_adopt_links_quarantined_event(tmp_path):
    st = FeedbackStore(tmp_path / "f.jsonl")
    e = capture_rating("s9", "t1", "v1", 2)
    st.append(e)
    st.register_session("s9", "u9")
    adopted = st.adopt(e.event_id, "s9")
    assert adopted.session_id == "s9"
    assert st.count() == 1 and st.quarantined() == []


def test_adopt_unknown_event_raises(tmp_path):
    st = FeedbackStore(tmp_path / "f.jsonl")
    with pytest.raises(KeyError):
        st.adopt("nope", "s1")


def test_adopt_unregistered_session_raises(tmp_path):
    st = FeedbackStore(tmp_path / "f.jsonl")
    e = capture_rating("s9", "t1", "v1", 2)
    st.append(e)
    with pytest.raises(ValueError):
        st.adopt(e.event_id, "s9")


def test_query_by_session(tmp_path):
    st = FeedbackStore(tmp_path / "f.jsonl")
    st.register_session("s1", "u1")
    st.register_session("s2", "u2")
    st.append(capture_rating("s1", "t1", "v1", 5))
    st.append(capture_rating("s2", "t1", "v1", 1))
    got = st.query(session_id="s1")
    assert len(got) == 1 and got[0].rating == 5


def test_query_by_user(tmp_path):
    st = FeedbackStore(tmp_path / "f.jsonl")
    st.register_session("s1", "u1")
    st.register_session("s2", "u1")
    st.append(capture_rating("s1", "t1", "v1", 5))
    st.append(capture_rating("s2", "t1", "v1", 4))
    assert len(st.query(user_id="u1")) == 2


def test_query_time_window_and_type(tmp_path):
    st = FeedbackStore(tmp_path / "f.jsonl")
    st.register_session("s1", "u1")
    e1 = capture_rating("s1", "t1", "v1", 5)
    e1.timestamp = 1000.0
    e2 = capture_thumbs("s1", "t2", "v1", True)
    e2.timestamp = 2000.0
    st.append(e1)
    st.append(e2)
    assert len(st.query(since=1500.0)) == 1
    assert len(st.query(until=1500.0)) == 1
    assert len(st.query(event_type="thumbs")) == 1


def test_store_persists_across_reload(tmp_path):
    p = tmp_path / "f.jsonl"
    st = FeedbackStore(p)
    st.register_session("s1", "u1")
    st.append(capture_rating("s1", "t1", "v1", 5))
    st2 = FeedbackStore(p)  # reload: sessions + events survive
    assert st2.known_session("s1")
    assert st2.count() == 1
    assert st2.query(user_id="u1")[0].rating == 5


# ---------- miner ----------

REFUND_QS = [
    "what is the refund policy for damaged items",
    "what is your refund policy for damaged goods",
    "tell me the refund policy for broken items",
]
REFUND_A = "Full refund within 30 days of delivery"


def _refund_events():
    return [_correction(f"r{i}", q, REFUND_A) for i, q in enumerate(REFUND_QS)]


def test_similar_corrections_cluster_into_one_case():
    miner = CorrectionMiner()
    cases = miner.mine(_refund_events())
    assert len(cases) == 1
    assert cases[0].expected == REFUND_A


def test_dissimilar_corrections_stay_separate():
    miner = CorrectionMiner()
    events = _refund_events() + [
        _correction("p1", "how do I reset my password",
                    "Use the forgot-password link on the login page"),
        _correction("w1", "what are your warehouse hours on Sunday",
                    "Warehouses are closed on Sundays"),
    ]
    cases = miner.mine(events)
    assert len(cases) == 3


def test_mined_case_cites_source_events():
    miner = CorrectionMiner()
    cases = miner.mine(_refund_events())
    assert sorted(cases[0].source_event_ids) == ["r0", "r1", "r2"]


def test_dedup_drops_duplicate_of_existing():
    miner = CorrectionMiner()
    existing = [GoldenCase(REFUND_QS[0], REFUND_A, ["old"], "g-old")]
    cases = miner.mine(_refund_events(), existing=existing)
    assert cases == []


def test_dedup_keeps_novel_cases():
    miner = CorrectionMiner()
    existing = [GoldenCase("something entirely different", "x", ["old"], "g")]
    cases = miner.mine(_refund_events(), existing=existing)
    assert len(cases) == 1


def test_mine_empty_returns_empty():
    assert CorrectionMiner().mine([]) == []


def test_mine_ignores_non_correction_events():
    miner = CorrectionMiner()
    events = [capture_rating("s1", "t1", "v1", 5),
              capture_thumbs("s1", "t2", "v1", False)]
    assert miner.mine(events) == []


def test_identical_texts_always_cluster():
    miner = CorrectionMiner()
    events = [_correction(f"e{i}", "same question here", f"answer {i}")
              for i in range(4)]
    assert len(miner.mine(events)) == 1


def test_mined_case_ids_deterministic():
    miner = CorrectionMiner()
    a = miner.mine(_refund_events())[0].case_id
    b = miner.mine(_refund_events())[0].case_id
    assert a == b and a.startswith("mined-")


# ---------- gate ----------

def test_clean_config_passes_gate():
    gate = RegressionGate()
    golden = _golden()
    base = FakeModel({c.input: c.expected for c in golden})
    cand = FakeModel({c.input: c.expected for c in golden})
    report = gate.evaluate(base, cand, golden)
    assert report.gate_passed
    assert report.regressions == []


def test_regressed_config_fails_gate():
    gate = RegressionGate()
    golden = _golden()
    base = FakeModel({c.input: c.expected for c in golden})
    broken = dict(base.mapping)
    broken["2+2"] = "5"  # candidate regresses one case
    cand = FakeModel(broken)
    report = gate.evaluate(base, cand, golden)
    assert not report.gate_passed
    assert [r.case_id for r in report.regressions] == ["g2"]


def test_report_shows_diff_for_regression():
    gate = RegressionGate()
    golden = _golden()
    base = FakeModel({c.input: c.expected for c in golden})
    cand = FakeModel({**base.mapping, "2+2": "5"})
    report = gate.evaluate(base, cand, golden)
    text = report.summary()
    assert "FAIL" in text and "g2" in text
    assert "-4" in text and "+5" in text  # unified diff of expected vs actual


def test_preexisting_failure_is_not_regression():
    gate = RegressionGate()
    golden = _golden()
    base = FakeModel({"capital of France": "Paris"})  # fails g2, g3 already
    cand = FakeModel({"capital of France": "Paris"})
    report = gate.evaluate(base, cand, golden)
    assert report.gate_passed  # no NEW failures
    assert len([r for r in report.results if not r.candidate_passed]) == 2


def test_candidate_fix_is_not_regression():
    gate = RegressionGate()
    golden = _golden()
    base = FakeModel({})  # baseline fails everything
    cand = FakeModel({c.input: c.expected for c in golden})
    report = gate.evaluate(base, cand, golden)
    assert report.gate_passed
    assert len(report.fixes) == 3


def test_empty_golden_set_passes():
    gate = RegressionGate()
    m = FakeModel({})
    assert gate.evaluate(m, m, []).gate_passed


def test_custom_normalize():
    gate = RegressionGate(normalize=str.lower)
    golden = [GoldenCase("q", "Paris", ["e"], "g")]
    base = FakeModel({"q": "paris"})
    report = gate.evaluate(base, base, golden)
    assert report.gate_passed


def test_gate_works_with_any_callable():
    gate = RegressionGate()
    golden = [GoldenCase("q", "yes", ["e"], "g")]
    report = gate.evaluate(lambda p: "yes", lambda p: "yes", golden)
    assert isinstance(report, GateReport) and report.gate_passed


# ---------- taxonomy ----------

def test_taxonomy_covers_all_event_types():
    assert set(EVENT_TYPES) == set(ALL_TYPES)


def test_severity_mapping():
    assert severity_of("correction") == "high"
    assert severity_of("tool_override") == "high"
    assert severity_of("rating") == "low"
    assert more_severe("rating", "correction") == "correction"


def test_taxonomy_rejects_unknown():
    with pytest.raises(ValueError):
        severity_of("nope")
    with pytest.raises(ValueError):
        describe("nope")


def test_retention_hooks_and_overrides():
    assert retention_days("correction") == 730
    assert retention_days("session_abandoned") == 180
    assert retention_days("rating", {"rating": 30}) == 30
    assert kind_of("rephrase_detected") == "implicit"
    assert kind_of("thumbs") == "explicit"


def test_quarantine_survives_a_restart(tmp_path):
    from feedback.capture import capture_thumbs
    from feedback.store import FeedbackStore

    path = tmp_path / "fb.jsonl"
    st = FeedbackStore(path)
    e = capture_thumbs("unknown-sess", "t1", "agent-v1", up=False)
    assert st.append(e) == "quarantined"

    reopened = FeedbackStore(path)  # new process, same files
    assert [q.event_id for q in reopened.quarantined()] == [e.event_id]
    reopened.register_session("sess-9", "user-9")
    reopened.adopt(e.event_id, "sess-9")
    assert FeedbackStore(path).quarantined() == []
    assert FeedbackStore(path).count() == 1


def test_conflicting_corrections_flagged_for_review():
    from feedback.capture import capture_correction
    from feedback.miner import CorrectionMiner

    agree = [capture_correction("s", f"t{i}", "v1", user_query="refund window for damaged items",
                                agent_answer="x", correction="30 days") for i in range(2)]
    clash = agree + [capture_correction("s", "t9", "v1", user_query="refund window for damaged items?",
                                        agent_answer="x", correction="14 days")]
    assert CorrectionMiner().mine(agree)[0].needs_review is False
    (case,) = CorrectionMiner().mine(clash)
    assert case.needs_review is True and len(case.source_event_ids) == 3
