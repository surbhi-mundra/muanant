#!/usr/bin/env python3
"""Verify the integrity of the SOVEREIGN audit chain.

Reads every row from ``audit_events``, recomputes each hash, and checks
that:
  - the first row's ``prev_hash`` is the literal string ``"genesis"``
  - each subsequent row's ``prev_hash`` equals the previous row's ``hash``
  - each row's stored ``hash`` equals the recomputed hash

Exits 0 if the chain is intact, 1 otherwise. Designed to run as a periodic
cron job in prod.

Usage::

    python scripts/verify_audit_chain.py
    python scripts/verify_audit_chain.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Make the project importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sovereign.audit.log import read_chain, verify_full_chain
from sovereign.core.config import get_settings
from sovereign.core.logging import configure_logging, get_logger
from sovereign.storage.db.base import get_engine, session_scope


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL for this run only.",
    )
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    settings = get_settings()
    configure_logging(settings)
    log = get_logger("verify_audit_chain")

    # Force engine creation with current settings
    get_engine(settings)

    try:
        with session_scope() as s:
            rows = read_chain(s, since_seq=0, limit=10_000_000)
    except Exception as e:
        log.error("audit.chain.read_failed", error=str(e))
        return 2

    if not rows:
        log.info("audit.chain.empty")
        return 0

    log.info("audit.chain.read", rows=len(rows), first_seq=rows[0][0], last_seq=rows[-1][0])

    with session_scope() as s:
        ok = verify_full_chain(s)
    if ok:
        log.info("audit.chain.ok", rows=len(rows))
        return 0
    log.error("audit.chain.broken")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
