"""Validated adapter for the OSRM-compatible road routing service."""
from math import isfinite

import httpx

from .config import settings


class RoutingError(RuntimeError):
    """Raised when a routing provider cannot return trustworthy road data."""


async def _get(path: str, params: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{settings.osrm_base_url.rstrip('/')}/{path}", params=params
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RoutingError(
            "Road routing provider unavailable; route was not fabricated"
        ) from exc

    if not isinstance(payload, dict):
        raise RoutingError("Road routing provider returned an invalid response")
    if payload.get("code") != "Ok":
        raise RoutingError(
            f"Road routing provider returned {payload.get('code', 'an error')}"
        )
    return payload


def _coord_string(coordinates: list[tuple[float, float]]) -> str:
    return ";".join(f"{lon},{lat}" for lat, lon in coordinates)


def _valid_nonnegative_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and value >= 0
    )


def _valid_coordinate(value, maximum: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and -maximum <= value <= maximum
    )


def _validate_matrix(matrix, size: int, label: str) -> None:
    if not isinstance(matrix, list) or len(matrix) != size:
        raise RoutingError(f"Road routing provider returned an invalid {label} matrix")
    for row in matrix:
        if (
            not isinstance(row, list)
            or len(row) != size
            or any(not _valid_nonnegative_number(value) for value in row)
        ):
            raise RoutingError(
                f"Road routing provider returned an incomplete or invalid {label} matrix"
            )


async def road_matrix(coordinates: list[tuple[float, float]]) -> dict:
    """Return validated road distance/time matrices for (lat, lon) coordinates."""
    if len(coordinates) < 2:
        raise RoutingError("At least a depot and one stop are required")
    if settings.routing_provider.strip().lower() == "ors":
        return await _ors_matrix(coordinates)
    payload = await _get(
        f"table/v1/driving/{_coord_string(coordinates)}",
        {"annotations": "distance,duration"},
    )
    distances, durations = payload.get("distances"), payload.get("durations")
    _validate_matrix(distances, len(coordinates), "distance")
    _validate_matrix(durations, len(coordinates), "duration")
    return {"distances_meters": distances, "durations_seconds": durations}


async def road_route(coordinates: list[tuple[float, float]]) -> dict:
    """Get validated road-network distance, duration and GeoJSON geometry."""
    if len(coordinates) < 2:
        raise RoutingError("At least a depot and one stop are required")
    if settings.routing_provider.strip().lower() == "ors":
        return await _ors_route(coordinates)
    payload = await _get(
        f"route/v1/driving/{_coord_string(coordinates)}",
        {"overview": "full", "geometries": "geojson", "steps": "false"},
    )
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
        raise RoutingError("Road routing provider could not find a valid route")
    route = routes[0]
    distance, duration = route.get("distance"), route.get("duration")
    if not _valid_nonnegative_number(distance) or not _valid_nonnegative_number(duration):
        raise RoutingError("Road routing provider returned invalid route metrics")

    geometry = route.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise RoutingError("Road routing provider returned invalid route geometry")
    points = geometry.get("coordinates")
    if (
        not isinstance(points, list)
        or len(points) < 2
        or any(
            not isinstance(point, list)
            or len(point) < 2
            or not _valid_coordinate(point[0], 180)
            or not _valid_coordinate(point[1], 90)
            for point in points
        )
    ):
        raise RoutingError("Road routing provider returned invalid route coordinates")

    return {
        "distance_meters": distance,
        "duration_seconds": duration,
        "geometry": geometry,
    }


async def _ors_post(path: str, body: dict) -> dict:
    """Call authenticated openrouteservice v2 endpoints hosted by HeiGIT."""
    if not settings.ors_api_key.strip():
        raise RoutingError("Openrouteservice API key is not configured")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.ors_base_url.rstrip('/')}/{path}",
                json=body,
                headers={"Authorization": settings.ors_api_key, "Content-Type": "application/json", "Accept": "application/geo+json, application/json"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RoutingError("Openrouteservice is unavailable or rejected the request") from exc
    if not isinstance(payload, dict):
        raise RoutingError("Openrouteservice returned an invalid response")
    return payload


def _ors_check_error(payload: dict) -> None:
    error = payload.get("error") or payload.get("errors")
    if error:
        message = error.get("message", "provider rejected request") if isinstance(error, dict) else "provider rejected request"
        raise RoutingError(f"Openrouteservice: {str(message)[:240]}")


async def _ors_matrix(coordinates: list[tuple[float, float]]) -> dict:
    locations = [[lon, lat] for lat, lon in coordinates]
    payload = await _ors_post("matrix/driving-car", {"locations": locations, "metrics": ["distance", "duration"], "units": "m"})
    _ors_check_error(payload)
    distances, durations = payload.get("distances"), payload.get("durations")
    _validate_matrix(distances, len(coordinates), "distance")
    _validate_matrix(durations, len(coordinates), "duration")
    return {"distances_meters": distances, "durations_seconds": durations}


async def _ors_route(coordinates: list[tuple[float, float]]) -> dict:
    locations = [[lon, lat] for lat, lon in coordinates]
    payload = await _ors_post("directions/driving-car/geojson", {"coordinates": locations})
    _ors_check_error(payload)
    features = payload.get("features")
    if not isinstance(features, list) or not features or not isinstance(features[0], dict):
        raise RoutingError("Openrouteservice returned no route feature")
    feature = features[0]
    summary = (feature.get("properties") or {}).get("summary") or {}
    geometry = feature.get("geometry")
    distance, duration = summary.get("distance"), summary.get("duration")
    if not _valid_nonnegative_number(distance) or not _valid_nonnegative_number(duration):
        raise RoutingError("Openrouteservice returned invalid route metrics")
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise RoutingError("Openrouteservice returned invalid route geometry")
    points = geometry.get("coordinates")
    if not isinstance(points, list) or len(points) < 2 or any(
        not isinstance(point, list) or len(point) < 2 or
        not _valid_coordinate(point[0], 180) or not _valid_coordinate(point[1], 90)
        for point in points
    ):
        raise RoutingError("Openrouteservice returned invalid route coordinates")
    return {"distance_meters": distance, "duration_seconds": duration, "geometry": {"type": "LineString", "coordinates": [[point[0], point[1]] for point in points]}}


# --- Estimated-distance fallback (never used in production) -----------------
DETOUR_FACTOR = 1.35          # straight-line -> typical urban road distance
AVERAGE_SPEED_MPS = 30 / 3.6  # 30 km/h urban average


def fallback_allowed() -> bool:
    return bool(settings.routing_fallback) and settings.app_env.strip().lower() != "production"


def _haversine_meters(a: tuple[float, float], b: tuple[float, float]) -> float:
    from math import asin, cos, radians, sin, sqrt

    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * asin(sqrt(h))


def estimated_matrix(coordinates: list[tuple[float, float]]) -> dict:
    distances = [
        [0.0 if i == j else round(_haversine_meters(a, b) * DETOUR_FACTOR, 1) for j, b in enumerate(coordinates)]
        for i, a in enumerate(coordinates)
    ]
    durations = [[round(d / AVERAGE_SPEED_MPS, 1) for d in row] for row in distances]
    return {"distances_meters": distances, "durations_seconds": durations, "estimated": True}


def estimated_route(coordinates: list[tuple[float, float]]) -> dict:
    distance = sum(
        _haversine_meters(coordinates[i], coordinates[i + 1]) * DETOUR_FACTOR
        for i in range(len(coordinates) - 1)
    )
    return {
        "distance_meters": round(distance, 1),
        "duration_seconds": round(distance / AVERAGE_SPEED_MPS, 1),
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in coordinates]},
        "estimated": True,
    }


async def resilient_matrix(coordinates: list[tuple[float, float]]) -> dict:
    """Road matrix; falls back to a labelled estimate outside production."""
    try:
        return await road_matrix(coordinates)
    except RoutingError:
        if not fallback_allowed() or len(coordinates) < 2:
            raise
        return estimated_matrix(coordinates)


async def resilient_route(coordinates: list[tuple[float, float]]) -> dict:
    """Road route geometry; falls back to a labelled estimate outside production."""
    try:
        return await road_route(coordinates)
    except RoutingError:
        if not fallback_allowed() or len(coordinates) < 2:
            raise
        return estimated_route(coordinates)
