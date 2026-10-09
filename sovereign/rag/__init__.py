"""RAG — 9-stage grounded retrieval pipeline.

The pipeline is the SOLE entry point for grounded Q&A. Naive
``query → vector search → LLM`` is forbidden.

::

    query
      ↓
    1. query understanding      (classify intent, extract constraints)
      ↓
    2. query rewriting          (expand / reformulate for better recall)
      ↓
    3. hybrid retrieval         (vector + keyword, RRF fusion)
      ↓
    4. metadata filtering       (project, document, date, type)
      ↓
    5. reranking                (cross-encoder over top-N candidates)
      ↓
    6. evidence selection       (pick top-k with score threshold)
      ↓
    7. LLM reasoning            (grounded answer from evidence, tool role)
      ↓
    8. evidence verification    (verify each claim against evidence)
      ↓
    9. final response           (with citations + support status)

A query that fails evidence verification returns
``"I don't have sufficient evidence to answer this."`` — this is a
first-class ``Verdict``, not an error.
"""
