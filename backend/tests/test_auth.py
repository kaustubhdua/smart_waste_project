import os
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite:///./test_smart_waste.db"
os.environ["API_TOKEN"] = "test-operator-token"

from fastapi.testclient import TestClient

from app.auth import hash_password, verify_password
from app.config import settings
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import OperatorSession, OperatorUser

client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def bootstrap(monkeypatch, username="rootadmin", password="correct-horse-battery-staple"):
    token = "bootstrap-secret-for-tests-" + ("x" * 32)
    monkeypatch.setattr(settings, "api_token", token)
    response = client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": token},
        json={"username": username, "password": password},
    )
    return token, response


def login(username="rootadmin", password="correct-horse-battery-staple"):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_password_hashing_is_salted_and_verifiable():
    first = hash_password("correct-horse-battery-staple")
    second = hash_password("correct-horse-battery-staple")
    assert first != second
    assert verify_password("correct-horse-battery-staple", first)
    assert not verify_password("wrong-password", first)
    assert not verify_password("correct-horse-battery-staple", "malformed")


def test_bootstrap_is_one_time_and_never_stores_plaintext_password(monkeypatch):
    _, response = bootstrap(monkeypatch)
    assert response.status_code == 201, response.text
    with SessionLocal() as db:
        user = db.query(OperatorUser).filter_by(username="rootadmin").one()
        assert user.password_hash != "correct-horse-battery-staple"
        assert verify_password("correct-horse-battery-staple", user.password_hash)
    second = client.post(
        "/api/v1/auth/bootstrap",
        headers={"X-Bootstrap-Token": settings.api_token},
        json={"username": "anotheradmin", "password": "another-secure-password"},
    )
    assert second.status_code == 409


def test_login_session_identity_logout_and_revocation(monkeypatch):
    bootstrap(monkeypatch)
    response = login()
    assert response.status_code == 200, response.text
    token = response.cookies.get("wasteops_session")
    assert response.json()["user"]["role"] == "admin"
    headers = {"Authorization": "Bearer " + token}
    assert client.get("/api/v1/auth/me", headers=headers).json()["username"] == "rootadmin"
    assert client.get("/api/v1/bins", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).json()["logged_out"] is True
    assert client.get("/api/v1/bins", headers=headers).status_code == 401


def test_admin_can_create_operator_but_operator_cannot_manage_users(monkeypatch):
    bootstrap(monkeypatch)
    admin_token = login().cookies.get("wasteops_session")
    admin_headers = {"Authorization": "Bearer " + admin_token}
    created = client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={"username": "dispatcher1", "password": "dispatcher-password-123", "role": "operator"},
    )
    assert created.status_code == 201, created.text
    operator_token = login("dispatcher1", "dispatcher-password-123").cookies.get("wasteops_session")
    operator_headers = {"Authorization": "Bearer " + operator_token}
    assert client.get("/api/v1/bins", headers=operator_headers).status_code == 200
    assert client.get("/api/v1/auth/users", headers=operator_headers).status_code == 403
    forbidden = client.post(
        "/api/v1/auth/users",
        headers=operator_headers,
        json={"username": "intruder", "password": "intruder-password-123", "role": "admin"},
    )
    assert forbidden.status_code == 403


def test_admin_revocation_invalidates_all_existing_sessions(monkeypatch):
    bootstrap(monkeypatch)
    admin_token = login().cookies.get("wasteops_session")
    admin_headers = {"Authorization": "Bearer " + admin_token}
    client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={"username": "dispatcher2", "password": "dispatcher-password-456", "role": "operator"},
    )
    operator_token = login("dispatcher2", "dispatcher-password-456").cookies.get("wasteops_session")
    revoked = client.post("/api/v1/auth/users/dispatcher2/revoke", headers=admin_headers)
    assert revoked.status_code == 200
    assert client.get("/api/v1/bins", headers={"Authorization": "Bearer " + operator_token}).status_code == 401


def test_last_active_administrator_cannot_be_revoked(monkeypatch):
    bootstrap(monkeypatch)
    token = login().cookies.get("wasteops_session")
    response = client.post(
        "/api/v1/auth/users/rootadmin/revoke",
        headers={"Authorization": "Bearer " + token},
    )
    assert response.status_code == 409


def test_expired_sessions_are_rejected(monkeypatch):
    bootstrap(monkeypatch)
    token = login().cookies.get("wasteops_session")
    with SessionLocal() as db:
        session = db.query(OperatorSession).one()
        session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    response = client.get("/api/v1/bins", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 401


def test_shared_api_token_is_not_accepted_as_production_operator_credential(monkeypatch):
    _, created = bootstrap(monkeypatch)
    assert created.status_code == 201
    token = settings.api_token
    monkeypatch.setattr(settings, "app_env", "production")
    response = client.get("/api/v1/bins", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 401


def test_password_change_rotates_current_session_and_revokes_all_previous_sessions(monkeypatch):
    bootstrap(monkeypatch)
    first_token = login().cookies.get("wasteops_session")
    second_token = login().cookies.get("wasteops_session")
    first_headers = {"Authorization": "Bearer " + first_token}
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=first_headers,
        json={
            "current_password": "correct-horse-battery-staple",
            "new_password": "new-correct-horse-battery-staple",
        },
    )
    assert changed.status_code == 200, changed.text
    renewed_token = changed.cookies.get("wasteops_session")
    assert renewed_token
    assert client.get("/api/v1/bins", headers={"Authorization": "Bearer " + renewed_token}).status_code == 200
    assert client.get("/api/v1/bins", headers=first_headers).status_code == 401
    assert client.get("/api/v1/bins", headers={"Authorization": "Bearer " + second_token}).status_code == 401
    assert login("rootadmin", "correct-horse-battery-staple").status_code == 401
    assert login("rootadmin", "new-correct-horse-battery-staple").status_code == 200


def test_repeated_failed_password_attempts_lock_account(monkeypatch):
    bootstrap(monkeypatch)
    for _ in range(8):
        assert login("rootadmin", "incorrect-password").status_code == 401
    locked = login("rootadmin", "incorrect-password")
    assert locked.status_code == 423
    assert login("rootadmin", "correct-horse-battery-staple").status_code == 423


def test_operator_cannot_enroll_or_rotate_device_credentials(monkeypatch):
    bootstrap(monkeypatch)
    admin_token = login().cookies.get("wasteops_session")
    admin_headers = {"Authorization": "Bearer " + admin_token}
    bin_payload = {
        "id": "bin-authz",
        "latitude": 28.6,
        "longitude": 77.2,
        "capacity_liters": 1000,
        "criticality": 2,
        "source": "demo",
    }
    assert client.post("/api/v1/bins", json=bin_payload, headers=admin_headers).status_code == 201
    client.post(
        "/api/v1/auth/users",
        headers=admin_headers,
        json={"username": "fieldops", "password": "field-operator-password", "role": "operator"},
    )
    operator_token = login("fieldops", "field-operator-password").cookies.get("wasteops_session")
    operator_headers = {"Authorization": "Bearer " + operator_token}
    forbidden = client.post(
        "/api/v1/devices",
        headers=operator_headers,
        json={"id": "sensor-authz", "bin_id": "bin-authz"},
    )
    assert forbidden.status_code == 403
    enrolled = client.post(
        "/api/v1/devices",
        headers=admin_headers,
        json={"id": "sensor-authz", "bin_id": "bin-authz"},
    )
    assert enrolled.status_code == 201
    assert client.post(
        "/api/v1/devices/sensor-authz/rotate-token",
        headers=operator_headers,
    ).status_code == 403


def test_service_event_actor_comes_from_authenticated_session_not_request_body(monkeypatch):
    bootstrap(monkeypatch)
    token = login().cookies.get("wasteops_session")
    headers = {"Authorization": "Bearer " + token}
    bin_payload = {
        "id": "bin-audit-actor",
        "latitude": 28.6,
        "longitude": 77.2,
        "capacity_liters": 1000,
        "criticality": 2,
        "source": "demo",
    }
    assert client.post("/api/v1/bins", json=bin_payload, headers=headers).status_code == 201
    job = client.post(
        "/api/v1/jobs",
        headers=headers,
        json={"bin_id": "bin-audit-actor", "demand_liters": 100},
    ).json()
    transition = client.post(
        "/api/v1/jobs/" + job["id"] + "/transitions",
        headers=headers,
        json={"status": "approved", "actor": "forged-admin-name"},
    )
    assert transition.status_code == 200
    events = client.get("/api/v1/jobs/" + job["id"] + "/events", headers=headers).json()
    assert events[-1]["actor"] == "rootadmin"
    assert events[-1]["actor"] != "forged-admin-name"
