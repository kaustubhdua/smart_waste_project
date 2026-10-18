from datetime import datetime, timezone
import csv
import io
from math import exp
from pathlib import Path
from statistics import mean
import joblib
import pandas as pd
import json
from hmac import compare_digest
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4
from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .db import Base, engine, get_db
from .models import Bin, Telemetry, CollectionJob, ServiceEvent, RoutePlan, Vehicle, Device, Driver
from .schemas import BinCreate, BinOut, TelemetryIn, JobCreate, TransitionIn, RouteRequest, VehicleCreate, JobAssign, DispatchRequest, DeviceCreate, DriverCreate, DriverTransition
from .routing import road_route, road_matrix, RoutingError
from .optimizer import optimize_cvrp, OptimizationError

app = FastAPI(title="Smart Waste Operations API", version="1.1.0", description="Persistent bin telemetry, collection jobs and road-network routing.")
if settings.auto_create_schema:
    Base.metadata.create_all(bind=engine)
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.cors_origins.split(',') if origin.strip()], allow_credentials=False, allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'], allow_headers=['Authorization', 'Content-Type', 'X-Device-Token', 'X-Driver-Id', 'X-Driver-Token'])

def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def _is_stale(measured_at: datetime) -> bool:
    age_seconds = (datetime.now(timezone.utc) - _utc(measured_at)).total_seconds()
    return age_seconds > settings.telemetry_stale_after_minutes * 60 or age_seconds < -settings.telemetry_future_skew_seconds

def _priority_score(fill_percent: float, bin_row: Bin) -> float:
    hours_elapsed = 0.0
    if bin_row.last_emptied_at is not None:
        hours_elapsed = max(0.0, (datetime.now(timezone.utc) - _utc(bin_row.last_emptied_at)).total_seconds() / 3600)
    fill_weight = 1.0 / (1.0 + exp(-0.1 * (min(100.0, max(0.0, fill_percent)) - 65.0)))
    time_weight = min(hours_elapsed / 48.0, 1.0)
    criticality_multiplier = {1: 0.8, 2: 0.9, 3: 1.0, 4: 1.15, 5: 1.3}.get(bin_row.criticality, 1.0)
    return round(min(100.0, max(0.0, (70.0 * fill_weight + 30.0 * time_weight) * criticality_multiplier)), 2)

MODEL_FEATURES = ["capacity_liters", "temperature_c", "hour", "day_of_week", "is_weekend", "fill_lag_1h", "fill_lag_3h", "rolling_mean_6h"]

def _load_forecast_artifact():
    path = Path(settings.model_path)
    if not path.is_file():
        return None
    artifact = joblib.load(path)
    if isinstance(artifact, dict) and "model" in artifact:
        return artifact
    return {"model": artifact, "features": MODEL_FEATURES, "metrics": {"evaluation_note": "Legacy artifact; validation metadata unavailable."}}

def _predict_next_fill_for_bin(db: Session, bin_row: Bin, artifact=None):
    artifact = artifact if artifact is not None else _load_forecast_artifact()
    if artifact is None:
        return None, "model_artifact_missing"
    rows = list(db.scalars(select(Telemetry).where(Telemetry.bin_id == bin_row.id).order_by(Telemetry.measured_at.desc()).limit(6)))
    rows.reverse()
    if len(rows) < 3:
        return None, "insufficient_history"
    intervals_minutes = [(_utc(rows[i].measured_at) - _utc(rows[i - 1].measured_at)).total_seconds() / 60 for i in range(1, len(rows))]
    if any(interval < 30 or interval > 90 for interval in intervals_minutes[-2:]):
        return None, "history_cadence_mismatch"
    latest = rows[-1]
    if _is_stale(latest.measured_at):
        return None, "stale_telemetry"
    if latest.temperature_c is None:
        return None, "temperature_missing"
    timestamp = _utc(latest.measured_at)
    feature_row = {
        "capacity_liters": bin_row.capacity_liters,
        "temperature_c": latest.temperature_c,
        "hour": timestamp.hour,
        "day_of_week": timestamp.weekday(),
        "is_weekend": int(timestamp.weekday() >= 5),
        "fill_lag_1h": latest.fill_percent,
        "fill_lag_3h": rows[-3].fill_percent,
        "rolling_mean_6h": mean(row.fill_percent for row in rows[-6:]),
    }
    feature_names = artifact.get("features", MODEL_FEATURES)
    missing = set(feature_names).difference(feature_row)
    if missing:
        raise ValueError(f"Model expects unsupported features: {sorted(missing)}")
    frame = pd.DataFrame([{name: feature_row[name] for name in feature_names}])
    prediction = float(artifact["model"].predict(frame)[0])
    if not (-float("inf") < prediction < float("inf")):
        raise ValueError("Model returned a non-finite prediction")
    return min(100.0, max(0.0, prediction)), None

def _release_vehicle_if_idle(db: Session, vehicle_id: str | None):
    if not vehicle_id:
        return
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        return
    db.flush()
    active_job = db.scalar(select(CollectionJob.id).where(
        CollectionJob.assigned_vehicle_id == vehicle_id,
        CollectionJob.status.in_(["assigned", "in_progress", "completed"]),
    ).limit(1))
    if active_job is None:
        vehicle.available = True

def require_operator(authorization: str | None = Header(default=None)):
    expected = "Bearer " + settings.api_token
    if not authorization or not compare_digest(authorization, expected) or settings.api_token.startswith(("change-me", "replace-with")):
        raise HTTPException(status_code=401, detail="Valid configured operator bearer token required")

@app.get("/health")
def health():
    return {"status": "ok", "service": "smart-waste-api"}

@app.get("/health/ready")
def readiness(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
    except Exception as exc:
        raise HTTPException(503, "Database is not ready") from exc
    return {"status": "ready", "database": "connected"}

@app.post("/api/v1/bins", response_model=BinOut, dependencies=[Depends(require_operator)], status_code=201)
def create_bin(payload: BinCreate, db: Session = Depends(get_db)):
    if db.get(Bin, payload.id):
        raise HTTPException(409, "Bin already exists")
    row = Bin(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@app.get("/api/v1/bins", response_model=list[BinOut], dependencies=[Depends(require_operator)])
def list_bins(db: Session = Depends(get_db)):
    return list(db.scalars(select(Bin).where(Bin.active.is_(True)).order_by(Bin.id)))

@app.post("/api/v1/devices", dependencies=[Depends(require_operator)], status_code=201)
def register_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    if not db.get(Bin, payload.bin_id):
        raise HTTPException(404, "Unknown bin")
    if db.get(Device, payload.id):
        raise HTTPException(409, "Device already exists; rotate its token or use another ID")
    raw_token = token_urlsafe(32)
    device = Device(id=payload.id, bin_id=payload.bin_id, token_hash=sha256(raw_token.encode("utf-8")).hexdigest())
    db.add(device)
    db.commit()
    return {"id": device.id, "bin_id": device.bin_id, "active": device.active, "token": raw_token, "token_notice": "Store this token securely; it will not be shown again."}

@app.get("/api/v1/devices", dependencies=[Depends(require_operator)])
def list_devices(db: Session = Depends(get_db)):
    rows = db.scalars(select(Device).order_by(Device.id))
    return [{"id": d.id, "bin_id": d.bin_id, "active": d.active, "last_seen_at": d.last_seen_at, "created_at": d.created_at} for d in rows]

@app.post("/api/v1/devices/{device_id}/rotate-token", dependencies=[Depends(require_operator)])
def rotate_device_token(device_id: str, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Unknown device")
    raw_token = token_urlsafe(32)
    device.token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
    device.active = True
    db.commit()
    return {"id": device.id, "token": raw_token, "token_notice": "Store this token securely; the previous token is now invalid."}

@app.delete("/api/v1/devices/{device_id}", dependencies=[Depends(require_operator)])
def revoke_device(device_id: str, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Unknown device")
    device.active = False
    db.commit()
    return {"id": device.id, "active": False}

@app.post("/api/v1/telemetry", status_code=202)
def ingest_telemetry(payload: TelemetryIn, x_device_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    device = db.get(Device, payload.device_id)
    if not device or not device.active or not x_device_token or not compare_digest(device.token_hash, sha256(x_device_token.encode("utf-8")).hexdigest()):
        raise HTTPException(401, "Valid active device credential required")
    if device.bin_id != payload.bin_id:
        raise HTTPException(403, "Device is not authorized for this bin")
    if not db.get(Bin, payload.bin_id):
        raise HTTPException(404, "Unknown bin")
    measured_at = _utc(payload.measured_at)
    if (measured_at - datetime.now(timezone.utc)).total_seconds() > settings.telemetry_future_skew_seconds:
        raise HTTPException(422, "Telemetry timestamp is too far in the future")
    row = Telemetry(**{**payload.model_dump(), "measured_at": measured_at}, source="live")
    device.last_seen_at = datetime.now(timezone.utc)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Telemetry).where(Telemetry.device_id == payload.device_id, Telemetry.message_id == payload.message_id))
        if existing:
            same_payload = (existing.bin_id == payload.bin_id and existing.fill_percent == payload.fill_percent and existing.temperature_c == payload.temperature_c and _utc(existing.measured_at) == measured_at)
            if not same_payload:
                raise HTTPException(409, "Message ID was already used with a different payload")
            current_device = db.get(Device, payload.device_id)
            if current_device:
                current_device.last_seen_at = datetime.now(timezone.utc)
                db.commit()
            return {"accepted": True, "duplicate": True, "telemetry_id": existing.id}
        raise HTTPException(409, "Telemetry could not be stored")
    db.refresh(row)
    return {"accepted": True, "duplicate": False, "telemetry_id": row.id}

@app.post("/api/v1/telemetry/import-csv", dependencies=[Depends(require_operator)])
async def import_telemetry_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import validated historical telemetry; the entire file is accepted or rejected as one batch."""
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(415, "Upload a .csv file")
    raw = await file.read(2_000_001)
    if len(raw) > 2_000_000:
        raise HTTPException(413, "CSV upload exceeds the 2 MB limit")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        required = {"bin_id", "device_id", "message_id", "fill_percent", "measured_at"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise HTTPException(422, detail={"message": "CSV is missing required columns", "required_columns": sorted(required)})
        pending, seen = [], {}
        duplicates = 0
        for row_number, raw_row in enumerate(reader, start=2):
            if row_number > 10001:
                raise HTTPException(413, "CSV exceeds the 10,000-row limit")
            try:
                event = TelemetryIn.model_validate(raw_row)
            except Exception as exc:
                raise HTTPException(422, detail={"row": row_number, "message": "Invalid telemetry row", "reason": str(exc)}) from exc
            if not db.get(Bin, event.bin_id):
                raise HTTPException(422, detail={"row": row_number, "message": f"Unknown bin: {event.bin_id}"})
            measured_at = _utc(event.measured_at)
            if (measured_at - datetime.now(timezone.utc)).total_seconds() > settings.telemetry_future_skew_seconds:
                raise HTTPException(422, detail={"row": row_number, "message": "Timestamp is too far in the future"})
            key = (event.device_id, event.message_id)
            signature = (event.bin_id, event.fill_percent, event.temperature_c, measured_at)
            if key in seen:
                if seen[key] != signature:
                    raise HTTPException(409, detail={"row": row_number, "message": "Message ID reused with a different payload in this file"})
                duplicates += 1
                continue
            seen[key] = signature
            existing = db.scalar(select(Telemetry).where(Telemetry.device_id == event.device_id, Telemetry.message_id == event.message_id))
            if existing:
                existing_signature = (existing.bin_id, existing.fill_percent, existing.temperature_c, _utc(existing.measured_at))
                if existing_signature != signature:
                    raise HTTPException(409, detail={"row": row_number, "message": "Message ID already exists with a different payload"})
                duplicates += 1
                continue
            pending.append(Telemetry(**{**event.model_dump(), "measured_at": measured_at}, source="imported"))
        if not pending and duplicates == 0:
            raise HTTPException(422, "CSV contains no telemetry rows")
        db.add_all(pending)
        db.commit()
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "CSV must be UTF-8 encoded") from exc
    except csv.Error as exc:
        db.rollback()
        raise HTTPException(422, "Malformed CSV file") from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Telemetry batch conflicted with concurrent writes; retry after refreshing data") from exc
    return {"accepted": len(pending), "duplicates_skipped": duplicates, "source": "imported"}

@app.get("/api/v1/bins/{bin_id}/history", dependencies=[Depends(require_operator)])
def bin_history(bin_id: str, limit: int = 100, db: Session = Depends(get_db)):
    if not db.get(Bin, bin_id):
        raise HTTPException(404, "Unknown bin")
    rows = db.scalars(select(Telemetry).where(Telemetry.bin_id == bin_id).order_by(Telemetry.measured_at.desc()).limit(max(1, min(limit, 500))))
    return [{"id": r.id, "fill_percent": r.fill_percent, "measured_at": r.measured_at, "received_at": r.received_at, "source": r.source} for r in rows]

@app.get("/api/v1/forecasts", dependencies=[Depends(require_operator)])
def list_forecasts(db: Session = Depends(get_db)):
    artifact = _load_forecast_artifact()
    if artifact is None:
        raise HTTPException(503, "No trained model artifact found. Train it with python person2_ml_prediction.py first.")
    results, skipped = [], []
    for bin_row in db.scalars(select(Bin).where(Bin.active.is_(True)).order_by(Bin.id)):
        try:
            prediction, reason = _predict_next_fill_for_bin(db, bin_row, artifact)
        except Exception as exc:
            skipped.append({"bin_id": bin_row.id, "reason": "model_error", "detail": str(exc)})
            continue
        if reason:
            skipped.append({"bin_id": bin_row.id, "reason": reason})
            continue
        latest = db.scalar(select(Telemetry).where(Telemetry.bin_id == bin_row.id).order_by(Telemetry.measured_at.desc()).limit(1))
        results.append({"bin_id": bin_row.id, "predicted_next_fill_percent": round(prediction, 2), "latest_observed_fill_percent": latest.fill_percent, "measured_at": _utc(latest.measured_at), "model_target": artifact.get("target", "next observed fill"), "data_source": latest.source})
    return {"predictions": results, "skipped": skipped, "model_metrics": artifact.get("metrics", {}), "forecast_semantics": "next observed fill level; not a validated 6/12-hour forecast", "model_artifact": settings.model_path}

@app.post("/api/v1/jobs", dependencies=[Depends(require_operator)], status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    bin_row = db.get(Bin, payload.bin_id)
    if not bin_row:
        raise HTTPException(404, "Unknown bin")
    latest = db.scalar(select(Telemetry).where(Telemetry.bin_id == payload.bin_id).order_by(Telemetry.measured_at.desc()).limit(1))
    demand = payload.demand_liters
    if demand is None and latest is not None and _is_stale(latest.measured_at):
        raise HTTPException(422, "Latest telemetry is stale; ingest a fresh reading before estimating demand")
    if demand is None:
        if latest is None:
            raise HTTPException(422, "Demand is required when no telemetry exists")
        demand_fill = latest.fill_percent
        demand_source = "latest_observed_telemetry"
        if settings.use_model_for_dispatch:
            try:
                forecast_fill, reason = _predict_next_fill_for_bin(db, bin_row)
            except Exception as exc:
                raise HTTPException(503, f"Model prediction failed: {exc}") from exc
            if reason:
                raise HTTPException(422, f"Model-driven demand is enabled but forecast is unavailable: {reason}")
            demand_fill = forecast_fill
            demand_source = "model_next_observation"
        demand = bin_row.capacity_liters * demand_fill / 100
    else:
        demand_source = "operator_supplied"
    if demand > bin_row.capacity_liters:
        raise HTTPException(422, "Collection demand cannot exceed the registered bin capacity")
    fill_for_priority = (demand * 100 / bin_row.capacity_liters) if demand_source == "model_next_observation" else (latest.fill_percent if latest is not None and not _is_stale(latest.measured_at) else 0.0)
    priority = payload.priority if payload.priority is not None else _priority_score(fill_for_priority, bin_row)
    job = CollectionJob(id=str(uuid4()), bin_id=payload.bin_id, demand_liters=demand, priority=priority)
    db.add(job)
    db.add(ServiceEvent(job_id=job.id, actor="system", previous_status="none", new_status="detected", note="Collection candidate created"))
    db.commit()
    return {"id": job.id, "bin_id": job.bin_id, "status": job.status, "demand_liters": job.demand_liters, "priority": job.priority, "priority_method": "weighted heuristic", "demand_source": demand_source}

ALLOWED = {
    "detected": {"approved", "exception"},
    "approved": {"assigned", "exception"},
    "assigned": {"in_progress", "approved", "exception"},
    "in_progress": {"completed", "exception"},
    "completed": {"verified"},
    "exception": {"approved"},
    "verified": set(),
}


@app.get("/api/v1/jobs", dependencies=[Depends(require_operator)])
def list_jobs(status: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    query = select(CollectionJob).order_by(CollectionJob.created_at.desc()).limit(max(1, min(limit, 500)))
    if status:
        if status not in ALLOWED:
            raise HTTPException(422, "Unknown job status")
        query = select(CollectionJob).where(CollectionJob.status == status).order_by(CollectionJob.created_at.desc()).limit(max(1, min(limit, 500)))
    rows = db.scalars(query)
    return [{"id": j.id, "bin_id": j.bin_id, "status": j.status, "demand_liters": j.demand_liters, "priority": j.priority, "assigned_vehicle_id": j.assigned_vehicle_id, "created_at": j.created_at, "updated_at": j.updated_at} for j in rows]

@app.get("/api/v1/jobs/{job_id}/events", dependencies=[Depends(require_operator)])
def job_events(job_id: str, db: Session = Depends(get_db)):
    if not db.get(CollectionJob, job_id):
        raise HTTPException(404, "Unknown job")
    rows = db.scalars(select(ServiceEvent).where(ServiceEvent.job_id == job_id).order_by(ServiceEvent.created_at, ServiceEvent.id))
    return [{"id": e.id, "actor": e.actor, "previous_status": e.previous_status, "new_status": e.new_status, "note": e.note, "created_at": e.created_at} @app.get("/api/v1/operations/summary", dependencies=[Depends(require_operator)])
def operations_summary(db: Session = Depends(get_db)):
    """Return dashboard counts using aggregates rather than loading every historical row."""
    now = datetime.now(timezone.utc)
    active_bins = int(db.scalar(select(func.count()).select_from(Bin).where(Bin.active.is_(True))) or 0)
    latest_by_bin = db.execute(
        select(Telemetry.bin_id, func.max(Telemetry.measured_at).label("latest_at"))
        .group_by(Telemetry.bin_id)
    ).all()
    fresh = sum(1 for row in latest_by_bin if not _is_stale(row.latest_at))
    job_counts = {
        status: int(count)
        for status, count in db.execute(
            select(CollectionJob.status, func.count()).group_by(CollectionJob.status)
        ).all()
    }
    for status in ALLOWED:
        job_counts.setdefault(status, 0)
    active_vehicles = int(
        db.scalar(select(func.count()).select_from(Vehicle).where(Vehicle.active.is_(True))) or 0
    )
    non_demo_bins = int(
        db.scalar(select(func.count()).select_from(Bin).where(Bin.source != "demo")) or 0
    )
    non_demo_telemetry = int(
        db.scalar(select(func.count()).select_from(Telemetry).where(Telemetry.source != "demo")) or 0
    )
    return {
        "generated_at": now,
        "active_bins": active_bins,
        "bins_with_telemetry": len(latest_by_bin),
        "fresh_telemetry_bins": fresh,
        "stale_or_future_telemetry_bins": len(latest_by_bin) - fresh,
        "jobs_by_status": job_counts,
        "vehicles_active": active_vehicles,
        "telemetry_stale_after_minutes": settings.telemetry_stale_after_minutes,
        "data_is_simulated": active_bins > 0 and non_demo_bins == 0 and non_demo_telemetry == 0,
    }
ry_rows),
    }

@app.post("/api/v1/vehicles", dependencies=[Depends(require_operator)], status_code=201)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    if db.get(Vehicle, payload.id):
        raise HTTPException(409, "Vehicle already exists")
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    return {"id": vehicle.id, "capacity_liters": vehicle.capacity_liters, "active": vehicle.active, "available": vehicle.available}

@app.get("/api/v1/vehicles", dependencies=[Depends(require_operator)])
def list_vehicles(db: Session = Depends(get_db)):
    rows = db.scalars(select(Vehicle).order_by(Vehicle.id))
    return [{"id": v.id, "capacity_liters": v.capacity_liters, "active": v.active, "available": v.available, "depot_latitude": v.depot_latitude, "depot_longitude": v.depot_longitude} for v in rows]

@app.post("/api/v1/jobs/{job_id}/assign", dependencies=[Depends(require_operator)])
def assign_job(job_id: str, payload: JobAssign, db: Session = Depends(get_db)):
    job = db.scalar(select(CollectionJob).where(CollectionJob.id == job_id).with_for_update())
    vehicle = db.scalar(select(Vehicle).where(Vehicle.id == payload.vehicle_id).with_for_update())
    if not job:
        raise HTTPException(404, "Unknown job")
    if not vehicle or not vehicle.active:
        raise HTTPException(404, "Unknown or inactive vehicle")
    if not vehicle.available:
        raise HTTPException(409, "Vehicle is already assigned to an active route")
    if job.status not in {"detected", "approved", "exception"}:
        raise HTTPException(409, f"Job cannot be assigned from status {job.status}")
    if job.demand_liters > vehicle.capacity_liters:
        raise HTTPException(422, "Job demand exceeds vehicle capacity")
    previous = job.status
    job.status = "assigned"
    job.assigned_vehicle_id = vehicle.id
    vehicle.available = False
    db.add(ServiceEvent(job_id=job.id, actor=payload.actor, previous_status=previous, new_status="assigned", note="Assigned to vehicle " + vehicle.id))
    db.commit()
    return {"id": job.id, "status": job.status, "assigned_vehicle_id": job.assigned_vehicle_id}

@app.post("/api/v1/jobs/{job_id}/transitions", dependencies=[Depends(require_operator)])
def transition_job(job_id: str, payload: TransitionIn, db: Session = Depends(get_db)):
    job = db.scalar(select(CollectionJob).where(CollectionJob.id == job_id).with_for_update())
    if not job:
        raise HTTPException(404, "Unknown job")
    if payload.status == "assigned" and not job.assigned_vehicle_id:
        raise HTTPException(409, "Assign a vehicle using the assignment endpoint before transitioning to assigned")
    if payload.status not in ALLOWED.get(job.status, set()):
        raise HTTPException(409, f"Invalid transition: {job.status} -> {payload.status}")
    previous = job.status
    previous_vehicle_id = job.assigned_vehicle_id
    job.status = payload.status
    if payload.status == "verified":
        bin_row = db.get(Bin, job.bin_id)
        if bin_row:
            bin_row.last_emptied_at = datetime.now(timezone.utc)
        _release_vehicle_if_idle(db, previous_vehicle_id)
    elif payload.status == "exception":
        _release_vehicle_if_idle(db, previous_vehicle_id)
    elif payload.status == "approved" and previous in {"assigned", "exception"}:
        job.assigned_vehicle_id = None
        _release_vehicle_if_idle(db, previous_vehicle_id)
    db.add(ServiceEvent(job_id=job.id, actor=payload.actor, previous_status=previous, new_status=payload.status, note=payload.note))
    db.commit()
    return {"id": job.id, "previous_status": previous, "status": job.status}

@app.post("/api/v1/routes/optimize", dependencies=[Depends(require_operator)])
async def optimize_route(payload: RouteRequest, db: Session = Depends(get_db)):
    bins = []
    for bin_id in payload.bin_ids:
        row = db.get(Bin, bin_id)
        if not row or not row.active:
            raise HTTPException(404, f"Unknown or inactive bin: {bin_id}")
        bins.append(row)
    coords = [(payload.depot_latitude, payload.depot_longitude)] + [(b.latitude, b.longitude) for b in bins]
    demands = [0.0]
    for row in bins:
        latest = db.scalar(select(Telemetry).where(Telemetry.bin_id == row.id).order_by(Telemetry.measured_at.desc()).limit(1))
        if latest is None:
            raise HTTPException(422, f"Missing telemetry for bin {row.id}; demand cannot be estimated")
        if _is_stale(latest.measured_at):
            raise HTTPException(422, f"Stale telemetry for bin {row.id}; route optimization requires fresh readings")
        demands.append(row.capacity_liters * latest.fill_percent / 100)
    capacities = [payload.vehicle_capacity_liters] * payload.num_vehicles
    try:
        matrix = await road_matrix(coords)
        optimized = optimize_cvrp(matrix["distances_meters"], demands, capacities)
        route_details = []
        for route in optimized["routes"]:
            ordered_nodes = [0] + route["stop_indices"] + [0]
            ordered_coords = [coords[i] for i in ordered_nodes]
            geometry = await road_route(ordered_coords) if route["stop_indices"] else {"distance_meters": 0, "duration_seconds": 0, "geometry": None}
            route_details.append({
                **route,
                "ordered_bin_ids": [bins[i - 1].id for i in route["stop_indices"]],
                "road_duration_seconds": geometry["duration_seconds"],
                "geometry": geometry["geometry"],
            })
    except RoutingError as exc:
        raise HTTPException(503, str(exc)) from exc
    except (OptimizationError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    plan_id = str(uuid4())
    response_payload = {"routes": route_details, "total_distance_meters": optimized["total_distance_meters"], "routing_provider": "OSRM", "solver": optimized["solver"], "data_mode": "telemetry-derived demand; verify sensor calibration before operational use"}
    db.add(RoutePlan(id=plan_id, depot_latitude=payload.depot_latitude, depot_longitude=payload.depot_longitude, routing_provider="OSRM", solver=optimized["solver"], total_distance_meters=optimized["total_distance_meters"], route_payload=json.dumps(response_payload)))
    db.commit()
    return {"route_plan_id": plan_id, **response_payload}

def _driver_auth(driver_id: str | None, token: str | None, db: Session) -> Driver:
    driver = db.get(Driver, driver_id) if driver_id else None
    if not driver or not driver.active or not token or not compare_digest(driver.token_hash, sha256(token.encode("utf-8")).hexdigest()):
        raise HTTPException(401, "Valid active driver credential required")
    driver.last_seen_at = datetime.now(timezone.utc)
    return driver

@app.post("/api/v1/drivers", dependencies=[Depends(require_operator)], status_code=201)
def register_driver(payload: DriverCreate, db: Session = Depends(get_db)):
    if db.get(Driver, payload.id):
        raise HTTPException(409, "Driver already exists")
    vehicle = db.get(Vehicle, payload.vehicle_id)
    if not vehicle or not vehicle.active:
        raise HTTPException(404, "Unknown or inactive vehicle")
    raw_token = token_urlsafe(32)
    driver = Driver(id=payload.id, vehicle_id=vehicle.id, token_hash=sha256(raw_token.encode("utf-8")).hexdigest())
    db.add(driver)
    db.commit()
    return {"id": driver.id, "vehicle_id": driver.vehicle_id, "token": raw_token, "token_notice": "Store this token securely; it will not be shown again."}

@app.get("/api/v1/drivers", dependencies=[Depends(require_operator)])
def list_drivers(db: Session = Depends(get_db)):
    rows = db.scalars(select(Driver).order_by(Driver.id))
    return [{"id": d.id, "vehicle_id": d.vehicle_id, "active": d.active, "last_seen_at": d.last_seen_at} for d in rows]

@app.post("/api/v1/drivers/{driver_id}/rotate-token", dependencies=[Depends(require_operator)])
def rotate_driver_token(driver_id: str, db: Session = Depends(get_db)):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(404, "Unknown driver")
    raw_token = token_urlsafe(32)
    driver.token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
    driver.active = True
    db.commit()
    return {"id": driver.id, "token": raw_token, "token_notice": "Store this token securely; the previous token is now invalid."}

@app.delete("/api/v1/drivers/{driver_id}", dependencies=[Depends(require_operator)])
def revoke_driver(driver_id: str, db: Session = Depends(get_db)):
    driver = db.get(Driver, driver_id)
    if not driver:
        raise HTTPException(404, "Unknown driver")
    driver.active = False
    db.commit()
    return {"id": driver.id, "active": False}

@app.get("/api/v1/driver/jobs")
def driver_jobs(x_driver_id: str | None = Header(default=None), x_driver_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    driver = _driver_auth(x_driver_id, x_driver_token, db)
    jobs = db.scalars(select(CollectionJob).where(CollectionJob.assigned_vehicle_id == driver.vehicle_id, CollectionJob.status.in_(["assigned", "in_progress"])).order_by(CollectionJob.priority.desc(), CollectionJob.created_at))
    result = []
    for job in jobs:
        bin_row = db.get(Bin, job.bin_id)
        result.append({"id": job.id, "bin_id": job.bin_id, "status": job.status, "demand_liters": job.demand_liters, "priority": job.priority, "latitude": bin_row.latitude if bin_row else None, "longitude": bin_row.longitude if bin_row else None})
    db.commit()
    return result

@app.post("/api/v1/driver/jobs/{job_id}/transition")
def driver_transition(job_id: str, payload: DriverTransition, x_driver_id: str | None = Header(default=None), x_driver_token: str | None = Header(default=None), db: Session = Depends(get_db)):
    driver = _driver_auth(x_driver_id, x_driver_token, db)
    job = db.scalar(select(CollectionJob).where(CollectionJob.id == job_id).with_for_update())
    if not job:
        raise HTTPException(404, "Unknown job")
    if job.assigned_vehicle_id != driver.vehicle_id:
        raise HTTPException(403, "Job is not assigned to this driver's vehicle")
    if payload.status not in ALLOWED.get(job.status, set()) or payload.status not in {"in_progress", "completed", "exception"}:
        raise HTTPException(409, f"Invalid driver transition: {job.status} -> {payload.status}")
    previous = job.status
    job.status = payload.status
    if payload.status == "completed":
        bin_row = db.get(Bin, job.bin_id)
        if bin_row:
            bin_row.last_emptied_at = datetime.now(timezone.utc)
    if payload.status == "exception":
        _release_vehicle_if_idle(db, driver.vehicle_id)
    db.add(ServiceEvent(job_id=job.id, actor="driver:" + driver.id, previous_status=previous, new_status=payload.status, note=payload.note))
    db.commit()
    return {"id": job.id, "previous_status": previous, "status": job.status}

@app.post("/api/v1/routes/dispatch", dependencies=[Depends(require_operator)])
async def dispatch_approved_jobs(payload: DispatchRequest, db: Session = Depends(get_db)):
    """Optimize approved jobs against registered vehicle capacities and atomically assign route stops."""
    jobs = []
    bins = []
    seen_bins = set()
    for job_id in payload.job_ids:
        job = db.scalar(select(CollectionJob).where(CollectionJob.id == job_id).with_for_update())
        if not job:
            raise HTTPException(404, f"Unknown job: {job_id}")
        if job.status != "approved":
            raise HTTPException(409, f"Job {job_id} must be approved before dispatch (current: {job.status})")
        if job.bin_id in seen_bins:
            raise HTTPException(422, "Only one open job per bin may be included in a dispatch")
        seen_bins.add(job.bin_id)
        bin_row = db.get(Bin, job.bin_id)
        latest = db.scalar(select(Telemetry).where(Telemetry.bin_id == job.bin_id).order_by(Telemetry.measured_at.desc()).limit(1))
        if not bin_row or not bin_row.active:
            raise HTTPException(422, f"Bin for job {job_id} is inactive")
        if job.demand_liters > bin_row.capacity_liters:
            raise HTTPException(422, f"Job {job_id} demand exceeds its bin capacity")
        if latest is None or _is_stale(latest.measured_at):
            raise HTTPException(422, f"Fresh telemetry is required for job {job_id}")
        jobs.append(job)
        bins.append(bin_row)
    vehicle_query = select(Vehicle).where(Vehicle.active.is_(True), Vehicle.available.is_(True)).order_by(Vehicle.id).with_for_update()
    if payload.vehicle_ids:
        vehicle_query = select(Vehicle).where(Vehicle.active.is_(True), Vehicle.available.is_(True), Vehicle.id.in_(payload.vehicle_ids)).order_by(Vehicle.id).with_for_update()
    vehicles = list(db.scalars(vehicle_query))
    if payload.vehicle_ids and len(vehicles) != len(payload.vehicle_ids):
        raise HTTPException(422, "One or more requested vehicles do not exist or are inactive")
    if not vehicles:
        raise HTTPException(422, "No active vehicles are registered")
    depot = (vehicles[0].depot_latitude, vehicles[0].depot_longitude)
    if any(abs(v.depot_latitude - depot[0]) > 0.0001 or abs(v.depot_longitude - depot[1]) > 0.0001 for v in vehicles[1:]):
        raise HTTPException(422, "Selected vehicles must share a depot for this CVRP planner")
    coords = [depot] + [(b.latitude, b.longitude) for b in bins]
    demands = [0.0] + [job.demand_liters for job in jobs]
    capacities = [v.capacity_liters for v in vehicles]
    try:
        matrix = await road_matrix(coords)
        optimized = optimize_cvrp(matrix["distances_meters"], demands, capacities)
        route_details = []
        assigned_job_ids = set()
        for route in optimized["routes"]:
            vehicle = vehicles[route["vehicle_index"]]
            if route["stop_indices"]:
                vehicle.available = False
            ordered_nodes = [0] + route["stop_indices"] + [0]
            ordered_coords = [coords[i] for i in ordered_nodes]
            geometry = await road_route(ordered_coords) if route["stop_indices"] else {"distance_meters": 0, "duration_seconds": 0, "geometry": None}
            route_jobs = []
            for node in route["stop_indices"]:
                job = jobs[node - 1]
                previous = job.status
                job.status = "assigned"
                job.assigned_vehicle_id = vehicle.id
                assigned_job_ids.add(job.id)
                db.add(ServiceEvent(job_id=job.id, actor="dispatcher", previous_status=previous, new_status="assigned", note=f"Assigned by route plan to vehicle {vehicle.id}"))
                route_jobs.append({"job_id": job.id, "bin_id": job.bin_id, "sequence": len(route_jobs) + 1, "demand_liters": job.demand_liters})
            route_details.append({**route, "vehicle_id": vehicle.id, "ordered_bin_ids": [bins[i - 1].id for i in route["stop_indices"]], "jobs": route_jobs, "road_distance_meters": geometry["distance_meters"], "road_duration_seconds": geometry["duration_seconds"], "geometry": geometry["geometry"]})
        if assigned_job_ids != {job.id for job in jobs}:
            raise OptimizationError("Optimizer returned a route that omitted one or more approved jobs")
    except RoutingError as exc:
        db.rollback()
        raise HTTPException(503, str(exc)) from exc
    except (OptimizationError, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    plan_id = str(uuid4())
    response_payload = {"routes": route_details, "total_distance_meters": optimized["total_distance_meters"], "routing_provider": "OSRM", "solver": optimized["solver"], "assigned_job_ids": sorted(assigned_job_ids), "data_mode": "approved jobs with fresh telemetry; verify sensor calibration before operational use"}
    db.add(RoutePlan(id=plan_id, depot_latitude=depot[0], depot_longitude=depot[1], routing_provider="OSRM", solver=optimized["solver"], total_distance_meters=optimized["total_distance_meters"], route_payload=json.dumps(response_payload)))
    db.commit()
    return {"route_plan_id": plan_id, **response_payload}

@app.post("/api/v1/routes/preview", dependencies=[Depends(require_operator)])
async def preview_route(payload: RouteRequest, db: Session = Depends(get_db)):
    bins = []
    for bin_id in payload.bin_ids:
        row = db.get(Bin, bin_id)
        if not row or not row.active:
            raise HTTPException(404, f"Unknown or inactive bin: {bin_id}")
        bins.append(row)
    total_demand = 0.0
    for row in bins:
        latest = db.scalar(select(Telemetry).where(Telemetry.bin_id == row.id).order_by(Telemetry.measured_at.desc()).limit(1))
        if latest is None:
            raise HTTPException(422, f"Missing telemetry for bin {row.id}; demand cannot be estimated")
        if _is_stale(latest.measured_at):
            raise HTTPException(422, f"Stale telemetry for bin {row.id}; route preview requires fresh readings")
        total_demand += row.capacity_liters * latest.fill_percent / 100
    if total_demand > payload.vehicle_capacity_liters:
        raise HTTPException(422, detail={"message": "Route exceeds vehicle capacity", "estimated_demand_liters": total_demand, "capacity_liters": payload.vehicle_capacity_liters})
    coords = [(payload.depot_latitude, payload.depot_longitude)] + [(b.latitude, b.longitude) for b in bins] + [(payload.depot_latitude, payload.depot_longitude)]
    try:
        route = await road_route(coords)
    except RoutingError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {"ordered_bin_ids": [b.id for b in bins], "estimated_demand_liters": total_demand, "capacity_liters": payload.vehicle_capacity_liters, "capacity_utilization": round(total_demand / payload.vehicle_capacity_liters, 4), "road_distance_meters": route["distance_meters"], "estimated_duration_seconds": route["duration_seconds"], "geometry": route["geometry"], "optimization": "road-route-preview; stop ordering supplied by caller, not optimized"}

@app.get("/api/v1/routes/plans", dependencies=[Depends(require_operator)])
def list_route_plans(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.scalars(select(RoutePlan).order_by(RoutePlan.created_at.desc()).limit(max(1, min(limit, 100))))
    return [{"id": row.id, "created_at": row.created_at, "total_distance_meters": row.total_distance_meters, "routing_provider": row.routing_provider, "solver": row.solver} for row in rows]

@app.get("/api/v1/routes/plans/{plan_id}", dependencies=[Depends(require_operator)])
def get_route_plan(plan_id: str, db: Session = Depends(get_db)):
    row = db.get(RoutePlan, plan_id)
    if not row:
        raise HTTPException(404, "Unknown route plan")
    return {"route_plan_id": row.id, **json.loads(row.route_payload), "created_at": row.created_at}
