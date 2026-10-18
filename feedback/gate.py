"""Regression gate: block config/model changes that regress golden cases.

A change REGRESSES when a golden case that passed under the baseline fails
under the candidate. Cases failing under both are pre-existing failures, not
regressions; cases the candidate fixes are improvements. The gate fails only
on regressions, and the report shows per-case pass/fail with diffs.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable
from dataclasses import dataclass, field

from .miner import GoldenCase


def default_normalize(text: str) -> str:
    return " ".join(text.strip().split())


@dataclass
class CaseResult:
    case_id: str
    input: str
    expected: str
    baseline_output: str
    candidate_output: str
    baseline_passed: bool
    candidate_passed: bool

    @property
    def regressed(self) -> bool:
        return self.baseline_passed and not self.candidate_passed

    @property
    def fixed(self) -> bool:
        return not self.baseline_passed and self.candidate_passed

    def diff(self) -> str:
        return "\n".join(difflib.unified_diff(
            self.expected.splitlines(), self.candidate_output.splitlines(),
            fromfile="expected", tofile="candidate", lineterm=""))


@dataclass
class GateReport:
    results: list[CaseResult] = field(default_factory=list)

    @property
    def regressions(self) -> list[CaseResult]:
        return [r for r in self.results if r.regressed]

    @property
    def fixes(self) -> list[CaseResult]:
        return [r for r in self.results if r.fixed]

    @property
    def gate_passed(self) -> bool:
        return not self.regressions

    def summary(self) -> str:
        lines = [f"gate {'PASS' if self.gate_passed else 'FAIL'}: "
                 f"{len(self.results)} cases, "
                 f"{len(self.regressions)} regressions, "
                 f"{len(self.fixes)} fixes"]
        for r in self.results:
            status = ("REGRESSED" if r.regressed else
                      "FIXED" if r.fixed else
                      "pass" if r.candidate_passed else "fail")
            lines.append(f"  [{status}] {r.case_id}")
            if r.regressed or not r.candidate_passed:
                d = r.diff()
                if d:
                    lines.append("    " + d.replace("\n", "\n    "))
        return "\n".join(lines)


class RegressionGate:
    """Evaluate a candidate config against golden cases with a baseline.

    Both baseline and candidate are callables: input str -> output str.
    """

    def __init__(self, normalize: Callable[[str], str] = default_normalize):
        self.normalize = normalize

    def _matches(self, output: str, expected: str) -> bool:
        return self.normalize(output) == self.normalize(expected)

    def evaluate(self, baseline: Callable[[str], str],
                 candidate: Callable[[str], str],
                 golden_cases: list[GoldenCase]) -> GateReport:
        report = GateReport()
        for case in golden_cases:
            b_out = baseline(case.input)
            c_out = candidate(case.input)
            report.results.append(CaseResult(
                case_id=case.case_id,
                input=case.input,
                expected=case.expected,
                baseline_output=b_out,
                candidate_output=c_out,
                baseline_passed=self._matches(b_out, case.expected),
                candidate_passed=self._matches(c_out, case.expected),
            ))
        return report
