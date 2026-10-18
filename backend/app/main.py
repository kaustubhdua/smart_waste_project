from datetime import datetime, timezone
import json
from hmac import compare_digest
from uuid import uuid4
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .config import settings
from .db import Base, engine, get_db
from .models import Bin, Telemetry, CollectionJob, ServiceEvent, RoutePlan, Vehicle
from .schemas import BinCreate, BinOut, TelemetryIn, JobCreate, TransitionIn, RouteRequest, VehicleCreate, JobAssign
from .routing import road_route, road_matrix, RoutingError
from .optimizer import optimize_cvrp, OptimizationError

app = FastAPI(title="Smart Waste Operations API", version="1.1.0", description="Persistent bin telemetry, collection jobs and road-network routing.")
if settings.auto_create_schema:
    Base.metadata.create_all(bind=engine)
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.cors_origins.split(',') if origin.strip()], allow_credentials=False, allow_methods=['GET', 'POST', 'OPTIONS'], allow_headers=['Authorization', 'Content-Type', 'X-Device-Token'])

def require_operator(authorization: str | None = Header(default=None)):
    expected = "Bearer " + settings.api_token
    if not authorization or not compare_digest(authorization, expected) or settings.api_token.startswith("change-me"):
        raise HTTPException(status_code=401, detail="Valid configured operator bearer token required")

def require_device(x_device_token: str | None = Header(default=None)):
    if not x_device_token or not compare_digest(x_device_token, settings.device_token) or settings.device_token.startswith("change-me"):
        raise HTTPException(status_code=401, detail="Valid configured device token required")

@app.get("/health")
def health():
    return {"status": "ok", "service": "smart-waste-api"}

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

@app.post("/api/v1/telemetry", dependencies=[Depends(require_device)], status_code=202)
def ingest_telemetry(payload: TelemetryIn, db: Session = Depends(get_db)):
    if not db.get(Bin, payload.bin_id):
        raise HTTPException(404, "Unknown bin")
    row = Telemetry(**payload.model_dump(), source="live")
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Telemetry).where(Telemetry.device_id == payload.device_id, Telemetry.message_id == payload.message_id))
        if existing:
            return {"accepted": True, "duplicate": True, "telemetry_id": existing.id}
        raise HTTPException(409, "Telemetry could not be stored")
    db.refresh(row)
    return {"accepted": True, "duplicate": False, "telemetry_id": row.id}

@app.get("/api/v1/bins/{bin_id}/history", dependencies=[Depends(require_operator)])
def bin_history(bin_id: str, limit: int = 100, db: Session = Depends(get_db)):
    if not db.get(Bin, bin_id):
        raise HTTPException(404, "Unknown bin")
    rows = db.scalars(select(Telemetry).where(Telemetry.bin_id == bin_id).order_by(Telemetry.measured_at.desc()).limit(max(1, min(limit, 500))))
    return [{"id": r.id, "fill_percent": r.fill_percent, "measured_at": r.measured_at, "received_at": r.received_at, "source": r.source} for r in rows]

@app.post("/api/v1/jobs", dependencies=[Depends(require_operator)], status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    bin_row = db.get(Bin, payload.bin_id)
    if not bin_row:
        raise HTTPException(404, "Unknown bin")
    latest = db.scalar(select(Telemetry).where(Telemetry.bin_id == payload.bin_id).order_by(Telemetry.measured_at.desc()).limit(1))
    demand = payload.demand_liters
    if demand is None:
        if latest is None:
            raise HTTPException(422, "Demand is required when no telemetry exists")
        demand = bin_row.capacity_liters * latest.fill_percent / 100
    job = CollectionJob(id=str(uuid4()), bin_id=payload.bin_id, demand_liters=demand, priority=payload.priority)
    db.add(job)
    db.add(ServiceEvent(job_id=job.id, actor="system", previous_status="none", new_status="detected", note="Collection candidate created"))
    db.commit()
    return {"id": job.id, "bin_id": job.bin_id, "status": job.status, "demand_liters": job.demand_liters, "priority": job.priority}

ALLOWED = {
    "detected": {"approved", "exception"},
    "approved": {"assigned", "exception"},
    "assigned": {"in_progress", "approved", "exception"},
    "in_progress": {"completed", "exception"},
    "completed": {"verified"},
    "exception": {"approved"},
    "verified": set(),
}


@app.post("/api/v1/vehicles", dependencies=[Depends(require_operator)], status_code=201)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db)):
    if db.get(Vehicle, payload.id):
        raise HTTPException(409, "Vehicle already exists")
    vehicle = Vehicle(**payload.model_dump())
    db.add(vehicle)
    db.commit()
    return {"id": vehicle.id, "capacity_liters": vehicle.capacity_liters, "active": vehicle.active}

@app.get("/api/v1/vehicles", dependencies=[Depends(require_operator)])
def list_vehicles(db: Session = Depends(get_db)):
    rows = db.scalars(select(Vehicle).order_by(Vehicle.id))
    return [{"id": v.id, "capacity_liters": v.capacity_liters, "active": v.active, "depot_latitude": v.depot_latitude, "depot_longitude": v.depot_longitude} for v in rows]

@app.post("/api/v1/jobs/{job_id}/assign", dependencies=[Depends(require_operator)])
def assign_job(job_id: str, payload: JobAssign, db: Session = Depends(get_db)):
    job = db.scalar(select(CollectionJob).where(CollectionJob.id == job_id).with_for_update())
    vehicle = db.scalar(select(Vehicle).where(Vehicle.id == payload.vehicle_id).with_for_update())
    if not job:
        raise HTTPException(404, "Unknown job")
    if not vehicle or not vehicle.active:
        raise HTTPException(404, "Unknown or inactive vehicle")
    if job.status not in {"detected", "approved", "exception"}:
        raise HTTPException(409, f"Job cannot be assigned from status {job.status}")
    if job.demand_liters > vehicle.capacity_liters:
        raise HTTPException(422, "Job demand exceeds vehicle capacity")
    previous = job.status
    job.status = "assigned"
    job.assigned_vehicle_id = vehicle.id
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
    job.status = payload.status
    if payload.status == "verified":
        bin_row = db.get(Bin, job.bin_id)
        if bin_row:
            bin_row.last_emptied_at = datetime.now(timezone.utc)
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
