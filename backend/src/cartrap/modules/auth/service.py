"""Auth and invite business logic."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets

import jwt
from fastapi import HTTPException, status
from pydantic import EmailStr
from pymongo.database import Database

from cartrap.config import Settings
from cartrap.modules.auth.models import (
    INVITE_ACCEPTED,
    INVITE_PENDING,
    INVITE_REVOKED,
    ROLE_ADMIN,
    ROLE_USER,
    USER_STATUS_ACTIVE,
)
from cartrap.modules.auth.repository import AuthRepository


class AuthService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self.repository = AuthRepository(database)
        self.settings = settings
        self.repository.ensure_indexes()

    def ensure_bootstrap_admin(self) -> None:
        if not self.settings.bootstrap_admin_email or not self.settings.bootstrap_admin_password:
            return

        email = self.settings.bootstrap_admin_email.lower()
        existing = self.repository.find_user_by_email(email)
        if existing is not None:
            return

        now = self._now()
        self.repository.create_user(
            {
                "email": email,
                "password_hash": self.hash_password(self.settings.bootstrap_admin_password),
                "role": ROLE_ADMIN,
                "status": USER_STATUS_ACTIVE,
                "created_at": now,
                "updated_at": now,
                "last_login_at": None,
            }
        )

    def create_invite(self, email: EmailStr, created_by_user_id: str) -> dict:
        normalized_email = str(email).lower()
        if self.repository.find_user_by_email(normalized_email) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists.")

        now = self._now()
        invite = self.repository.create_invite(
            {
                "email": normalized_email,
                "token": secrets.token_urlsafe(24),
                "status": INVITE_PENDING,
                "expires_at": now + timedelta(hours=self.settings.invite_ttl_hours),
                "accepted_at": None,
                "revoked_at": None,
                "created_at": now,
                "created_by": created_by_user_id,
            }
        )
        return self.serialize_invite(invite)

    def revoke_invite(self, invite_id: str) -> dict:
        invite = self.repository.find_invite_by_id(invite_id)
        if invite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
        if invite["status"] != INVITE_PENDING:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite is not pending.")

        self.repository.revoke_invite(invite_id, self._now())
        invite["status"] = INVITE_REVOKED
        return self.serialize_invite(invite)

    def accept_invite(self, token: str, password: str) -> dict:
        invite = self.repository.find_invite_by_token(token)
        if invite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
        if invite["status"] != INVITE_PENDING:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite is not pending.")
        if invite["expires_at"] < self._now():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite has expired.")

        now = self._now()
        user = self.repository.create_user(
            {
                "email": invite["email"],
                "password_hash": self.hash_password(password),
                "role": ROLE_USER,
                "status": USER_STATUS_ACTIVE,
                "created_at": now,
                "updated_at": now,
                "last_login_at": None,
            }
        )
        self.repository.accept_invite(str(invite["_id"]), now)
        return self.serialize_user(user)

    def login(self, email: str, password: str) -> dict:
        user = self.repository.find_user_by_email(email.lower())
        if user is None or not self.verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

        now = self._now()
        self.repository.update_user_last_login(str(user["_id"]), now)
        user["last_login_at"] = now
        return self.issue_tokens(user)

    def refresh_tokens(self, refresh_token: str) -> dict:
        payload = self.decode_token(refresh_token, token_type="refresh")
        user = self.repository.find_user_by_id(payload["sub"])
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
        return self.issue_tokens(user)

    def get_current_user(self, access_token: str) -> dict:
        payload = self.decode_token(access_token, token_type="access")
        user = self.repository.find_user_by_id(payload["sub"])
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.")
        return self.serialize_user(user)

    def issue_tokens(self, user: dict) -> dict:
        now = self._now()
        subject = str(user["_id"])
        access_token = jwt.encode(
            {
                "sub": subject,
                "role": user["role"],
                "type": "access",
                "exp": now + timedelta(minutes=self.settings.access_token_ttl_minutes),
                "iat": now,
            },
            self.settings.jwt_secret,
            algorithm="HS256",
        )
        refresh_token = jwt.encode(
            {
                "sub": subject,
                "role": user["role"],
                "type": "refresh",
                "exp": now + timedelta(minutes=self.settings.refresh_token_ttl_minutes),
                "iat": now,
            },
            self.settings.jwt_refresh_secret,
            algorithm="HS256",
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    def decode_token(self, token: str, token_type: str) -> dict:
        secret = self.settings.jwt_secret if token_type == "access" else self.settings.jwt_refresh_secret
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc

        if payload.get("type") != token_type:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")
        return payload

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return f"{urlsafe_b64encode(salt).decode()}${urlsafe_b64encode(digest).decode()}"

    @staticmethod
    def verify_password(password: str, stored_password_hash: str) -> bool:
        salt_part, digest_part = stored_password_hash.split("$", maxsplit=1)
        salt = urlsafe_b64decode(salt_part.encode())
        expected = urlsafe_b64decode(digest_part.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(actual, expected)

    @staticmethod
    def serialize_invite(invite: dict) -> dict:
        return {
            "id": str(invite["_id"]),
            "email": invite["email"],
            "status": invite["status"],
            "token": invite["token"],
            "expires_at": invite["expires_at"],
        }

    @staticmethod
    def serialize_user(user: dict) -> dict:
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "role": user["role"],
            "status": user["status"],
        }

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
