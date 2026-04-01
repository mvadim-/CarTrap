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
    ACTIVE_USER_STATUSES,
    INVITE_ACCEPTED,
    INVITE_PENDING,
    INVITE_REVOKED,
    INACTIVE_USER_STATUSES,
    ROLE_ADMIN,
    ROLE_USER,
    USER_STATUS_ACTIVE,
    USER_STATUS_BLOCKED,
    USER_STATUS_DISABLED,
)
from cartrap.modules.auth.repository import AuthRepository
from cartrap.modules.runtime_settings.service import RuntimeSettingsService


class AuthService:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        *,
        runtime_settings_service: RuntimeSettingsService | None = None,
    ) -> None:
        self.repository = AuthRepository(database)
        self.settings = settings
        self._runtime_settings_service = runtime_settings_service
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
                "expires_at": now + timedelta(hours=self._get_invite_ttl_hours()),
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
        self.ensure_user_is_active(user, status_code=status.HTTP_403_FORBIDDEN)

        now = self._now()
        self.repository.update_user_last_login(str(user["_id"]), now)
        user["last_login_at"] = now
        return self.issue_tokens(user)

    def refresh_tokens(self, refresh_token: str) -> dict:
        payload = self.decode_token(refresh_token, token_type="refresh")
        user = self.repository.find_user_by_id(payload["sub"])
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
        self.ensure_user_is_active(user)
        return self.issue_tokens(user)

    def get_current_user(self, access_token: str) -> dict:
        payload = self.decode_token(access_token, token_type="access")
        user = self.repository.find_user_by_id(payload["sub"])
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.")
        self.ensure_user_is_active(user)
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
            "accepted_at": invite.get("accepted_at"),
            "revoked_at": invite.get("revoked_at"),
            "created_at": invite.get("created_at"),
            "created_by": invite.get("created_by"),
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
    def serialize_user_for_admin(user: dict) -> dict:
        return {
            **AuthService.serialize_user(user),
            "created_at": user["created_at"],
            "updated_at": user["updated_at"],
            "last_login_at": user.get("last_login_at"),
        }

    @staticmethod
    def ensure_user_is_active(user: dict, *, status_code: int = status.HTTP_401_UNAUTHORIZED) -> None:
        user_status = user.get("status", USER_STATUS_ACTIVE)
        if user_status in ACTIVE_USER_STATUSES:
            return
        if user_status == USER_STATUS_BLOCKED:
            detail = "User account is blocked."
        elif user_status == USER_STATUS_DISABLED:
            detail = "User account is disabled."
        elif user_status in INACTIVE_USER_STATUSES:
            detail = "User account is inactive."
        else:
            detail = "User account is inactive."
        raise HTTPException(status_code=status_code, detail=detail)

    def _get_invite_ttl_hours(self) -> int:
        if self._runtime_settings_service is None:
            return self.settings.invite_ttl_hours
        return int(self._runtime_settings_service.get_effective_value("invite_ttl_hours"))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
