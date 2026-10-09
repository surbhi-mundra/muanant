"""SOVEREIGN admin CLI entrypoint.

Phase 1: minimal skeleton. Real subcommands (user create, project create,
reindex, audit-verify) are added in later phases as the relevant subsystems
land.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from sovereign import __version__

# Make scripts/ importable for audit-verify delegation
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def cmd_version() -> int:
    print(__version__)
    return 0


def cmd_audit_verify() -> int:
    """Delegate to the standalone verify_audit_chain script."""
    spec = importlib.util.spec_from_file_location(
        "verify_audit_chain", SCRIPTS_DIR / "verify_audit_chain.py"
    )
    if spec is None or spec.loader is None:
        print("error: could not load verify_audit_chain", file=sys.stderr)
        return 2
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return int(mod.main())


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sovereign-admin",
        description="SOVEREIGN admin CLI",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("version", help="Print SOVEREIGN version and exit")
    sub.add_parser("audit-verify", help="Verify the audit log hash chain")

    args = parser.parse_args()

    if args.cmd == "version":
        return cmd_version()
    if args.cmd == "audit-verify":
        return cmd_audit_verify()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
