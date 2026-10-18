"""Mine correction events into golden eval cases.

Hand-rolled TF-IDF + threshold single-linkage clustering over the correction
queries: corrections about the same question become ONE golden case instead
of N duplicates. Every mined case cites its source event IDs, and cases that
duplicate the existing golden set are dropped.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field

from .capture import FeedbackEvent

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class GoldenCase:
    input: str
    expected: str
    source_event_ids: list[str] = field(default_factory=list)
    case_id: str = ""

    def __post_init__(self) -> None:
        if not self.case_id:
            digest = hashlib.md5(f"{self.input}\x00{self.expected}".encode()).hexdigest()
            self.case_id = f"mined-{digest[:8]}"


class CorrectionMiner:
    def __init__(self, similarity_threshold: float = 0.35,
                 dedup_threshold: float = 0.8):
        self.threshold = similarity_threshold
        self.dedup_threshold = dedup_threshold

    # ---- TF-IDF machinery ----
    def _tfidf(self, docs: list[str]) -> list[dict[str, float]]:
        tokenized = [_tokens(d) for d in docs]
        n = len(docs)
        df: dict[str, int] = {}
        for toks in tokenized:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        vectors = []
        for toks in tokenized:
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            vec = {}
            for t, c in tf.items():
                idf = math.log((1 + n) / (1 + df[t])) + 1.0
                vec[t] = (c / len(toks)) * idf if toks else 0.0
            vectors.append(vec)
        return vectors

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(a[t] * b[t] for t in a if t in b)
        na = math.sqrt(sum(v * v for v in a.values()))
        nb = math.sqrt(sum(v * v for v in b.values()))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)

    def similarity(self, a: str, b: str) -> float:
        vecs = self._tfidf([a, b])
        return self._cosine(vecs[0], vecs[1])

    # ---- clustering ----
    def _cluster(self, events: list[FeedbackEvent]) -> list[list[FeedbackEvent]]:
        """Single-linkage clustering on query similarity."""
        if not events:
            return []
        queries = [e.user_query for e in events]
        vecs = self._tfidf(queries)
        parent = list(range(len(events)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[rj] = ri

        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                if self._cosine(vecs[i], vecs[j]) >= self.threshold:
                    union(i, j)
        groups: dict[int, list[FeedbackEvent]] = {}
        for i, e in enumerate(events):
            groups.setdefault(find(i), []).append(e)
        return list(groups.values())

    # ---- mining ----
    def mine(self, events: list[FeedbackEvent],
             existing: list[GoldenCase] | None = None) -> list[GoldenCase]:
        corrections = [e for e in events if e.event_type == "correction"]
        cases: list[GoldenCase] = []
        for group in self._cluster(corrections):
            # representative: the event whose query is most similar to the rest
            rep = max(group, key=lambda e: sum(
                self.similarity(e.user_query, o.user_query)
                for o in group if o is not e) if len(group) > 1 else 1.0)
            cases.append(GoldenCase(
                input=rep.user_query,
                expected=rep.correction or "",
                source_event_ids=[e.event_id for e in group],
            ))
        return self.deduplicate(cases, existing or [])

    def deduplicate(self, cases: list[GoldenCase],
                    existing: list[GoldenCase]) -> list[GoldenCase]:
        """Drop mined cases that duplicate the existing golden set."""
        kept = []
        for c in cases:
            dup = any(self.similarity(c.input, e.input) >= self.dedup_threshold
                      for e in existing)
            if not dup:
                kept.append(c)
        return kept
