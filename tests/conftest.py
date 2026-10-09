"""SOVEREIGN test suite.

Layout:
- ``tests/unit/``         — fast, isolated, no DB/network
- ``tests/integration/``  — may use MongoDB, in-process FastAPI, mock backends
- ``tests/fixtures/``     — sample docs, recorded model responses

Tests NEVER require a GPU. Anything that would need a real model backend
is either skipped via ``@pytest.mark.requires_gpu`` or routed through the
MockBackend (which is the default in ``configs/models.yaml``).

Tests use MongoDB (localhost:27017). Make sure MongoDB is running locally
or via `docker run -d -p 27017:27017 mongo:7`.
"""

import os
import sys
from pathlib import Path

# Make sure the project root is on sys.path for `import sovereign`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Tests use mongomock (in-process, no MongoDB server needed).
# Uses the "mock://" URL scheme which triggers mongomock in storage/db/base.py.
os.environ.setdefault("SOVEREIGN_ENV", "dev")
os.environ.setdefault("DATABASE_URL", "mock://localhost/sovereign_test")
