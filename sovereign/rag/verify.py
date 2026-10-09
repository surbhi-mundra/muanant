"""Stage 8 — Evidence verification.

After the LLM generates an answer, this stage verifies each claim in the
answer against the evidence. Each claim gets a support status:

- SUPPORTED: the claim is directly backed by the evidence
- PARTIALLY_SUPPORTED: some aspects of the claim are backed, others aren't
- UNSUPPORTED: the claim is not backed by any evidence
- CONFLICTING: the evidence contains contradictory information

This stage is what makes SOVEREIGN's RAG "grounded" — we don't just trust
the LLM; we verify its claims against the evidence it was given.

In dev (MockBackend), verification uses a simple text-overlap heuristic.
In prod, the LLM does real entailment verification.
"""

from __future__ import annotations

import json
import re

from sovereign.core.logging import get_logger
from sovereign.models.gateway import ModelGateway
from sovereign.models.schemas import LLMRequest, Message
from sovereign.rag.model import Claim, EvidenceRef, SupportStatus

log = get_logger(__name__)

_VERIFY_SYSTEM_PROMPT = """You are an evidence verification system.
Given a claim and a list of evidence excerpts, determine if the claim is
supported by the evidence.

Return a JSON object with:
- "support_status": one of "SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONFLICTING"
- "reasoning": brief explanation (1 sentence)

Definitions:
- SUPPORTED: the claim is directly and fully backed by the evidence
- PARTIALLY_SUPPORTED: some aspects are backed but not all
- UNSUPPORTED: the evidence does not support this claim at all
- CONFLICTING: the evidence contains contradictory information about this claim

Return ONLY valid JSON."""


async def verify_answer(
    answer: str,
    evidence: list[EvidenceRef],
    gateway: ModelGateway,
) -> list[Claim]:
    """Stage 8: verify the LLM's answer against the evidence.

    Splits the answer into claims (by sentences), then verifies each claim.
    Returns a list of Claim objects with support_status set.
    """
    if not answer or not evidence:
        return []

    # Split answer into claim sentences
    claim_texts = _extract_claims(answer)
    if not claim_texts:
        return []

    claims: list[Claim] = []

    for claim_text in claim_texts:
        status = await _verify_single_claim(claim_text, evidence, gateway)
        claims.append(
            Claim(
                text=claim_text,
                evidence=evidence,  # all evidence is potentially relevant
                support_status=status,
            )
        )

    return claims


async def _verify_single_claim(
    claim_text: str,
    evidence: list[EvidenceRef],
    gateway: ModelGateway,
) -> SupportStatus:
    """Verify a single claim against the evidence."""
    try:
        evidence_text = "\n\n".join(
            f"[{i+1}] {ev.text}" for i, ev in enumerate(evidence)
        )

        resp = await gateway.text.complete(
            LLMRequest(
                messages=[
                    Message(role="system", content=_VERIFY_SYSTEM_PROMPT),
                    Message(
                        role="user",
                        content=f"Claim: {claim_text}\n\nEvidence:\n{evidence_text}",
                    ),
                ],
                json_mode=True,
                temperature=0.0,
            )
        )

        parsed = json.loads(resp.content)
        status_str = str(parsed.get("support_status", "UNSUPPORTED"))
        valid_statuses = ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "CONFLICTING")
        if status_str in valid_statuses:
            return status_str  # type: ignore[return-value]
        return "UNSUPPORTED"

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        log.debug("rag.verify.fallback", claim=claim_text, error=str(e))
        return _heuristic_verify(claim_text, evidence)


def _heuristic_verify(claim_text: str, evidence: list[EvidenceRef]) -> SupportStatus:
    """Simple text-overlap heuristic for verification (mock/fallback)."""
    claim_words = set(claim_text.lower().split())
    # Remove common words
    claim_words = {w for w in claim_words if len(w) > 3}

    if not claim_words:
        return "UNSUPPORTED"

    max_overlap = 0.0
    for ev in evidence:
        ev_words = set(ev.text.lower().split())
        if not ev_words:
            continue
        overlap = len(claim_words & ev_words) / len(claim_words)
        max_overlap = max(max_overlap, overlap)

    if max_overlap > 0.6:
        return "SUPPORTED"
    if max_overlap > 0.3:
        return "PARTIALLY_SUPPORTED"
    return "UNSUPPORTED"


def _extract_claims(answer: str) -> list[str]:
    """Split an answer into individual claims (sentences).

    Filters out the "insufficient evidence" message and citation-only
    fragments.
    """
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", answer.strip())

    claims: list[str] = []
    for raw_sent in sentences:
        sent = raw_sent.strip()
        # Skip empty or very short fragments
        if len(sent) < 10:
            continue
        # Skip the insufficient evidence message
        if "don't have sufficient evidence" in sent.lower():
            continue
        # Skip pure citation references like "[1]"
        if re.match(r"^\[\d+\]$", sent):
            continue
        claims.append(sent)

    return claims
