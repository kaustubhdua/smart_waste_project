from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict, field_validator

class BinCreate(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    capacity_liters: float = Field(gt=0, le=100000)
    criticality: int = Field(default=1, ge=1, le=5)
    source: str = Field(default="demo", pattern="^(live|imported|demo)$")

class BinOut(BinCreate):
    model_config = ConfigDict(from_attributes=True)
    active: bool

class TelemetryIn(BaseModel):
    bin_id: str
    device_id: str = Field(min_length=1, max_length=100)
    message_id: str = Field(min_length=1, max_length=150)
    fill_percent: float = Field(ge=0, le=100)
    measured_at: datetime

    @field_validator("measured_at")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("measured_at must include a timezone, preferably UTC")
        return value.astimezone(timezone.utc)

class JobCreate(BaseModel):
    bin_id: str
    demand_liters: float | None = Field(default=None, gt=0)
    priority: float = Field(default=0, ge=0, le=100)

class TransitionIn(BaseModel):
    status: str = Field(pattern="^(approved|assigned|in_progress|completed|exception|verified)$")
    actor: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=1000)

class RouteRequest(BaseModel):
    depot_latitude: float = Field(ge=-90, le=90)
    depot_longitude: float = Field(ge=-180, le=180)
    bin_ids: list[str] = Field(min_length=1, max_length=50)
    vehicle_capacity_liters: float = Field(gt=0, le=100000)
    num_vehicles: int = Field(default=1, ge=1, le=20)

    @field_validator("bin_ids")
    @classmethod
    def unique_bins(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("bin_ids must not contain duplicates")
        return value

class VehicleCreate(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    capacity_liters: float = Field(gt=0, le=100000)
    depot_latitude: float = Field(ge=-90, le=90)
    depot_longitude: float = Field(ge=-180, le=180)

class JobAssign(BaseModel):
    vehicle_id: str = Field(min_length=1, max_length=80)
    actor: str = Field(min_length=1, max_length=100)

class DispatchRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1, max_length=50)
    vehicle_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)

    @field_validator("job_ids")
    @classmethod
    def unique_jobs(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("job_ids must not contain duplicates")
        return value

    @field_validator("vehicle_ids")
    @classmethod
    def unique_vehicles(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError("vehicle_ids must not contain duplicates")
        return value
