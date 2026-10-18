import httpx
from .config import settings

class RoutingError(RuntimeError):
    pass

async def road_route(coordinates: list[tuple[float, float]]) -> dict:
    """Get real road-network distance, duration and geometry from OSRM.
    Coordinates are (latitude, longitude); OSRM expects longitude,latitude.
    No straight-line fallback is permitted because it would misrepresent road travel.
    """
    if len(coordinates) < 2:
        raise RoutingError("At least a depot and one stop are required")
    path = ";".join(f"{lon},{lat}" for lat, lon in coordinates)
    url = f"{settings.osrm_base_url.rstrip('/')}/route/v1/driving/{path}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params={"overview": "full", "geometries": "geojson", "steps": "false"})
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RoutingError("Road routing provider unavailable; route was not fabricated") from exc
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RoutingError("Road routing provider could not find a valid route")
    route = payload["routes"][0]
    return {"distance_meters": route["distance"], "duration_seconds": route["duration"], "geometry": route.get("geometry")}
