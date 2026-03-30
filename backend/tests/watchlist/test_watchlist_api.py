from __future__ import annotations

import base64
from pathlib import Path
import sys

from bson import ObjectId
from datetime import datetime, timedelta, timezone

import mongomock
from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import cartrap.app as app_module
from cartrap.config import Settings
from cartrap.modules.copart_provider.client import (
    CopartConnectorBootstrapResult,
    CopartConnectorExecutionResult,
    CopartEncryptedSessionBundle,
)
from cartrap.modules.copart_provider.errors import CopartGatewayUnavailableError
from cartrap.modules.copart_provider.models import CopartLotSnapshot


class FakeMongoManager:
    def __init__(self, uri: str, database_name: str, ping_on_startup: bool = False) -> None:
        self._database_name = database_name
        self._client = None

    def connect(self) -> None:
        self._client = mongomock.MongoClient(tz_aware=True)

    @property
    def database(self):
        return self._client[self._database_name]

    def close(self) -> None:
        self._client = None


class FakeProvider:
    def __init__(self, snapshots: dict[str, CopartLotSnapshot], should_fail: bool = False) -> None:
        self._snapshots = snapshots
        self._should_fail = should_fail

    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        if self._should_fail:
            raise RuntimeError("upstream failed")
        return self._snapshots[url]

    def close(self) -> None:
        return None


class GatewayUnavailableProvider:
    def fetch_lot(self, url: str) -> CopartLotSnapshot:
        del url
        raise CopartGatewayUnavailableError("gateway unavailable")

    def close(self) -> None:
        return None


class FakeConnectorClient:
    def __init__(self, app) -> None:
        self._app = app

    def bootstrap_connector_session(
        self,
        *,
        username: str,
        password: str,
        client_ip: str | None = None,
        correlation_id: str | None = None,
    ) -> CopartConnectorBootstrapResult:
        del password
        del client_ip
        del correlation_id
        bundle = CopartEncryptedSessionBundle(
            encrypted_bundle=f"bundle:{username}",
            key_version="v1",
            captured_at=datetime.now(timezone.utc),
            expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
        return CopartConnectorBootstrapResult(
            bundle=bundle,
            account_label=username,
            connection_status="connected",
            verified_at=datetime.now(timezone.utc),
        )

    def search_with_connector_session(self, payload: dict, bundle: CopartEncryptedSessionBundle) -> CopartConnectorExecutionResult:
        del payload
        del bundle
        raise RuntimeError("Search execution is not used in watchlist tests.")

    def lot_details_with_connector_session(
        self,
        lot_number: str,
        bundle: CopartEncryptedSessionBundle,
        etag: str | None = None,
    ) -> CopartConnectorExecutionResult:
        del bundle
        del etag
        provider = self._app.state.copart_provider_factory()
        snapshot = provider.fetch_lot(f"https://www.copart.com/lot/{lot_number}")
        payload = {
            "lotDetails": {
                "lotNumber": int(snapshot.lot_number),
                "lotDescription": snapshot.title,
                "saleDate": snapshot.sale_date.isoformat() if snapshot.sale_date else None,
                "currentBid": snapshot.current_bid,
                "buyTodayBid": snapshot.buy_now_price,
                "currencyCode": snapshot.currency,
                "status": snapshot.raw_status,
                "lotImages": [{"url": str(url)} for url in snapshot.image_urls],
                "thumbnailUrl": str(snapshot.thumbnail_url) if snapshot.thumbnail_url else None,
                "odometer": snapshot.odometer,
                "primaryDamage": snapshot.primary_damage,
                "estimatedRetailValue": snapshot.estimated_retail_value,
                "hasKey": snapshot.has_key,
                "drivetrain": snapshot.drivetrain,
                "highlights": snapshot.highlights,
                "encryptedVIN": _encode_vin(snapshot.vin),
            }
        }
        return CopartConnectorExecutionResult(
            payload=payload,
            bundle=CopartEncryptedSessionBundle(
                encrypted_bundle="bundle:rotated",
                key_version="v1",
                captured_at=datetime.now(timezone.utc),
                expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
            ),
            etag='"lot-etag"',
            not_modified=False,
            connection_status="connected",
            verified_at=datetime.now(timezone.utc),
            used_at=datetime.now(timezone.utc),
        )

    def close(self) -> None:
        return None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(app_module, "MongoManager", FakeMongoManager)
    settings = Settings(
        environment="test",
        mongo_uri="mongodb://unused",
        mongo_db="cartrap_test",
        jwt_secret="test-secret-123-test-secret-123x",
        jwt_refresh_secret="refresh-secret-123-refresh-secret-123",
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_password="AdminPass123",
    )
    app = app_module.create_app(settings)

    snapshots = {
        "https://www.copart.com/lot/12345678": CopartLotSnapshot(
            lot_number="12345678",
            title="2020 TOYOTA CAMRY SE",
            url="https://www.copart.com/lot/12345678",
            thumbnail_url="https://img.copart.com/12345678-detail.jpg",
            image_urls=[
                "https://img.copart.com/12345678-detail.jpg",
                "https://img.copart.com/12345678-detail-2.jpg",
            ],
            odometer="12,345 ACTUAL",
            primary_damage="FRONT END",
            estimated_retail_value=36500.0,
            has_key=True,
            drivetrain="AWD",
            highlights=["Run and Drive", "Enhanced Vehicles"],
            vin="1FA6P8TH0J5100001",
            status="on_approval",
            raw_status="On Approval",
            sale_date=datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
            current_bid=4200.0,
            buy_now_price=6500.0,
            currency="USD",
        ),
        "https://www.copart.com/lot/87654321": CopartLotSnapshot(
            lot_number="87654321",
            title="2018 HONDA CIVIC EX",
            url="https://www.copart.com/lot/87654321",
            thumbnail_url=None,
            image_urls=[],
            odometer=None,
            primary_damage=None,
            estimated_retail_value=None,
            has_key=None,
            drivetrain=None,
            highlights=[],
            vin=None,
            status="upcoming",
            raw_status="Upcoming",
            sale_date=datetime(2026, 3, 21, 18, 30, tzinfo=timezone.utc),
            current_bid=1800.0,
            buy_now_price=None,
            currency="USD",
        ),
    }
    app.state.copart_provider_factory = lambda: FakeProvider(snapshots)
    app.state.copart_connector_client_factory = lambda: FakeConnectorClient(app)
    return TestClient(app)


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


def _create_user(client: TestClient, email: str, password: str) -> str:
    admin_token = _login(client, "admin@example.com", "AdminPass123")
    invite = client.post(
        "/api/admin/invites",
        json={"email": email},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    client.post("/api/auth/invites/accept", json={"token": invite["token"], "password": password})
    token = _login(client, email, password)
    _connect_copart(client, token, email)
    return token


def _connect_copart(client: TestClient, token: str, username: str) -> None:
    response = client.post(
        "/api/provider-connections/copart/connect",
        json={"username": username, "password": "copart-secret"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def _encode_vin(vin: str | None) -> str | None:
    if not vin:
        return None
    key = "g2memberutil97534"
    encoded = bytes(ord(char) ^ ord(key[index]) for index, char in enumerate(vin))
    return base64.b64encode(encoded).decode("ascii")


def test_watchlist_crud_for_user(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "buyer@example.com", "BuyerPass123")
        create_response = client.post(
            "/api/watchlist",
            json={"lot_url": "https://www.copart.com/lot/12345678"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

        assert create_response.status_code == 201
        tracked_lot_id = create_response.json()["tracked_lot"]["id"]

        list_response = client.get(
            "/api/watchlist",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert list_response.status_code == 200
        assert len(list_response.json()["items"]) == 1
        assert list_response.json()["items"][0]["thumbnail_url"] == "https://img.copart.com/12345678-detail.jpg"
        assert list_response.json()["items"][0]["image_urls"] == [
            "https://img.copart.com/12345678-detail.jpg",
            "https://img.copart.com/12345678-detail-2.jpg",
        ]
        assert list_response.json()["items"][0]["freshness"]["status"] == "live"
        assert list_response.json()["items"][0]["freshness"]["retryable"] is False
        stale_after = datetime.fromisoformat(list_response.json()["items"][0]["freshness"]["stale_after"].replace("Z", "+00:00"))
        last_checked_at = datetime.fromisoformat(list_response.json()["items"][0]["last_checked_at"].replace("Z", "+00:00"))
        assert stale_after - last_checked_at <= timedelta(minutes=15)
        assert list_response.json()["items"][0]["refresh_state"]["status"] == "idle"
        assert list_response.json()["items"][0]["odometer"] == "12,345 ACTUAL"
        assert list_response.json()["items"][0]["primary_damage"] == "FRONT END"
        assert list_response.json()["items"][0]["estimated_retail_value"] == 36500.0
        assert list_response.json()["items"][0]["has_key"] is True
        assert list_response.json()["items"][0]["drivetrain"] == "AWD"
        assert list_response.json()["items"][0]["highlights"] == ["Run and Drive", "Enhanced Vehicles"]
        assert list_response.json()["items"][0]["vin"] == "1FA6P8TH0J5100001"

        delete_response = client.delete(
            f"/api/watchlist/{tracked_lot_id}",
            headers={"Authorization": f"Bearer {user_token}"},
        )

        assert delete_response.status_code == 204
        assert client.get("/api/watchlist", headers={"Authorization": f"Bearer {user_token}"}).json()["items"] == []


def test_watchlist_rejects_duplicate_lot(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "driver@example.com", "DriverPass123")
        payload = {"lot_url": "https://www.copart.com/lot/12345678"}
        headers = {"Authorization": f"Bearer {user_token}"}

        assert client.post("/api/watchlist", json=payload, headers=headers).status_code == 201
        duplicate_response = client.post("/api/watchlist", json=payload, headers=headers)

    assert duplicate_response.status_code == 409


def test_watchlist_keeps_update_marker_until_explicit_acknowledge(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "updates@example.com", "UpdatesPass123")
        older_id = client.post(
            "/api/watchlist",
            json={"lot_number": "12345678"},
            headers={"Authorization": f"Bearer {user_token}"},
        ).json()["tracked_lot"]["id"]
        newer_id = client.post(
            "/api/watchlist",
            json={"lot_number": "87654321"},
            headers={"Authorization": f"Bearer {user_token}"},
        ).json()["tracked_lot"]["id"]
        client.app.state.mongo.database["tracked_lots"].update_one(
            {"_id": ObjectId(older_id)},
            {
                "$set": {
                    "has_unseen_update": True,
                    "latest_change_at": datetime(2026, 3, 17, 16, 0, tzinfo=timezone.utc),
                    "latest_changes": {
                        "raw_status": {"before": "On Approval", "after": "Live"},
                        "current_bid": {"before": 4200.0, "after": 5100.0},
                    },
                }
            },
        )

        first_list_response = client.get("/api/watchlist", headers={"Authorization": f"Bearer {user_token}"})
        second_list_response = client.get("/api/watchlist", headers={"Authorization": f"Bearer {user_token}"})
        acknowledge_response = client.post(
            f"/api/watchlist/{older_id}/acknowledge-update",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        third_list_response = client.get("/api/watchlist", headers={"Authorization": f"Bearer {user_token}"})

    assert first_list_response.status_code == 200
    assert [item["id"] for item in first_list_response.json()["items"]] == [older_id, newer_id]
    assert first_list_response.json()["items"][0]["has_unseen_update"] is True
    assert first_list_response.json()["items"][0]["latest_changes"]["current_bid"] == {"before": 4200.0, "after": 5100.0}

    assert second_list_response.status_code == 200
    assert [item["id"] for item in second_list_response.json()["items"]] == [older_id, newer_id]
    assert second_list_response.json()["items"][0]["has_unseen_update"] is True
    assert second_list_response.json()["items"][0]["latest_changes"]["current_bid"] == {"before": 4200.0, "after": 5100.0}

    assert acknowledge_response.status_code == 200
    acknowledged_tracked_lot = acknowledge_response.json()["tracked_lot"]
    assert acknowledged_tracked_lot["has_unseen_update"] is False
    assert acknowledged_tracked_lot["latest_changes"]["current_bid"] == {"before": 4200.0, "after": 5100.0}

    assert third_list_response.status_code == 200
    assert [item["id"] for item in third_list_response.json()["items"]] == [older_id, newer_id]
    assert third_list_response.json()["items"][0]["has_unseen_update"] is False
    assert third_list_response.json()["items"][0]["latest_changes"]["current_bid"] == {"before": 4200.0, "after": 5100.0}


def test_watchlist_history_returns_recorded_snapshot_changes(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "history@example.com", "HistoryPass123")
        tracked_lot = client.post(
            "/api/watchlist",
            json={"lot_number": "12345678"},
            headers={"Authorization": f"Bearer {user_token}"},
        ).json()["tracked_lot"]
        tracked_lot_id = tracked_lot["id"]
        client.app.state.mongo.database["lot_snapshots"].insert_one(
            {
                "tracked_lot_id": tracked_lot_id,
                "owner_user_id": "history@example.com",
                "provider": "copart",
                "provider_lot_id": "12345678",
                "lot_key": "copart:12345678",
                "lot_number": "12345678",
                "status": "live",
                "raw_status": "Live",
                "sale_date": datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
                "current_bid": 5100.0,
                "buy_now_price": 6500.0,
                "currency": "USD",
                "detected_at": datetime.now(timezone.utc) + timedelta(minutes=1),
            }
        )

        history_response = client.get(
            f"/api/watchlist/{tracked_lot_id}/history",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert history_response.status_code == 200
    payload = history_response.json()
    assert payload["tracked_lot_id"] == tracked_lot_id
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["changes"]["raw_status"] == {"before": "On Approval", "after": "Live"}
    assert payload["entries"][0]["changes"]["current_bid"] == {"before": 4200.0, "after": 5100.0}


def test_watchlist_accepts_lot_number_input(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "lotnumber@example.com", "LotNumberPass123")
        response = client.post(
            "/api/watchlist",
            json={"lot_number": "12345678"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 201
    assert response.json()["tracked_lot"]["lot_number"] == "12345678"
    assert response.json()["tracked_lot"]["url"] == "https://www.copart.com/lot/12345678"
    assert response.json()["tracked_lot"]["thumbnail_url"] == "https://img.copart.com/12345678-detail.jpg"
    assert response.json()["tracked_lot"]["image_urls"] == [
        "https://img.copart.com/12345678-detail.jpg",
        "https://img.copart.com/12345678-detail-2.jpg",
    ]
    assert response.json()["tracked_lot"]["vin"] == "1FA6P8TH0J5100001"


def test_watchlist_rejects_empty_identifier(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "missing@example.com", "MissingPass123")
        response = client.post(
            "/api/watchlist",
            json={},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 422


def test_watchlist_rejects_lot_number_without_digits(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "badnumber@example.com", "BadNumberPass123")
        response = client.post(
            "/api/watchlist",
            json={"lot_number": "MUSTANG"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 422


def test_watchlist_returns_upstream_error_on_invalid_lot_source(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "source@example.com", "SourcePass123")
        client.app.state.copart_provider_factory = lambda: FakeProvider({}, should_fail=True)

        response = client.post(
            "/api/watchlist",
            json={"lot_url": "https://www.copart.com/lot/12345678"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to fetch lot details from Copart: upstream failed"


def test_watchlist_returns_gateway_unavailable_error_without_direct_fallback(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "gateway-watchlist@example.com", "GatewayWatchPass123")
        client.app.state.copart_provider_factory = lambda: GatewayUnavailableProvider()

        response = client.post(
            "/api/watchlist",
            json={"lot_url": "https://www.copart.com/lot/12345678"},
            headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Copart gateway is unavailable."


def test_watchlist_delete_is_scoped_to_owner(client: TestClient) -> None:
    with client:
        owner_token = _create_user(client, "owner@example.com", "OwnerPass123")
        other_token = _create_user(client, "other@example.com", "OtherPass123")
        tracked_lot_id = client.post(
            "/api/watchlist",
            json={"lot_url": "https://www.copart.com/lot/87654321"},
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()["tracked_lot"]["id"]

        response = client.delete(
            f"/api/watchlist/{tracked_lot_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )

    assert response.status_code == 404


def test_watchlist_list_returns_cached_legacy_item_and_schedules_repair_without_live_fetch(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "legacy@example.com", "LegacyPass123")
        owner_id = client.app.state.mongo.database["users"].find_one({"email": "legacy@example.com"})["_id"]
        tracked_lot_id = client.app.state.mongo.database["tracked_lots"].insert_one(
            {
                "owner_user_id": str(owner_id),
                "lot_number": "12345678",
                "url": "https://www.copart.com/lot/12345678",
                "title": "2020 TOYOTA CAMRY SE",
                "thumbnail_url": None,
                "image_urls": [],
                "status": "on_approval",
                "raw_status": "On Approval",
                "sale_date": datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
                "current_bid": 4200.0,
                "buy_now_price": 6500.0,
                "currency": "USD",
                "last_checked_at": datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
                "active": True,
                "created_at": datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
            }
        ).inserted_id

        response = client.get("/api/watchlist", headers={"Authorization": f"Bearer {user_token}"})
        stored = client.app.state.mongo.database["tracked_lots"].find_one({"_id": tracked_lot_id})

    assert response.status_code == 200
    assert response.json()["items"][0]["thumbnail_url"] is None
    assert response.json()["items"][0]["image_urls"] == []
    assert response.json()["items"][0]["odometer"] is None
    assert response.json()["items"][0]["refresh_state"]["status"] == "repair_pending"
    assert stored["thumbnail_url"] is None
    assert stored.get("repair_requested_at") is not None


def test_watchlist_refresh_live_repairs_legacy_item_without_read_path_fetch(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "legacy-refresh@example.com", "LegacyRefreshPass123")
        owner_id = client.app.state.mongo.database["users"].find_one({"email": "legacy-refresh@example.com"})["_id"]
        tracked_lot_id = client.app.state.mongo.database["tracked_lots"].insert_one(
            {
                "owner_user_id": str(owner_id),
                "lot_number": "12345678",
                "url": "https://www.copart.com/lot/12345678",
                "title": "2020 TOYOTA CAMRY SE",
                "thumbnail_url": None,
                "image_urls": [],
                "status": "on_approval",
                "raw_status": "On Approval",
                "sale_date": datetime(2026, 3, 20, 17, 0, tzinfo=timezone.utc),
                "current_bid": 4200.0,
                "buy_now_price": 6500.0,
                "currency": "USD",
                "last_checked_at": datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
                "active": True,
                "created_at": datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
            }
        ).inserted_id

        refresh_response = client.post(
            f"/api/watchlist/{tracked_lot_id}/refresh-live",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        stored = client.app.state.mongo.database["tracked_lots"].find_one({"_id": tracked_lot_id})

    assert refresh_response.status_code == 200
    assert refresh_response.json()["tracked_lot"]["thumbnail_url"] == "https://img.copart.com/12345678-detail.jpg"
    assert refresh_response.json()["tracked_lot"]["vin"] == "1FA6P8TH0J5100001"
    assert refresh_response.json()["tracked_lot"]["refresh_state"]["status"] == "idle"
    assert stored["thumbnail_url"] == "https://img.copart.com/12345678-detail.jpg"
    assert stored["vin"] == "1FA6P8TH0J5100001"
    assert stored.get("repair_requested_at") is None


def test_watchlist_does_not_refetch_when_detail_keys_are_present_with_null_values(client: TestClient) -> None:
    with client:
        user_token = _create_user(client, "nulls@example.com", "NullsPass123")
        owner_id = client.app.state.mongo.database["users"].find_one({"email": "nulls@example.com"})["_id"]
        client.app.state.copart_provider_factory = lambda: FakeProvider({}, should_fail=True)
        client.app.state.mongo.database["tracked_lots"].insert_one(
            {
                "owner_user_id": str(owner_id),
                "lot_number": "87654321",
                "url": "https://www.copart.com/lot/87654321",
                "title": "2018 HONDA CIVIC EX",
                "thumbnail_url": "https://img.copart.com/87654321-detail.jpg",
                "image_urls": ["https://img.copart.com/87654321-detail.jpg"],
                "odometer": None,
                "primary_damage": None,
                "estimated_retail_value": None,
                "has_key": None,
                "drivetrain": None,
                "highlights": [],
                "vin": None,
                "status": "upcoming",
                "raw_status": "Upcoming",
                "sale_date": datetime(2026, 3, 21, 18, 30, tzinfo=timezone.utc),
                "current_bid": 1800.0,
                "buy_now_price": None,
                "currency": "USD",
                "last_checked_at": datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
                "active": True,
                "created_at": datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 12, 18, 0, tzinfo=timezone.utc),
            }
        )

        response = client.get("/api/watchlist", headers={"Authorization": f"Bearer {user_token}"})

    assert response.status_code == 200
    assert response.json()["items"][0]["vin"] is None
