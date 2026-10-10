"""Authentication service — local auth with Argon2 + JWT.

Phase 11 v1: local auth (Argon2 password hashing + JWT tokens).
OIDC (Keycloak/Authentik) is the target for prod, behind the same interface.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass

from sovereign.core.config import get_settings
from sovereign.core.errors import AuthError
from sovereign.core.logging import get_logger

log = get_logger(__name__)

# JWT implementation (no external dep needed for HS256)
_JWT_HEADER = {"alg": "HS256", "typ": "JWT"}


def _b64url_encode(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    import base64

    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data)


def _hash_password(password: str) -> str:
    """Hash a password using a salted SHA-256 (simplified for dev).

    In prod, use Argon2 via passlib. The passlib dependency is declared
    but Argon2 requires the argon2-cffi backend; this fallback ensures
    auth works in all environments.
    """
    import os

    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return f"pbkdf2$sha256${salt.hex()}${h.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        parts = stored.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2":
            return False
        salt = bytes.fromhex(parts[2])
        expected = bytes.fromhex(parts[3])
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return hmac.compare_digest(h, expected)
    except Exception:
        return False


def create_token(user_id: str, role: str = "viewer", project_ids: list[str] | None = None) -> str:
    """Create a JWT token for a user."""
    settings = get_settings()
    secret = settings.jwt_secret.get_secret_value()
    ttl = settings.jwt_ttl_minutes * 60

    payload = {
        "sub": user_id,
        "role": role,
        "projects": project_ids or [],
        "iat": int(time.time()),
        "exp": int(time.time()) + ttl,
    }

    header_b64 = _b64url_encode(json.dumps(_JWT_HEADER).encode())
    payload_b64 = _b64url_encode(json.dumps(payload).encode())
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{signing_input}.{sig_b64}"


def verify_token(token: str) -> dict[str, object]:
    """Verify a JWT token. Returns the payload dict.

    Raises AuthError if invalid or expired.
    """
    settings = get_settings()
    secret = settings.jwt_secret.get_secret_value()

    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthError("invalid token format")

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            raise AuthError("invalid token signature")

        payload: dict[str, object] = json.loads(_b64url_decode(payload_b64))

        exp = payload.get("exp")
        if isinstance(exp, int) and exp < int(time.time()):
            raise AuthError("token expired")

        return payload

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        raise AuthError(f"token verification failed: {e}") from e


@dataclass(slots=True)
class User:
    """A user record."""

    id: str
    email: str
    display_name: str
    role: str
    is_active: bool = True


class AuthService:
    """Authentication service — register, login, verify.

    Phase 11 v1: in-memory user store (dev). Prod uses the database
    (User table from Phase 1) + OIDC.
    """

    def __init__(self) -> None:
        self._users: dict[str, tuple[User, str]] = {}  # email → (user, password_hash)

    def register(self, email: str, password: str, display_name: str = "", role: str = "viewer") -> User:
        """Register a new user. Returns the User object."""
        if email in self._users:
            raise AuthError("email already registered")

        from sovereign.core.ids import new_ulid

        user = User(
            id=new_ulid(),
            email=email,
            display_name=display_name or email,
            role=role,
        )
        password_hash = _hash_password(password)
        self._users[email] = (user, password_hash)

        log.info("auth.user.registered", user_id=user.id, email=email, role=role)
        return user

    def login(self, email: str, password: str) -> str:
        """Login a user. Returns a JWT token.

        Raises AuthError if credentials are invalid.
        """
        entry = self._users.get(email)
        if entry is None:
            raise AuthError("invalid credentials")

        user, stored_hash = entry
        if not user.is_active:
            raise AuthError("user inactive")

        if not _verify_password(password, stored_hash):
            raise AuthError("invalid credentials")

        token = create_token(user.id, user.role)
        log.info("auth.user.login", user_id=user.id, email=email)
        return token

    def get_user(self, email: str) -> User | None:
        """Get a user by email."""
        entry = self._users.get(email)
        return entry[0] if entry else None
