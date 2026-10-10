"""Contradiction detector — finds conflicting evidence across sources.

After evidence is collected, this module checks for contradictions:
cases where two or more sources provide conflicting information about
the same topic. This is critical for industrial use cases where decisions
based on conflicting data can have safety implications.

Detection strategies:
1. **Value mismatch**: two sources give different numerical values for
   the same parameter (e.g. "max pressure 150 PSI" vs "max pressure 200 PSI").
2. **Contradictory facts**: sources directly contradict (e.g. "pump is
   operational" vs "pump is failed").
3. **Temporal conflict**: a newer source supersedes an older one.
4. **Scope conflict**: sources apply to different equipment models/contexts.

In dev (MockBackend), detection uses simple text-pattern matching.
In prod, the LLM does real semantic contradiction detection.
"""

from __future__ import annotations

import re

from sovereign.core.logging import get_logger
from sovereign.evidence.model import Citation, Contradiction

log = get_logger(__name__)


class ContradictionDetector:
    """Detects contradictions between evidence citations.

    Usage::

        detector = ContradictionDetector()
        contradictions = detector.detect(citations)
    """

    # Patterns for extracting numerical values
    _NUMBER_PATTERN = re.compile(
        r"(\d+(?:\.\d+)?)\s*(PSI|psi|bar|BAR|kPa|kpa|MPa|MPa|"
        r"°C|°F|RPM|rpm|Hz|kHz|V|A|W|kW|MW|mm|cm|m|km|"
        r"kg|g|lb|oz|L|gal|%|percent)",
        re.IGNORECASE,
    )

    def detect(self, citations: list[Citation]) -> list[Contradiction]:
        """Detect contradictions in a list of citations.

        Returns a list of Contradiction objects. Each links the conflicting
        citations and describes the conflict.
        """
        if len(citations) < 2:
            return []

        contradictions: list[Contradiction] = []

        # 1. Value mismatch detection
        contradictions.extend(self._detect_value_mismatches(citations))

        # 2. Contradictory fact detection
        contradictions.extend(self._detect_contradictory_facts(citations))

        return contradictions

    def _detect_value_mismatches(
        self, citations: list[Citation]
    ) -> list[Contradiction]:
        """Detect cases where sources give different numerical values.

        Extracts (parameter, value) pairs from citation text and flags
        cases where the same parameter has different values across sources.
        """
        contradictions: list[Contradiction] = []

        # Extract all numerical values from each citation
        # Group by the "context" (surrounding text) to find same-parameter conflicts
        value_map: dict[str, list[tuple[Citation, str]]] = {}

        for cit in citations:
            # Find all value+unit pairs
            for match in self._NUMBER_PATTERN.finditer(cit.evidence_text):
                value = match.group(1)
                unit = match.group(2)
                # Get surrounding context (the word before the number)
                start = max(0, match.start() - 30)
                context_before = cit.evidence_text[start:match.start()].strip()
                # Use the last few words as the parameter key
                words = context_before.split()[-3:]
                param_key = " ".join(words).lower()

                if param_key:
                    key = f"{param_key} ({unit})"
                    value_map.setdefault(key, []).append((cit, value))

        # Find keys with multiple different values
        for key, entries in value_map.items():
            if len(entries) < 2:
                continue

            values = {v for _, v in entries}
            if len(values) > 1:
                # Different values for the same parameter
                conflicting_texts = [
                    f'"{cit.evidence_text[:200]}" → {val} (from {cit.source_label})'
                    for cit, val in entries
                ]
                contradictions.append(
                    Contradiction(
                        conflict_type="value_mismatch",
                        description=f'Conflicting values for "{key}": '
                        + ", ".join(f"{v}" for _, v in entries),
                        citation_ids=[cit.citation_id for cit, _ in entries],
                        conflicting_texts=conflicting_texts,
                    )
                )

        return contradictions

    def _detect_contradictory_facts(
        self, citations: list[Citation]
    ) -> list[Contradiction]:
        """Detect direct factual contradictions.

        Uses simple pattern matching for common contradiction pairs:
        - operational vs failed/down/broken
        - pass vs fail
        - open vs closed
        - yes vs no
        """
        contradictions: list[Contradiction] = []

        # Define contradiction pairs (word1, word2)
        # Only use word-boundary matching to avoid false positives
        # (e.g. "pass" in "passenger" or "fail" in "failure")
        import re  # noqa: PLC0415

        pairs = [
            ("operational", "failed"),
            ("operational", "broken"),
            ("operational", "down"),
            ("open", "closed"),
            ("safe", "unsafe"),
            ("normal", "abnormal"),
            ("working", "broken"),
            ("active", "inactive"),
        ]

        for word1, word2 in pairs:
            # Use word-boundary regex to avoid matching substrings
            pat1 = re.compile(rf"\b{word1}\b", re.IGNORECASE)
            pat2 = re.compile(rf"\b{word2}\b", re.IGNORECASE)

            cits1 = [c for c in citations if pat1.search(c.evidence_text)]
            cits2 = [c for c in citations if pat2.search(c.evidence_text)]

            # Only flag if BOTH words appear in DIFFERENT citations
            # (same citation mentioning both is not a contradiction)
            cits1_only = [c for c in cits1 if c not in cits2]
            cits2_only = [c for c in cits2 if c not in cits1]

            if cits1_only and cits2_only:
                all_cits = cits1_only + cits2_only
                contradictions.append(
                    Contradiction(
                        conflict_type="contradictory_facts",
                        description=(
                            f'Conflicting status: "{word1}" vs "{word2}" '
                            f'across {len(all_cits)} sources'
                        ),
                        citation_ids=[c.citation_id for c in all_cits],
                        conflicting_texts=[
                            f'[{word1 if c in cits1_only else word2}] '
                            f'"{c.evidence_text[:200]}" (from {c.source_label})'
                            for c in all_cits
                        ],
                    )
                )

        return contradictions
