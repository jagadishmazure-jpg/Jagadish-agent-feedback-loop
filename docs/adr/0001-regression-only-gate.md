# ADR 0001: The gate fails on regressions, not on an aggregate score

Status: accepted (2026-10-18)

## Context
A change can raise the average score and still break cases that users have
already corrected. Each of those breaks is a mistake the user sees again.

## Decision
`RegressionGate` compares the baseline and the candidate per case. It fails if
any case that passed on the baseline fails on the candidate. Fixes are
reported, but they never offset a regression.

## Consequences
- Changes that trade one known case for another are blocked until someone
  decides explicitly, for example by updating the golden case.
- Exact matching makes the gate strict. A paraphrased correct answer counts as
  a regression until a reference-guided judge replaces exact match.
- An empty golden set passes, so production use needs a minimum case count.
