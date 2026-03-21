"""Shared refresh job runtime primitives for worker-managed sync flows."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from pymongo.collection import Collection
from pymongo.database import Database


JOB_RUNTIME_COLLECTION = "job_runtime"
DEFAULT_JOB_LEASE_SECONDS = 120
DEFAULT_JOB_RETRY_BACKOFF_SECONDS = 60


class JobRuntimeService:
    def __init__(
        self,
        database: Database,
        *,
        lease_seconds: int = DEFAULT_JOB_LEASE_SECONDS,
        retry_backoff_seconds: int = DEFAULT_JOB_RETRY_BACKOFF_SECONDS,
    ) -> None:
        self._collection: Collection = database[JOB_RUNTIME_COLLECTION]
        self._lease_seconds = lease_seconds
        self._retry_backoff_seconds = retry_backoff_seconds
        self.ensure_indexes()

    def ensure_indexes(self) -> None:
        self._collection.create_index("execution_key", unique=True)
        self._collection.create_index("lease_expires_at")
        self._collection.create_index("next_retry_at")
        self._collection.create_index([("job_type", 1), ("resource_id", 1)])

    @staticmethod
    def build_execution_key(job_type: str, resource_id: str) -> str:
        return f"{job_type}:{resource_id}"

    def acquire(
        self,
        *,
        job_type: str,
        resource_id: str,
        now: datetime,
        metadata: dict | None = None,
    ) -> dict | None:
        execution_key = self.build_execution_key(job_type, resource_id)
        existing = self._collection.find_one({"execution_key": execution_key})
        if existing is not None:
            next_retry_at = existing.get("next_retry_at")
            if next_retry_at is not None and next_retry_at > now:
                return None
            lease_expires_at = existing.get("lease_expires_at")
            if existing.get("status") == "running" and lease_expires_at is not None and lease_expires_at > now:
                return None

        attempt_count = int(existing.get("attempt_count") or 0) + 1 if existing is not None else 1
        lease_expires_at = now + timedelta(seconds=self._lease_seconds)
        run_id = f"{execution_key}:{int(now.timestamp())}:{attempt_count}"
        document = {
            "job_type": job_type,
            "resource_id": resource_id,
            "execution_key": execution_key,
            "status": "running",
            "run_id": run_id,
            "attempt_count": attempt_count,
            "lease_acquired_at": now,
            "last_started_at": now,
            "lease_expires_at": lease_expires_at,
            "next_retry_at": None,
            "last_error_message": None,
            "retryable": False,
            "last_run_metadata": metadata or {},
            "updated_at": now,
        }
        self._collection.update_one(
            {"execution_key": execution_key},
            {
                "$set": document,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return self._collection.find_one({"execution_key": execution_key})

    def complete(
        self,
        runtime: dict,
        *,
        now: datetime,
        outcome: str,
        metadata: dict | None = None,
    ) -> dict:
        summary = self._build_outcome(
            runtime,
            status="succeeded",
            now=now,
            outcome=outcome,
            metadata=metadata,
            retryable=False,
            next_retry_at=None,
            error_message=None,
        )
        self._persist_outcome(runtime["execution_key"], summary)
        return summary

    def fail_retryable(
        self,
        runtime: dict,
        *,
        now: datetime,
        outcome: str,
        error_message: str,
        metadata: dict | None = None,
        backoff_seconds: int | None = None,
    ) -> dict:
        next_retry_at = now + timedelta(seconds=backoff_seconds or self._retry_backoff_seconds)
        summary = self._build_outcome(
            runtime,
            status="retryable_failure",
            now=now,
            outcome=outcome,
            metadata=metadata,
            retryable=True,
            next_retry_at=next_retry_at,
            error_message=error_message,
        )
        self._persist_outcome(runtime["execution_key"], summary)
        return summary

    def fail_non_retryable(
        self,
        runtime: dict,
        *,
        now: datetime,
        outcome: str,
        error_message: str,
        metadata: dict | None = None,
    ) -> dict:
        summary = self._build_outcome(
            runtime,
            status="failed",
            now=now,
            outcome=outcome,
            metadata=metadata,
            retryable=False,
            next_retry_at=None,
            error_message=error_message,
        )
        self._persist_outcome(runtime["execution_key"], summary)
        return summary

    def describe_skip(self, *, job_type: str, resource_id: str, now: datetime) -> dict:
        execution_key = self.build_execution_key(job_type, resource_id)
        existing = self._collection.find_one({"execution_key": execution_key})
        if existing is None:
            return {
                "job_type": job_type,
                "resource_id": resource_id,
                "execution_key": execution_key,
                "status": "skipped",
                "skip_reason": "not_eligible",
                "attempt_count": 0,
                "run_id": None,
                "started_at": None,
                "finished_at": now,
                "next_retry_at": None,
                "retryable": False,
                "lease_expires_at": None,
                "error_message": None,
                "outcome": "skipped",
                "metadata": {},
            }

        lease_expires_at = existing.get("lease_expires_at")
        next_retry_at = existing.get("next_retry_at")
        if existing.get("status") == "running" and lease_expires_at is not None and lease_expires_at > now:
            skip_reason = "locked"
        elif next_retry_at is not None and next_retry_at > now:
            skip_reason = "backoff"
        else:
            skip_reason = "not_eligible"
        return {
            "job_type": job_type,
            "resource_id": resource_id,
            "execution_key": execution_key,
            "status": "skipped",
            "skip_reason": skip_reason,
            "attempt_count": int(existing.get("attempt_count") or 0),
            "run_id": existing.get("run_id"),
            "started_at": existing.get("last_started_at"),
            "finished_at": now,
            "next_retry_at": next_retry_at,
            "retryable": False,
            "lease_expires_at": lease_expires_at,
            "error_message": existing.get("last_error_message"),
            "outcome": "skipped",
            "metadata": existing.get("last_run_metadata", {}),
        }

    def _persist_outcome(self, execution_key: str, summary: dict) -> None:
        self._collection.update_one(
            {"execution_key": execution_key},
            {
                "$set": {
                    "status": summary["status"],
                    "run_id": summary["run_id"],
                    "attempt_count": summary["attempt_count"],
                    "last_started_at": summary["started_at"],
                    "last_finished_at": summary["finished_at"],
                    "last_outcome": summary["outcome"],
                    "last_run_metadata": summary["metadata"],
                    "retryable": summary["retryable"],
                    "next_retry_at": summary["next_retry_at"],
                    "last_error_message": summary["error_message"],
                    "lease_expires_at": summary["finished_at"],
                    "updated_at": summary["finished_at"],
                }
            },
        )

    @staticmethod
    def _build_outcome(
        runtime: dict,
        *,
        status: str,
        now: datetime,
        outcome: str,
        metadata: dict | None,
        retryable: bool,
        next_retry_at: datetime | None,
        error_message: str | None,
    ) -> dict:
        return {
            "job_type": runtime["job_type"],
            "resource_id": runtime["resource_id"],
            "execution_key": runtime["execution_key"],
            "status": status,
            "skip_reason": None,
            "attempt_count": int(runtime.get("attempt_count") or 1),
            "run_id": runtime.get("run_id"),
            "started_at": runtime.get("last_started_at"),
            "finished_at": now,
            "next_retry_at": next_retry_at,
            "retryable": retryable,
            "lease_expires_at": runtime.get("lease_expires_at"),
            "error_message": error_message,
            "outcome": outcome,
            "metadata": metadata or {},
        }
