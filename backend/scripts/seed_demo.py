"""Idempotently seed explicitly labeled demo data for local development."""
from datetime import datetime, timedelta, timezone
from app.db import Base, SessionLocal, engine
from app.models import Bin, Telemetry, Vehicle

def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        depot_lat, depot_lon = 28.5355, 77.3910
        bins = []
        for index in range(1, 9):
            bin_id = f"DEMO-BIN-{index:02d}"
            row = db.get(Bin, bin_id)
            if row is None:
                row = Bin(
                    id=bin_id,
                    latitude=depot_lat + ((index % 4) - 1.5) * 0.006,
                    longitude=depot_lon + ((index // 4) - 0.5) * 0.008,
                    capacity_liters=[500, 750, 1000][index % 3],
                    criticality=1 + (index % 5),
                    source="demo",
                )
                db.add(row)
            bins.append(row)
        for vehicle_id, capacity in (("DEMO-TRUCK-01", 1800), ("DEMO-TRUCK-02", 2200)):
            if db.get(Vehicle, vehicle_id) is None:
                db.add(Vehicle(id=vehicle_id, capacity_liters=capacity, depot_latitude=depot_lat, depot_longitude=depot_lon, active=True))
        db.flush()
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        for index, bin_row in enumerate(bins):
            for offset in range(6):
                message_id = f"seed-{bin_row.id}-{offset}"
                existing = db.query(Telemetry).filter_by(device_id="demo-generator", message_id=message_id).first()
                if existing:
                    continue
                fill = min(96.0, 22.0 + index * 4.5 + offset * (5.0 + index % 3))
                db.add(Telemetry(
                    bin_id=bin_row.id,
                    device_id="demo-generator",
                    message_id=message_id,
                    fill_percent=round(fill, 1),
                    temperature_c=round(24.0 + index * 0.7, 1),
                    measured_at=now - timedelta(hours=5 - offset),
                    source="demo",
                ))
        db.commit()
        print(f"Demo seed ready: {len(bins)} labeled demo bins and 2 demo vehicles.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
