# Interview points

Short, honest talking points for Jagadish-agent-feedback-loop. Every number quoted is from the
real run shown in the README.

- Implicit signals matter as much as explicit ones; most users rephrase or leave rather than rate.
- The gate fails on regressions, not on overall score, so a change that fixes ten things and breaks one still stops.
- Orphan events are quarantined to disk; in my first version they lived in memory and a restart lost them.
- When corrections disagree I flag the case instead of letting the miner pick a winner.

## Likely follow-up questions

- Why exact match? (Deterministic and offline; the plan is a judge that has passed bias probes.)
- How do you stop bad corrections becoming tests? (Review flag, source citations, and a human queue.)
- What about PII in corrections? (Redact before storage; the bank and retail repos show how.)
