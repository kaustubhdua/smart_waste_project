from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, ForeignKey, UniqueConstraint, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Bin(Base):
    __tablename__ = "bins"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    capacity_liters: Mapped[float] = mapped_column(Float)
    criticality: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(20), default="demo")
    last_emptied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (UniqueConstraint("device_id", "message_id", name="uq_device_message"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bin_id: Mapped[str] = mapped_column(ForeignKey("bins.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(100), index=True)
    message_id: Mapped[str] = mapped_column(String(150))
    fill_percent: Mapped[float] = mapped_column(Float)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(20), default="live")

class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    capacity_liters: Mapped[float] = mapped_column(Float)
    depot_latitude: Mapped[float] = mapped_column(Float)
    depot_longitude: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class CollectionJob(Base):
    __tablename__ = "collection_jobs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    bin_id: Mapped[str] = mapped_column(ForeignKey("bins.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="detected", index=True)
    demand_liters: Mapped[float] = mapped_column(Float)
    priority: Mapped[float] = mapped_column(Float, default=0)
    assigned_vehicle_id: Mapped[str | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    events: Mapped[list["ServiceEvent"]] = relationship(back_populates="job", cascade="all, delete-orphan")

class ServiceEvent(Base):
    __tablename__ = "service_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("collection_jobs.id"), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    previous_status: Mapped[str] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    job: Mapped[CollectionJob] = relationship(back_populates="events")

class RoutePlan(Base):
    __tablename__ = "route_plans"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    depot_latitude: Mapped[float] = mapped_column(Float)
    depot_longitude: Mapped[float] = mapped_column(Float)
    routing_provider: Mapped[str] = mapped_column(String(40))
    solver: Mapped[str] = mapped_column(String(120))
    total_distance_meters: Mapped[float] = mapped_column(Float)
    route_payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    bin_id: Mapped[str] = mapped_column(ForeignKey("bins.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Driver(Base):
    __tablename__ = "drivers"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
