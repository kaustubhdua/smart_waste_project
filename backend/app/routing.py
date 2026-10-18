import httpx
from .config import settings

class RoutingError(RuntimeError):
    pass

async def _get(path: str, params: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f"{settings.osrm_base_url.rstrip('/')}/{path}", params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RoutingError("Road routing provider unavailable; route was not fabricated") from exc
    if payload.get("code") != "Ok":
        raise RoutingError(f"Road routing provider returned {payload.get('code', 'an error')}")
    return payload

def _coord_string(coordinates: list[tuple[float, float]]) -> str:
    return ";".join(f"{lon},{lat}" for lat, lon in coordinates)

async def road_matrix(coordinates: list[tuple[float, float]]) -> dict:
    """Road-network matrix; coordinates are (lat, lon), OSRM expects lon,lat."""
    if len(coordinates) < 2:
        raise RoutingError("At least a depot and one stop are required")
    payload = await _get(f"table/v1/driving/{_coord_string(coordinates)}", {"annotations": "distance,duration"})
    distances, durations = payload.get("distances"), payload.get("durations")
    if not distances or not durations or any(v is None for row in distances for v in row) or any(v is None for row in durations for v in row):
        raise RoutingError("Road network matrix is incomplete for one or more stops")
    return {"distances_meters": distances, "durations_seconds": durations}

async def road_route(coordinates: list[tuple[float, float]]) -> dict:
    """Get real road-network distance, duration and geometry from OSRM."""
    if len(coordinates) < 2:
        raise RoutingError("At least a depot and one stop are required")
    payload = await _get(f"route/v1/driving/{_coord_string(coordinates)}", {"overview": "full", "geometries": "geojson", "steps": "false"})
    if not payload.get("routes"):
        raise RoutingError("Road routing provider could not find a valid route")
    route = payload["routes"][0]
    return {"distance_meters": route["distance"], "duration_seconds": route["duration"], "geometry": route.get("geometry")}
