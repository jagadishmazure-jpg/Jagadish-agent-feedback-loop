# Implementation guide: from offline build to Azure

> Status: **planned**. Nothing here has been deployed. The offline build in this
> repository is what exists today; this guide is how it would be taken to a
> real Azure environment.

## Azure service mapping

| Offline component | Azure service (planned) | Notes |
|---|---|---|
| Capture | Feedback widget in the app plus events from the agent runtime to Event Hubs | Keep session and turn ids |
| Store | Fabric lakehouse or Azure Data Explorer table with the same append/query contract | Retention per event type |
| Mining | Scheduled job with embedding clustering (Azure OpenAI embeddings) | Review queue before cases are used |
| Gate | GitHub Actions check on every prompt, config or model change | Required check on pull requests |

## Steps

1. Emit the six event types from the product UI and the agent runtime with the same ids.
2. Land them in an append-only table; keep the quarantine and adopt flow for late session data.
3. Swap TF-IDF for embeddings and add a review queue for flagged and new cases.
4. Replace exact match with a reference-guided judge that has passed bias probes.
5. Make the gate a required CI check with a minimum case count.

## Guardrails to keep when going live

- Events are validated on construction; an empty correction or an out-of-range rating cannot be stored.
- Orphan events are quarantined to disk, never silently dropped.
- Mined cases cite the events they came from, so any case can be traced back to real feedback.
- Clusters with disagreeing corrections are flagged for review instead of picking an answer silently.
- The gate fails on any regression of a previously passing case, with a diff.

## What to measure before calling it production-ready

- Share of corrections that become reviewed golden cases within a week.
- Regressions caught by the gate versus regressions reported by users.
- Repeat-correction rate for the same query cluster after a fix ships.
