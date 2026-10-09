"""Risk — findings, severity taxonomy, risk scoring, recommended actions.

Phase 9 formalizes the risk/finding analysis. Provides:
- ``Finding``: typed finding with severity, confidence, evidence, actions.
- ``Severity``: 5-level taxonomy (CRITICAL/HIGH/MEDIUM/LOW/INFO).
- ``RiskScorer``: computes overall risk score from findings.
- ``RiskAssessor``: extracts findings from RAG responses + evidence.
- ``RiskReport``: complete risk assessment output.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from sovereign.core.logging import get_logger
from sovereign.rag.model import Claim, EvidenceRef

log = get_logger(__name__)

Severity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

SEVERITY_SCORES: dict[Severity, int] = {
    "CRITICAL": 100,
    "HIGH": 75,
    "MEDIUM": 50,
    "LOW": 25,
    "INFO": 10,
}

_RISK_KEYWORDS: dict[str, list[str]] = {
    "CRITICAL": [
        "critical", "catastrophic", "explosion", "fire", "collapse",
        "failure", "rupture", "fatal", "imminent", "emergency",
    ],
    "HIGH": [
        "hazard", "danger", "unsafe", "leak", "corrosion", "severe",
        "urgent", "immediate", "broken", "damaged", "defective",
    ],
    "MEDIUM": [
        "risk", "warning", "caution", "wear", "deterioration",
        "aging", "degradation", "below standard", "non-compliant",
    ],
    "LOW": [
        "minor", "cosmetic", "surface", "slight", "observe",
        "monitor", "recommend", "consider",
    ],
    "INFO": [
        "note", "information", "reference", "general", "background",
        "context", "summary",
    ],
}


class Finding(BaseModel):
    """A single finding from a risk assessment."""

    finding_id: str = ""
    description: str
    severity: Severity = "MEDIUM"
    confidence: float = 0.5
    category: str = "general"
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    source: str = "analysis"

    @property
    def severity_score(self) -> int:
        return SEVERITY_SCORES.get(self.severity, 25)


class RiskReport(BaseModel):
    """Complete output of a risk assessment."""

    query: str = ""
    findings: list[Finding] = Field(default_factory=list)
    overall_risk_score: int = 0
    risk_level: Severity = "INFO"
    summary: str = ""
    recommendations: list[str] = Field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "CRITICAL")

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "HIGH")

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    def findings_by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]


class RiskScorer:
    """Computes an overall risk score from findings."""

    @staticmethod
    def score(findings: list[Finding]) -> tuple[int, Severity]:
        """Compute (score, level) from findings."""
        if not findings:
            return (0, "INFO")

        max_score = max(f.severity_score for f in findings)

        severity_counts: dict[Severity, int] = {}
        for f in findings:
            severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

        bonus = 0.0
        for sev, count in severity_counts.items():
            if count > 1:
                bonus += (count - 1) * (SEVERITY_SCORES[sev] * 0.05)

        total = min(100, int(max_score + bonus))

        if total >= 90:
            level: Severity = "CRITICAL"
        elif total >= 70:
            level = "HIGH"
        elif total >= 40:
            level = "MEDIUM"
        elif total >= 20:
            level = "LOW"
        else:
            level = "INFO"

        return (total, level)


class RiskAssessor:
    """Extracts findings from RAG responses and evidence."""

    def __init__(self) -> None:
        self._scorer = RiskScorer()

    def assess(
        self,
        query: str,
        answer: str,
        claims: list[Claim] | None = None,
        evidence: list[EvidenceRef] | None = None,
    ) -> RiskReport:
        """Run a risk assessment on a RAG response."""
        findings: list[Finding] = []
        claims = claims or []
        evidence = evidence or []

        # 1. Findings from the answer
        findings.extend(self._extract_from_text(answer, source="answer"))

        # 2. Findings from evidence
        for ev in evidence:
            findings.extend(self._extract_from_text(ev.text, source="evidence", evidence_ref=ev))

        # 3. Flag unsupported/conflicting claims
        for claim in claims:
            if claim.support_status == "UNSUPPORTED":
                findings.append(
                    Finding(
                        finding_id=f"finding_{len(findings)}",
                        description=f"Unsupported claim: {claim.text[:200]}",
                        severity="MEDIUM",
                        confidence=0.7,
                        category="data_quality",
                        recommended_actions=["Verify against additional evidence sources."],
                    )
                )
            elif claim.support_status == "CONFLICTING":
                findings.append(
                    Finding(
                        finding_id=f"finding_{len(findings)}",
                        description=f"Conflicting evidence for: {claim.text[:200]}",
                        severity="HIGH",
                        confidence=0.8,
                        category="data_quality",
                        recommended_actions=["Resolve contradiction before relying on this."],
                    )
                )

        score, level = self._scorer.score(findings)
        recommendations = self._generate_recommendations(findings)
        summary = self._build_summary(findings, score, level)

        return RiskReport(
            query=query,
            findings=findings,
            overall_risk_score=score,
            risk_level=level,
            summary=summary,
            recommendations=recommendations,
        )

    def _extract_from_text(
        self,
        text: str,
        source: str = "analysis",
        evidence_ref: EvidenceRef | None = None,
    ) -> list[Finding]:
        """Extract risk findings from text using keyword matching."""
        findings: list[Finding] = []
        text_lower = text.lower()
        evidence_list = [evidence_ref] if evidence_ref else []

        for severity, keywords in _RISK_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    idx = text_lower.index(keyword)
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(keyword) + 100)
                    context = text[start:end].strip()

                    findings.append(
                        Finding(
                            finding_id=f"finding_{len(findings)}",
                            description=f"[{severity}] '{keyword}' detected: ...{context}...",
                            severity=severity,
                            confidence=0.6,
                            category=self._classify_category(keyword),
                            evidence_refs=evidence_list,
                            source=source,
                            recommended_actions=self._recommend_for_severity(severity),
                        )
                    )

        return findings

    def _classify_category(self, keyword: str) -> str:
        mechanical = {"wear", "corrosion", "leak", "rupture", "damaged", "broken", "collapse"}
        electrical = {"fire", "short", "arc"}
        safety = {"hazard", "danger", "unsafe", "fatal", "emergency", "explosion"}
        operational = {"failure", "non-compliant", "below standard"}

        if keyword in mechanical:
            return "mechanical"
        if keyword in electrical:
            return "electrical"
        if keyword in safety:
            return "safety"
        if keyword in operational:
            return "operational"
        return "general"

    def _recommend_for_severity(self, severity: str) -> list[str]:
        recs: dict[str, list[str]] = {
            "CRITICAL": [
                "Immediate action required — halt operation if safety is at risk.",
                "Notify safety officer and management immediately.",
                "Implement temporary mitigation measures.",
                "Schedule emergency repair/replacement.",
            ],
            "HIGH": [
                "Schedule corrective action within 7 days.",
                "Increase monitoring frequency.",
                "Notify relevant stakeholders.",
                "Prepare contingency plan.",
            ],
            "MEDIUM": [
                "Schedule corrective action within 30 days.",
                "Monitor condition for changes.",
                "Document in maintenance log.",
            ],
            "LOW": [
                "Include in next scheduled maintenance cycle.",
                "Monitor during routine inspections.",
            ],
            "INFO": [
                "No action required — informational only.",
            ],
        }
        return recs.get(severity, ["Review and assess."])

    def _generate_recommendations(self, findings: list[Finding]) -> list[str]:
        if not findings:
            return ["No risks identified. Continue routine monitoring."]

        recs: list[str] = []
        critical = [f for f in findings if f.severity == "CRITICAL"]
        high = [f for f in findings if f.severity == "HIGH"]

        if critical:
            recs.append(f"URGENT: {len(critical)} critical finding(s) require immediate attention.")
        if high:
            recs.append(f"{len(high)} high-severity finding(s) need action within 7 days.")

        all_actions: set[str] = set()
        for f in findings:
            for action in f.recommended_actions:
                all_actions.add(action)
        recs.extend(sorted(all_actions)[:5])

        return recs

    def _build_summary(self, findings: list[Finding], score: int, level: Severity) -> str:
        if not findings:
            return "No risk findings identified. Overall risk is LOW."

        parts = [
            f"Risk Assessment: {level} (score: {score}/100)",
            f"Total findings: {len(findings)}",
        ]
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            count = sum(1 for f in findings if f.severity == sev)
            if count > 0:
                parts.append(f"  {sev}: {count}")

        return ". ".join(parts)
