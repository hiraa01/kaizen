from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt


class InvalidTokenError(Exception):
    pass


class JwtService:
    _ALGORITHM: str = "HS256"

    @staticmethod
    def _secret_key() -> str:
        # Prefer an explicit secret key in env for security.
        # Keep a dev fallback to avoid breaking local development.
        return os.getenv("JWT_SECRET_KEY", os.getenv("SECRET_KEY", "dev-secret-key"))

    @classmethod
    def create_access_token(cls, *, user_id: int, expires_in_minutes: int = 60 * 24 * 30) -> str:
        now: datetime = datetime.now(timezone.utc)
        expires_at: datetime = now + timedelta(minutes=expires_in_minutes)

        payload: dict[str, Any] = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "type": "access",
        }
        return jwt.encode(payload, cls._secret_key(), algorithm=cls._ALGORITHM)

    @classmethod
    def decode_user_id(cls, token: str) -> int:
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                cls._secret_key(),
                algorithms=[cls._ALGORITHM],
                options={"verify_aud": False},
            )
        except JWTError as exc:
            raise InvalidTokenError("Invalid token") from exc

        subject: Any = payload.get("sub")
        if subject is None:
            raise InvalidTokenError("Token missing subject")

        try:
            return int(subject)
        except (TypeError, ValueError) as exc:
            raise InvalidTokenError("Invalid token subject") from exc

