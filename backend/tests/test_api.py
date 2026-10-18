import os
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_smart_waste.db"
os.environ["API_TOKEN"] = "test-operator-token"
os.environ["DEVICE_TOKEN"] = "test-device-token"

from app.main import app
from app.db import Base, engine

client = TestClient(app)
OP = {"Authorization": "Bearer test-operator-token"}
DEVICE = {"X-Device-Token": "test-device-token"}

def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def test_health_is_public():
    assert client.get("/health").json()["status"] == "ok"

def test_operator_token_required():
    assert client.get("/api/v1/bins").status_code == 401

def test_bin_and_idempotent_telemetry():
    b = {"id":"bin-test","latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":2,"source":"demo"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    event = {"bin_id":"bin-test","device_id":"device-1","message_id":"m-1","fill_percent":45,"measured_at":"2026-01-01T10:00:00Z"}
    first = client.post("/api/v1/telemetry", json=event, headers=DEVICE)
    second = client.post("/api/v1/telemetry", json=event, headers=DEVICE)
    assert first.status_code == 202 and first.json()["duplicate"] is False
    assert second.status_code == 202 and second.json()["duplicate"] is True
    assert len(client.get("/api/v1/bins/bin-test/history", headers=OP).json()) == 1

def test_invalid_fill_rejected():
    event = {"bin_id":"missing","device_id":"d","message_id":"m","fill_percent":101,"measured_at":"2026-01-01T10:00:00Z"}
    assert client.post("/api/v1/telemetry", json=event, headers=DEVICE).status_code == 422

def test_collection_job_state_machine_and_history():
    b = {"id":"bin-job","latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":2,"source":"demo"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    job_response = client.post("/api/v1/jobs", json={"bin_id":"bin-job","demand_liters":120,"priority":55}, headers=OP)
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]
    invalid = client.post(f"/api/v1/jobs/{job_id}/transitions", json={"status":"completed","actor":"dispatcher"}, headers=OP)
    assert invalid.status_code == 409
    for status in ("approved",):
        response = client.post(f"/api/v1/jobs/{job_id}/transitions", json={"status":status,"actor":"test-user"}, headers=OP)
        assert response.status_code == 200
    vehicle = {"id":"truck-state","capacity_liters":500,"depot_latitude":28.6,"depot_longitude":77.2}
    assert client.post("/api/v1/vehicles", json=vehicle, headers=OP).status_code == 201
    assigned = client.post(f"/api/v1/jobs/{job_id}/assign", json={"vehicle_id":"truck-state","actor":"dispatcher"}, headers=OP)
    assert assigned.status_code == 200
    for status in ("in_progress", "completed", "verified"):
        response = client.post(f"/api/v1/jobs/{job_id}/transitions", json={"status":status,"actor":"test-user"}, headers=OP)
        assert response.status_code == 200
    assert client.post(f"/api/v1/jobs/{job_id}/transitions", json={"status":"approved","actor":"test-user"}, headers=OP).status_code == 409

def test_assignment_requires_existing_vehicle_and_respects_capacity():
    b = {"id":"bin-assign","latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":2,"source":"demo"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    job = client.post("/api/v1/jobs", json={"bin_id":"bin-assign","demand_liters":300}, headers=OP).json()
    bad = client.post(f"/api/v1/jobs/{job['id']}/assign", json={"vehicle_id":"missing","actor":"dispatcher"}, headers=OP)
    assert bad.status_code == 404
    vehicle = {"id":"truck-1","capacity_liters":500,"depot_latitude":28.6,"depot_longitude":77.2}
    assert client.post("/api/v1/vehicles", json=vehicle, headers=OP).status_code == 201
    assigned = client.post(f"/api/v1/jobs/{job['id']}/assign", json={"vehicle_id":"truck-1","actor":"dispatcher"}, headers=OP)
    assert assigned.status_code == 200
    assert assigned.json()["assigned_vehicle_id"] == "truck-1"
