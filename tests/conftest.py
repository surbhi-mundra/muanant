"""SOVEREIGN test suite.

Layout:
- ``tests/unit/``         — fast, isolated, no DB/network
- ``tests/integration/``  — may use SQLite, in-process FastAPI, mock backends
- ``tests/fixtures/``     — sample docs, recorded model responses

Tests NEVER require a GPU. Anything that would need a real model backend
is either skipped via ``@pytest.mark.requires_gpu`` or routed through the
MockBackend (which is the default in ``configs/models.yaml``).
"""

import os
import sys
from pathlib import Path

# Make sure the project root is on sys.path for `import sovereign`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Tests run against an isolated in-memory SQLite DB by default.
# Per-test fixtures may override this via monkeypatch + reset_settings_cache().
os.environ.setdefault("SOVEREIGN_ENV", "dev")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
