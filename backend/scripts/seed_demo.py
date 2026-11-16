"""Idempotently seed a complete, explicitly labeled training scenario.

The seed is opt-in, prohibited in production, and creates generated records only.
Driver credentials are random, hashed at rest, and printed once at creation.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import Bin, CollectionJob, Driver, ServiceEvent, Telemetry, Vehicle
from app.priority import calculate_priority


def seed():
    if settings.app_env.strip().lower() == "production" or not settings.seed_demo_data:
        raise RuntimeError(
            "Training seeding is disabled by default; set SEED_DEMO_DATA=true "
            "in a non-production environment to opt in."
        )

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    new_driver_credentials = []
    try:
        depot_lat, depot_lon = 28.5355, 77.3910
        bins = []
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

        # A varied service area gives the map, priority queue and optimizer
        # enough records to demonstrate realistic multi-vehicle workflows.
        for index in range(1, 17):
            bin_id = f"DEMO-BIN-{index:02d}"
            row = db.get(Bin, bin_id)
            if row is None:
                row = Bin(
                    id=bin_id,
                    latitude=depot_lat + (((index - 1) % 4) - 1.5) * 0.0065,
                    longitude=depot_lon + (((index - 1) // 4) - 1.5) * 0.0075,
                    capacity_liters=[500, 750, 1000, 1200][index % 4],
                    criticality=1 + (index % 5),
                    source="demo",
                )
                db.add(row)
            bins.append(row)

        vehicle_specs = (
            ("DEMO-TRUCK-01", 1800),
            ("DEMO-TRUCK-02", 2200),
            ("DEMO-TRUCK-03", 1600),
            ("DEMO-TRUCK-04", 2000),
        )
        for vehicle_id, capacity in vehicle_specs:
            if db.get(Vehicle, vehicle_id) is None:
                db.add(Vehicle(
                    id=vehicle_id,
                    capacity_liters=capacity,
                    depot_latitude=depot_lat,
                    depot_longitude=depot_lon,
                    active=True,
                    available=True,
                ))
        db.flush()

        # Six hourly observations per bin exercise history, freshness and
        # optional next-observation model paths without claiming field data.
        latest_fill = {}
        for index, bin_row in enumerate(bins):
            for offset in range(6):
                message_id = f"training-{bin_row.id}-{offset}"
                existing = db.query(Telemetry).filter_by(
                    device_id="training-generator",
                    message_id=message_id,
                ).first()
                fill = min(96.0, 18.0 + index * 4.1 + offset * (4.0 + index % 3))
                if offset == 5:
                    latest_fill[bin_row.id] = round(fill, 1)
                if existing:
                    continue
                db.add(Telemetry(
                    bin_id=bin_row.id,
                    device_id="training-generator",
                    message_id=message_id,
                    fill_percent=round(fill, 1),
                    temperature_c=round(24.0 + index * 0.45, 1),
                    measured_at=now - timedelta(hours=5 - offset),
                    source="demo",
                ))
        db.flush()

        # Four driver identities make the separate driver workspace usable.
        # Tokens are only shown once, at creation, and only their hashes persist.
        for index, (vehicle_id, _) in enumerate(vehicle_specs, start=1):
            driver_id = f"DEMO-DRIVER-{index:02d}"
            if db.get(Driver, driver_id) is None:
                raw_token = token_urlsafe(32)
                db.add(Driver(
                    id=driver_id,
                    vehicle_id=vehicle_id,
                    token_hash=sha256(raw_token.encode("utf-8")).hexdigest(),
                    active=True,
                ))
                new_driver_credentials.append((driver_id, raw_token))

        # Seed two assigned stops for the driver workflow and additional
        # detected jobs for operator approval and dispatch practice.
        assigned_bins = {"DEMO-BIN-06": "DEMO-TRUCK-01", "DEMO-BIN-08": "DEMO-TRUCK-02"}
        for bin_row in bins:
            fill = latest_fill[bin_row.id]
            if fill < 65:
                continue
            existing_job = db.query(CollectionJob).filter(
                CollectionJob.bin_id == bin_row.id,
                CollectionJob.status != "verified",
            ).first()
            if existing_job:
                continue

            vehicle_id = assigned_bins.get(bin_row.id)
            demand = round(bin_row.capacity_liters * fill / 100, 1)
            priority = calculate_priority(fill, 5.0, bin_row.criticality)
            job = CollectionJob(
                id=f"TRAIN-{bin_row.id}",
                bin_id=bin_row.id,
                status="assigned" if vehicle_id else "detected",
                demand_liters=demand,
                priority=priority,
                assigned_vehicle_id=vehicle_id,
                created_at=now - timedelta(minutes=20 + len(bins)),
            )
            db.add(job)
            db.flush()
            db.add(ServiceEvent(
                job_id=job.id,
                actor="training-seed",
                previous_status="none",
                new_status=job.status,
                note="Preloaded training scenario",
                created_at=now - timedelta(minutes=20),
            ))
            if vehicle_id:
                vehicle = db.get(Vehicle, vehicle_id)
                if vehicle:
                    vehicle.available = False

        db.commit()
        print(
            f"Training workspace ready: {len(bins)} collection points, "
            f"{len(vehicle_specs)} vehicles, {len(bins) * 6} telemetry observations, "
            "driver accounts and collection workflow records."
        )
        for driver_id, raw_token in new_driver_credentials:
            print(f"ONE-TIME TRAINING DRIVER CREDENTIAL | {driver_id} | {raw_token}")
        if not new_driver_credentials:
            print("Training driver credentials already exist; existing tokens were not rotated.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
