from __future__ import annotations

from pathlib import Path
import sys

from bson import ObjectId
from datetime import datetime, timezone

import mongomock
from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


import cartrap.app as app_module
from cartrap.config import Settings
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
            status="upcoming",
            raw_status="Upcoming",
            sale_date=datetime(2026, 3, 21, 18, 30, tzinfo=timezone.utc),
            current_bid=1800.0,
            buy_now_price=None,
            currency="USD",
        ),
    }
    app.state.copart_provider_factory = lambda: FakeProvider(snapshots)
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
    return _login(client, email, password)


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
            json={"lot_url": "https://www.copart.com/lot/404"},
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to fetch lot details from Copart: upstream failed"


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
