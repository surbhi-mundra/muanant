"""Stage 2 — Query rewriting / expansion.

Takes the original query + the QueryAnalysis from stage 1, and produces
expanded query strings for better retrieval recall.

In dev (MockBackend), this returns the original query as-is.
In prod, the LLM generates reformulations (synonyms, decomposed sub-questions,
etc.) that are run as separate retrievals and merged.
"""

from __future__ import annotations

from sovereign.rag.model import QueryAnalysis


def expand_query(query: str, analysis: QueryAnalysis) -> list[str]:
    """Stage 2: produce expanded query strings for retrieval.

    Returns a list of query strings to run. The first is always the
    original; the rest are reformulations from the analysis.
    """
    queries = [query]

    # Add any rewritten queries from the LLM analysis
    for rq in analysis.rewritten_queries:
        if rq and rq not in queries:
            queries.append(rq)

    # If key terms were extracted, add a keyword-focused query
    if analysis.key_terms and len(analysis.key_terms) > 1:
        kw_query = " ".join(analysis.key_terms)
        if kw_query not in queries:
            queries.append(kw_query)

    return queries
