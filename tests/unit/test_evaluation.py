"""Tests for sovereign.evaluation — retrieval, faithfulness, injection."""

from __future__ import annotations

from sovereign.evaluation import (
    EvalReport,
    EvalResult,
    InjectionTestSuite,
    RAGFaithfulnessEvaluator,
    RegressionCorpus,
    run_evaluation_suite,
)


class TestEvalReport:
    def test_add_passed(self) -> None:
        report = EvalReport()
        report.add(EvalResult(name="t1", passed=True, score=1.0))
        assert report.total == 1
        assert report.passed == 1
        assert report.failed == 0

    def test_add_failed(self) -> None:
        report = EvalReport()
        report.add(EvalResult(name="t1", passed=False, score=0.0))
        assert report.total == 1
        assert report.passed == 0
        assert report.failed == 1

    def test_pass_rate(self) -> None:
        report = EvalReport()
        report.add(EvalResult(name="t1", passed=True))
        report.add(EvalResult(name="t2", passed=False))
        assert report.pass_rate == 0.5

    def test_finalize(self) -> None:
        report = EvalReport()
        report.add(EvalResult(name="t1", passed=True))
        report.finalize()
        assert "1/1 passed" in report.summary


class TestInjectionTestSuite:
    def test_run_all(self) -> None:
        suite = InjectionTestSuite()
        report = suite.run_all()
        assert report.total > 0
        assert all(r.name.startswith("injection_") for r in report.results)

    def test_canary_detection(self) -> None:
        """Canary leakage should be detected (not safe)."""
        suite = InjectionTestSuite()
        report = suite.run_all()
        canary_test = next(r for r in report.results if "canary" in r.name)
        assert canary_test.passed  # passed = correctly identified as unsafe

    def test_normal_response_safe(self) -> None:
        """Normal response should be safe."""
        suite = InjectionTestSuite()
        report = suite.run_all()
        normal_test = next(r for r in report.results if "normal" in r.name)
        assert normal_test.passed

    def test_instruction_override_detected(self) -> None:
        """Instruction override should be detected."""
        suite = InjectionTestSuite()
        report = suite.run_all()
        override_test = next(r for r in report.results if "override" in r.name)
        assert override_test.passed


class TestRAGFaithfulness:
    def test_answered_with_evidence_passes(self) -> None:
        """Answered verdict with evidence should pass."""
        evaluator = RAGFaithfulnessEvaluator()
        result = evaluator.evaluate("query", {
            "verdict": {"kind": "answered"},
            "answer": "test answer",
            "evidence": [{"document_id": "d1", "text": "evidence"}],
            "claims": [{"text": "test", "support_status": "SUPPORTED"}],
        })
        assert result.passed

    def test_answered_without_evidence_fails(self) -> None:
        """Answered verdict without evidence should fail."""
        evaluator = RAGFaithfulnessEvaluator()
        result = evaluator.evaluate("query", {
            "verdict": {"kind": "answered"},
            "answer": "test answer",
            "evidence": [],
            "claims": [],
        })
        assert not result.passed

    def test_insufficient_evidence_passes(self) -> None:
        """Insufficient evidence verdict should pass."""
        evaluator = RAGFaithfulnessEvaluator()
        result = evaluator.evaluate("query", {
            "verdict": {"kind": "insufficient_evidence"},
            "answer": "",
            "evidence": [],
            "claims": [],
        })
        assert result.passed

    def test_all_unsupported_claims_fails(self) -> None:
        """All unsupported claims with answered verdict should fail."""
        evaluator = RAGFaithfulnessEvaluator()
        result = evaluator.evaluate("query", {
            "verdict": {"kind": "answered"},
            "answer": "test",
            "evidence": [{"document_id": "d1", "text": "ev"}],
            "claims": [{"text": "c1", "support_status": "UNSUPPORTED"}],
        })
        assert not result.passed


class TestRegressionCorpus:
    def test_get_queries(self) -> None:
        corpus = RegressionCorpus()
        queries = corpus.get_queries()
        assert len(queries) > 0
        assert all("query" in q for q in queries)


class TestEvaluationSuite:
    def test_run_evaluation_suite(self) -> None:
        """Full evaluation suite should run and produce a report."""
        report = run_evaluation_suite()
        assert report.total > 0
        assert report.passed > 0
        assert report.summary
