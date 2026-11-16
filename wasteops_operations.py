"""Pure state transitions for the standalone WasteOps training workspace."""
from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(radians, a)
    lat2, lon2 = map(radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


def record_telemetry(data: dict, row: dict, stamp: datetime) -> None:
    data.setdefault("telemetry_history", []).append({
        "bin_id": row["id"],
        "time": stamp.isoformat(timespec="minutes"),
        "fill_pct": round(float(row["fill_pct"]), 1),
        "battery_pct": int(row["battery_pct"]),
        "temperature_c": round(float(row.get("temperature_c", 25.0)), 1),
    })
    data["telemetry_history"] = data["telemetry_history"][-3000:]


def route_distance_for_bins(bin_ids: list[str], bins: list[dict], depot: tuple[float, float]) -> float:
    by_id = {row["id"]: row for row in bins}
    points = [depot] + [
        (by_id[bin_id]["latitude"], by_id[bin_id]["longitude"])
        for bin_id in bin_ids
    ] + [depot]
    return sum(distance_km(points[i], points[i + 1]) for i in range(len(points) - 1))


def complete_collection(
    data: dict,
    bins: list[dict],
    vehicles: list[dict],
    jobs: list[dict],
    job: dict,
    stamp: datetime,
    depot: tuple[float, float],
) -> None:
    """Record one completion, update telemetry/analytics, and reconcile fleet state."""
    row = next((item for item in bins if item["id"] == job["bin_id"]), None)
    if row is None:
        raise ValueError("The collection point for this job no longer exists.")

    row["fill_pct"] = 0.0
    row["last_collected"] = stamp.isoformat(timespec="minutes")
    row["status"] = "Normal"
    record_telemetry(data, row, stamp)

    history = data.setdefault("history", [])
    time_label = stamp.strftime("%H:%M")
    if history and history[-1].get("time") == time_label:
        history[-1]["collected"] = int(history[-1].get("collected", 0)) + 1
    else:
        history.append({"time": time_label, "collected": 1, "requests": 0})
    data["history"] = history[-24:]

    vehicle_id = job.get("vehicle", "Unassigned")
    routes = data.setdefault("routes", {})
    route = routes.get(vehicle_id)
    if route:
        route["bins"] = [bin_id for bin_id in route.get("bins", []) if bin_id != row["id"]]
        if route["bins"]:
            by_id = {item["id"]: item for item in bins}
            route["load_l"] = sum(
                int(round(by_id[bin_id]["capacity_l"] * by_id[bin_id]["fill_pct"] / 100))
                for bin_id in route["bins"]
            )
            route["distance_km"] = route_distance_for_bins(route["bins"], bins, depot)
        else:
            routes.pop(vehicle_id, None)

    vehicle = next((item for item in vehicles if item["id"] == vehicle_id), None)
    still_active = any(
        item is not job
        and item["vehicle"] == vehicle_id
        and item["status"] in ("Assigned", "In progress")
        for item in jobs
    )
    if vehicle and not still_active:
        vehicle["available"] = True
        vehicle["route_progress_pct"] = 0.0
        vehicle["latitude"], vehicle["longitude"] = depot
        routes.pop(vehicle_id, None)
    data["route_order"] = list(routes)
