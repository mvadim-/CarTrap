"""Mongo-backed repositories for auth and invite flows."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.collection import Collection
from pymongo.database import Database


class AuthRepository:
    def __init__(self, database: Database) -> None:
        self.users: Collection = database["users"]
        self.invites: Collection = database["invites"]

    def ensure_indexes(self) -> None:
        self.users.create_index("email", unique=True)
        self.invites.create_index("email")
        self.invites.create_index("token", unique=True)

    def find_user_by_email(self, email: str) -> Optional[dict]:
        return self.users.find_one({"email": email.lower()})

    def find_user_by_id(self, user_id: str) -> Optional[dict]:
        try:
            return self.users.find_one({"_id": ObjectId(user_id)})
        except (InvalidId, TypeError):
            return None

    def list_users(self) -> list[dict]:
        return list(self.users.find())

    def create_user(self, payload: dict) -> dict:
        document = dict(payload)
        result = self.users.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    def update_user_last_login(self, user_id: str, timestamp: datetime) -> None:
        self.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"last_login_at": timestamp}})

    def update_user(self, user_id: str, payload: dict) -> Optional[dict]:
        try:
            object_id = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        return self.users.find_one_and_update(
            {"_id": object_id},
            {"$set": dict(payload)},
            return_document=ReturnDocument.AFTER,
        )

    def delete_user(self, user_id: str) -> int:
        try:
            object_id = ObjectId(user_id)
        except (InvalidId, TypeError):
            return 0
        result = self.users.delete_one({"_id": object_id})
        return result.deleted_count

    def count_users(self, query: dict | None = None) -> int:
        return self.users.count_documents(query or {})

    def count_other_users_with_role_and_status(
        self,
        *,
        role: str,
        status: str,
        exclude_user_id: str,
    ) -> int:
        try:
            excluded_id = ObjectId(exclude_user_id)
        except (InvalidId, TypeError):
            return 0
        return self.users.count_documents(
            {
                "role": role,
                "status": status,
                "_id": {"$ne": excluded_id},
            }
        )

    def create_invite(self, payload: dict) -> dict:
        document = dict(payload)
        result = self.invites.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    def find_invite_by_token(self, token: str) -> Optional[dict]:
        return self.invites.find_one({"token": token})

    def find_invite_by_id(self, invite_id: str) -> Optional[dict]:
        try:
            return self.invites.find_one({"_id": ObjectId(invite_id)})
        except (InvalidId, TypeError):
            return None

    def list_invites(self, query: dict | None = None) -> list[dict]:
        return list(self.invites.find(query or {}).sort("created_at", -1))

    def delete_invites_by_email(self, email: str) -> int:
        result = self.invites.delete_many({"email": email.lower()})
        return result.deleted_count

    def revoke_invite(self, invite_id: str, revoked_at: datetime) -> None:
        self.invites.update_one(
            {"_id": ObjectId(invite_id)},
            {"$set": {"status": "revoked", "revoked_at": revoked_at}},
        )

    def accept_invite(self, invite_id: str, accepted_at: datetime) -> None:
        self.invites.update_one(
            {"_id": ObjectId(invite_id)},
            {"$set": {"status": "accepted", "accepted_at": accepted_at}},
        )
