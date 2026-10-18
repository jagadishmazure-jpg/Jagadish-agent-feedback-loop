# Architecture

## The loop

```mermaid
flowchart LR
    P[Product / agent runtime] -->|turns| C[capture.py]
    C -->|FeedbackEvent| S[store.py\nappend-only JSONL]
    S -->|corrections| M[miner.py\nTF-IDF clustering]
    M -->|GoldenCase +\nsource citations| G[golden set]
    G --> RG[gate.py\nRegressionGate]
    BASE[baseline config] --> RG
    CAND[candidate config] --> RG
    RG -->|gate_passed?| CI[CI / deploy decision]
    CI -->|ship| P
```

## Session linkage and quarantine

```mermaid
flowchart TD
    E[FeedbackEvent] --> K{session known?}
    K -->|yes| S[stored in JSONL]
    K -->|no| Q[quarantined\nnever dropped]
    Q -->|session registered| A[adopt → stored]
```

Orphan events are quarantined, not dropped: a missing session id is a
pipeline bug worth noticing, not data worth losing.

## What counts as a regression

```mermaid
flowchart TD
    B[baseline output] --> CMP{compare}
    C[candidate output] --> CMP
    CMP -->|both pass| OK[no change]
    CMP -->|both fail| PRE[pre-existing failure\nnot a regression]
    CMP -->|baseline pass\ncandidate fail| REG[REGRESSION\ngate fails]
    CMP -->|baseline fail\ncandidate pass| FIX[improvement\ngate passes]
```

Only true regressions fail the gate: the change made something worse
than it was. Pre-existing failures and fixes are reported, not blocking.
