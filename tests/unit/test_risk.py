"""Tests for sovereign.risk — findings, scoring, risk assessor."""

from __future__ import annotations

from sovereign.rag.model import Claim, EvidenceRef
from sovereign.risk.model import (
    Finding,
    RiskAssessor,
    RiskScorer,
)


class TestFindingModel:
    def test_severity_score(self) -> None:
        f = Finding(description="test", severity="CRITICAL")
        assert f.severity_score == 100

    def test_severity_score_default(self) -> None:
        f = Finding(description="test", severity="MEDIUM")
        assert f.severity_score == 50


class TestRiskScorer:
    def test_empty_findings(self) -> None:
        score, level = RiskScorer.score([])
        assert score == 0
        assert level == "INFO"

    def test_single_critical(self) -> None:
        findings = [Finding(description="test", severity="CRITICAL")]
        score, level = RiskScorer.score(findings)
        assert score == 100
        assert level == "CRITICAL"

    def test_single_low(self) -> None:
        findings = [Finding(description="test", severity="LOW")]
        score, level = RiskScorer.score(findings)
        assert score == 25
        assert level == "LOW"

    def test_multiple_same_severity_bonus(self) -> None:
        """Multiple findings at the same severity should increase the score."""
        one = [Finding(description="t", severity="HIGH")]
        two = [
            Finding(description="t", severity="HIGH"),
            Finding(description="t2", severity="HIGH"),
        ]
        score1, _ = RiskScorer.score(one)
        score2, _ = RiskScorer.score(two)
        assert score2 > score1

    def test_level_thresholds(self) -> None:
        assert RiskScorer.score([Finding(description="t", severity="CRITICAL")])[1] == "CRITICAL"
        assert RiskScorer.score([Finding(description="t", severity="HIGH")])[1] == "HIGH"
        assert RiskScorer.score([Finding(description="t", severity="MEDIUM")])[1] == "MEDIUM"
        assert RiskScorer.score([Finding(description="t", severity="LOW")])[1] == "LOW"
        assert RiskScorer.score([Finding(description="t", severity="INFO")])[1] == "INFO"


class TestRiskAssessor:
    def test_assess_no_risks(self) -> None:
        """No risk keywords → no findings."""
        assessor = RiskAssessor()
        report = assessor.assess("query", "The pump is operating normally within parameters.")
        assert report.total_findings == 0
        assert report.overall_risk_score == 0
        assert report.risk_level == "INFO"

    def test_assess_finds_critical_keywords(self) -> None:
        """Critical keywords should produce CRITICAL findings."""
        assessor = RiskAssessor()
        report = assessor.assess("query", "There is a critical failure in the system.")
        assert report.total_findings > 0
        assert report.critical_count > 0
        assert report.overall_risk_score >= 90

    def test_assess_finds_high_keywords(self) -> None:
        """High-severity keywords should produce HIGH findings."""
        assessor = RiskAssessor()
        report = assessor.assess("query", "A hazard was identified with dangerous corrosion.")
        assert report.total_findings > 0
        assert report.high_count > 0

    def test_assess_with_evidence(self) -> None:
        """Evidence text should also be scanned for risks."""
        assessor = RiskAssessor()
        evidence = [EvidenceRef(document_id="d1", text="Bearing wear detected on pump P-101.")]
        report = assessor.assess("query", "All normal.", evidence=evidence)
        assert report.total_findings > 0
        # Wear is a MEDIUM keyword
        assert any(f.severity == "MEDIUM" for f in report.findings)

    def test_assess_unsupported_claims(self) -> None:
        """Unsupported claims should become MEDIUM findings."""
        assessor = RiskAssessor()
        claims = [Claim(text="test claim", support_status="UNSUPPORTED")]
        report = assessor.assess("query", "safe answer", claims=claims)
        assert any(f.category == "data_quality" for f in report.findings)

    def test_assess_conflicting_claims(self) -> None:
        """Conflicting claims should become HIGH findings."""
        assessor = RiskAssessor()
        claims = [Claim(text="test claim", support_status="CONFLICTING")]
        report = assessor.assess("query", "safe answer", claims=claims)
        conflicting = [f for f in report.findings if "Conflicting" in f.description]
        assert len(conflicting) > 0
        assert conflicting[0].severity == "HIGH"

    def test_assess_generates_recommendations(self) -> None:
        """Recommendations should be generated for findings."""
        assessor = RiskAssessor()
        report = assessor.assess("query", "Critical failure detected.")
        assert len(report.recommendations) > 0

    def test_assess_summary_contains_score(self) -> None:
        """Summary should include the risk score."""
        assessor = RiskAssessor()
        report = assessor.assess("query", "Critical failure.")
        assert str(report.overall_risk_score) in report.summary

    def test_findings_by_severity(self) -> None:
        """findings_by_severity should filter correctly."""
        assessor = RiskAssessor()
        report = assessor.assess("query", "Critical failure and hazard detected.")
        critical = report.findings_by_severity("CRITICAL")
        assert all(f.severity == "CRITICAL" for f in critical)

    def test_finding_has_recommended_actions(self) -> None:
        """Each finding should have recommended actions."""
        assessor = RiskAssessor()
        report = assessor.assess("query", "Critical failure detected.")
        for f in report.findings:
            assert len(f.recommended_actions) > 0

    def test_finding_category_classification(self) -> None:
        """Findings should be classified into categories."""
        assessor = RiskAssessor()
        report = assessor.assess("query", "Corrosion detected on the pipe.")
        categories = {f.category for f in report.findings}
        assert "mechanical" in categories

    def test_empty_answer(self) -> None:
        """Empty answer should produce no findings."""
        assessor = RiskAssessor()
        report = assessor.assess("query", "")
        assert report.total_findings == 0
