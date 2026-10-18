import os
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_smart_waste.db"
os.environ["API_TOKEN"] = "test-operator-token"

from app.main import app
from app.db import Base, engine

client = TestClient(app)
OP = {"Authorization": "Bearer test-operator-token"}

def register_device(device_id, bin_id):
    response = client.post("/api/v1/devices", json={"id":device_id,"bin_id":bin_id}, headers=OP)
    assert response.status_code == 201, response.text
    return {"X-Device-Token": response.json()["token"]}

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
    device_headers = register_device("device-1", "bin-test")
    event = {"bin_id":"bin-test","device_id":"device-1","message_id":"m-1","fill_percent":45,"measured_at":datetime.now(timezone.utc).isoformat()}
    first = client.post("/api/v1/telemetry", json=event, headers=device_headers)
    second = client.post("/api/v1/telemetry", json=event, headers=device_headers)
    assert first.status_code == 202 and first.json()["duplicate"] is False
    assert second.status_code == 202 and second.json()["duplicate"] is True
    assert len(client.get("/api/v1/bins/bin-test/history", headers=OP).json()) == 1

def test_invalid_fill_rejected():
    event = {"bin_id":"missing","device_id":"d","message_id":"m","fill_percent":101,"measured_at":"2026-01-01T10:00:00Z"}
    assert client.post("/api/v1/telemetry", json=event, headers={}).status_code == 422

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

def test_duplicate_message_with_changed_payload_is_conflict():
    b = {"id":"bin-dup","latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":2,"source":"live"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    event = {"bin_id":"bin-dup","device_id":"device-dup","message_id":"stable-id","fill_percent":40,"measured_at":"2026-10-18T10:00:00Z"}
    device_headers = register_device("device-dup", "bin-dup")
    event["measured_at"] = datetime.now(timezone.utc).isoformat()
    assert client.post("/api/v1/telemetry", json=event, headers=device_headers).status_code == 202
    changed = {**event, "fill_percent":41}
    assert client.post("/api/v1/telemetry", json=changed, headers=device_headers).status_code == 409

def test_naive_and_future_telemetry_timestamps_are_rejected():
    naive = {"bin_id":"bin-time","device_id":"d","message_id":"naive","fill_percent":10,"measured_at":"2026-10-18T10:00:00"}
    assert client.post("/api/v1/telemetry", json=naive, headers={}).status_code == 422
    b = {"id":"bin-time","latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":2,"source":"live"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    device_headers = register_device("d", "bin-time")
    future = {**naive, "measured_at":(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}
    assert client.post("/api/v1/telemetry", json=future, headers=device_headers).status_code == 422

def test_operations_summary_and_job_events_are_persistent():
    b = {"id":"bin-summary","latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":2,"source":"demo"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    job = client.post("/api/v1/jobs", json={"bin_id":"bin-summary","demand_liters":100}, headers=OP).json()
    summary = client.get("/api/v1/operations/summary", headers=OP)
    assert summary.status_code == 200
    assert summary.json()["active_bins"] == 1
    assert summary.json()["jobs_by_status"]["detected"] == 1
    events = client.get(f"/api/v1/jobs/{job['id']}/events", headers=OP)
    assert events.status_code == 200
    assert events.json()[0]["new_status"] == "detected"
    assert client.get("/api/v1/jobs?status=unknown", headers=OP).status_code == 422

def test_dispatch_optimizes_approved_jobs_and_assigns_vehicle(monkeypatch):
    import asyncio
    import app.main as main_module

    async def fake_matrix(coords):
        n = len(coords)
        return {"distances_meters": [[0 if i == j else 100 + abs(i-j) * 20 for j in range(n)] for i in range(n)],
                "durations_seconds": [[0 if i == j else 60 for j in range(n)] for i in range(n)]}

    async def fake_route(coords):
        return {"distance_meters": 320, "duration_seconds": 240, "geometry": {"type":"LineString","coordinates":[[77.2,28.6],[77.21,28.61]]}}

    monkeypatch.setattr(main_module, "road_matrix", fake_matrix)
    monkeypatch.setattr(main_module, "road_route", fake_route)
    for bin_id, longitude in (("dispatch-a",77.20),("dispatch-b",77.21)):
        b = {"id":bin_id,"latitude":28.6,"longitude":longitude,"capacity_liters":1000,"criticality":2,"source":"live"}
        assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
        device_id = "device-"+bin_id
        device_headers = register_device(device_id, bin_id)
        telemetry = {"bin_id":bin_id,"device_id":device_id,"message_id":"now-"+bin_id,"fill_percent":30,"measured_at":datetime.now(timezone.utc).isoformat()}
        assert client.post("/api/v1/telemetry", json=telemetry, headers=device_headers).status_code == 202
    jobs = []
    for bin_id in ("dispatch-a","dispatch-b"):
        job = client.post("/api/v1/jobs", json={"bin_id":bin_id,"demand_liters":100}, headers=OP).json()
        jobs.append(job["id"])
        assert client.post(f"/api/v1/jobs/{job['id']}/transitions", json={"status":"approved","actor":"dispatcher"}, headers=OP).status_code == 200
    vehicle = {"id":"dispatch-truck","capacity_liters":500,"depot_latitude":28.6,"depot_longitude":77.2}
    assert client.post("/api/v1/vehicles", json=vehicle, headers=OP).status_code == 201
    response = client.post("/api/v1/routes/dispatch", json={"job_ids":jobs,"vehicle_ids":["dispatch-truck"]}, headers=OP)
    assert response.status_code == 200, response.text
    assert sorted(response.json()["assigned_job_ids"]) == sorted(jobs)
    for job_id in jobs:
        persisted = client.get("/api/v1/jobs", headers=OP).json()
        found = next(j for j in persisted if j["id"] == job_id)
        assert found["status"] == "assigned"
        assert found["assigned_vehicle_id"] == "dispatch-truck"
    assert client.get("/health/ready").json()["status"] == "ready"
    driver_response = client.post("/api/v1/drivers", json={"id":"driver-01","vehicle_id":"dispatch-truck"}, headers=OP)
    assert driver_response.status_code == 201
    driver_headers = {"X-Driver-Id":"driver-01","X-Driver-Token":driver_response.json()["token"]}
    driver_jobs = client.get("/api/v1/driver/jobs", headers=driver_headers)
    assert driver_jobs.status_code == 200
    assert sorted(j["id"] for j in driver_jobs.json()) == sorted(jobs)
    for job_id in jobs:
        started = client.post(f"/api/v1/driver/jobs/{job_id}/transition", json={"status":"in_progress"}, headers=driver_headers)
        assert started.status_code == 200
        completed = client.post(f"/api/v1/driver/jobs/{job_id}/transition", json={"status":"completed","note":"Collected and recorded by driver"}, headers=driver_headers)
        assert completed.status_code == 200
    assert client.get("/api/v1/driver/jobs", headers=driver_headers).json() == []

def test_job_priority_is_computed_from_fresh_fill_and_bin_criticality():
    b = {"id":"bin-priority","latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":5,"source":"live"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    device_headers = register_device("priority-device", "bin-priority")
    event = {"bin_id":"bin-priority","device_id":"priority-device","message_id":"priority-now","fill_percent":90,"measured_at":datetime.now(timezone.utc).isoformat()}
    assert client.post("/api/v1/telemetry", json=event, headers=device_headers).status_code == 202
    job = client.post("/api/v1/jobs", json={"bin_id":"bin-priority"}, headers=OP)
    assert job.status_code == 201
    assert 0 <= job.json()["priority"] <= 100
    assert job.json()["priority_method"] == "weighted heuristic"
    assert job.json()["demand_liters"] == 900

def test_device_credentials_are_scoped_revocable_and_rotatable():
    for bin_id in ("device-bin-a","device-bin-b"):
        b = {"id":bin_id,"latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":2,"source":"live"}
        assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    device_headers = register_device("scoped-device", "device-bin-a")
    event = {"bin_id":"device-bin-a","device_id":"scoped-device","message_id":"scope-1","fill_percent":15,"measured_at":datetime.now(timezone.utc).isoformat()}
    assert client.post("/api/v1/telemetry", json=event, headers={"X-Device-Token":"wrong"}).status_code == 401
    wrong_bin = {**event,"bin_id":"device-bin-b","message_id":"scope-2"}
    assert client.post("/api/v1/telemetry", json=wrong_bin, headers=device_headers).status_code == 403
    assert client.delete("/api/v1/devices/scoped-device", headers=OP).status_code == 200
    assert client.post("/api/v1/telemetry", json=event, headers=device_headers).status_code == 401
    rotated = client.post("/api/v1/devices/scoped-device/rotate-token", headers=OP)
    assert rotated.status_code == 200
    assert client.post("/api/v1/telemetry", json=event, headers={"X-Device-Token":rotated.json()["token"]}).status_code == 202

def test_csv_import_is_validated_idempotent_and_labeled_imported():
    b = {"id":"bin-import","latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":2,"source":"imported"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    csv_body = "bin_id,device_id,message_id,fill_percent,measured_at\nbin-import,dataset-1,row-1,42,2026-10-18T10:00:00Z\n"
    first = client.post("/api/v1/telemetry/import-csv", files={"file":("readings.csv",csv_body,"text/csv")}, headers=OP)
    assert first.status_code == 200, first.text
    assert first.json()["accepted"] == 1
    second = client.post("/api/v1/telemetry/import-csv", files={"file":("readings.csv",csv_body,"text/csv")}, headers=OP)
    assert second.status_code == 200
    assert second.json()["duplicates_skipped"] == 1
    history = client.get("/api/v1/bins/bin-import/history", headers=OP).json()
    assert len(history) == 1 and history[0]["source"] == "imported"

def test_csv_import_rejects_unknown_bins_without_partial_commit():
    csv_body = "bin_id,device_id,message_id,fill_percent,measured_at\nmissing,dataset-1,row-1,42,2026-10-18T10:00:00Z\n"
    response = client.post("/api/v1/telemetry/import-csv", files={"file":("readings.csv",csv_body,"text/csv")}, headers=OP)
    assert response.status_code == 422

def test_forecast_endpoint_uses_loaded_artifact_and_real_history(monkeypatch):
    import app.main as main_module

    class FakeModel:
        def predict(self, frame):
            assert list(frame.columns) == main_module.MODEL_FEATURES
            assert frame.iloc[0]["temperature_c"] == 25.0
            return [67.5]

    b = {"id":"bin-forecast","latitude":28.6,"longitude":77.2,"capacity_liters":1000,"criticality":3,"source":"live"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    headers = register_device("forecast-device", "bin-forecast")
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    for idx, fill in enumerate((20, 28, 35)):
        event = {"bin_id":"bin-forecast","device_id":"forecast-device","message_id":f"forecast-{idx}","fill_percent":fill,"temperature_c":25.0,"measured_at":(now-timedelta(hours=2-idx)).isoformat()}
        assert client.post("/api/v1/telemetry", json=event, headers=headers).status_code == 202
    artifact = {"model":FakeModel(),"features":main_module.MODEL_FEATURES,"metrics":{"evaluation_note":"test fixture"},"target":"next observed fill"}
    monkeypatch.setattr(main_module, "_load_forecast_artifact", lambda: artifact)
    response = client.get("/api/v1/forecasts", headers=OP)
    assert response.status_code == 200, response.text
    assert response.json()["predictions"][0]["predicted_next_fill_percent"] == 67.5
    assert response.json()["forecast_semantics"].startswith("next observed fill")

def test_job_demand_cannot_exceed_bin_capacity():
    b = {"id":"bin-capacity","latitude":28.6,"longitude":77.2,"capacity_liters":100,"criticality":2,"source":"demo"}
    assert client.post("/api/v1/bins", json=b, headers=OP).status_code == 201
    response = client.post("/api/v1/jobs", json={"bin_id":"bin-capacity","demand_liters":101}, headers=OP)
    assert response.status_code == 422
