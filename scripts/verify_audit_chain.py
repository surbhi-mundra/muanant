#!/usr/bin/env python3
"""Verify the integrity of the SOVEREIGN audit chain (MongoDB).

Reads every document from the ``audit_events`` collection, recomputes each
hash, and checks that the chain is intact.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sovereign.audit.log import read_chain, verify_full_chain
from sovereign.core.config import get_settings
from sovereign.core.logging import configure_logging, get_logger
from sovereign.storage.db.base import get_db


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    settings = get_settings()
    configure_logging(settings)
    log = get_logger("verify_audit_chain")

    get_db(settings)

    try:
        db = get_db()
        rows = read_chain(db, since_seq=0, limit=10_000_000)
    except Exception as e:
        log.error("audit.chain.read_failed", error=str(e))
        return 2

    if not rows:
        log.info("audit.chain.empty")
        return 0

    log.info("audit.chain.read", rows=len(rows), first_seq=rows[0][0], last_seq=rows[-1][0])

    ok = verify_full_chain(db)
    if ok:
        log.info("audit.chain.ok", rows=len(rows))
        return 0
    log.error("audit.chain.broken")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
