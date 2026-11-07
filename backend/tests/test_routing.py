import pytest

import app.routing as routing
from app.routing import RoutingError


COORDINATES = [(28.6, 77.2), (28.61, 77.21)]


@pytest.mark.asyncio
async def test_road_matrix_returns_validated_distance_and_duration_matrices(monkeypatch):
    async def fake_get(path, params):
        assert path == "table/v1/driving/77.2,28.6;77.21,28.61"
        assert params == {"annotations": "distance,duration"}
        return {
            "code": "Ok",
            "distances": [[0, 120.5], [120.5, 0]],
            "durations": [[0, 35], [35, 0]],
        }

    monkeypatch.setattr(routing, "_get", fake_get)
    result = await routing.road_matrix(COORDINATES)
    assert result["distances_meters"] == [[0, 120.5], [120.5, 0]]
    assert result["durations_seconds"] == [[0, 35], [35, 0]]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "distances,durations",
    [
        ([[0, 1]], [[0, 1], [1, 0]]),
        ([[0, None], [1, 0]], [[0, 1], [1, 0]]),
        ([[0, float("nan")], [1, 0]], [[0, 1], [1, 0]]),
        ([[0, -1], [1, 0]], [[0, 1], [1, 0]]),
        ([[0, 1], [1, 0]], [[0, 1]]),
    ],
)
async def test_road_matrix_rejects_incomplete_or_invalid_provider_data(
    monkeypatch, distances, durations
):
    async def fake_get(path, params):
        return {"code": "Ok", "distances": distances, "durations": durations}

    monkeypatch.setattr(routing, "_get", fake_get)
    with pytest.raises(RoutingError):
        await routing.road_matrix(COORDINATES)


@pytest.mark.asyncio
async def test_get_rejects_non_object_provider_json(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return ["not", "an", "object"]

    class Client:
        def __init__(self, timeout):
            assert timeout == 20

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, params):
            return Response()

    monkeypatch.setattr(routing.httpx, "AsyncClient", Client)
    with pytest.raises(RoutingError, match="invalid response"):
        await routing._get("table/v1/driving/example", {})


@pytest.mark.asyncio
async def test_road_route_rejects_invalid_metrics_and_geometry(monkeypatch):
    async def fake_get(path, params):
        return {
            "code": "Ok",
            "routes": [{
                "distance": float("inf"),
                "duration": 30,
                "geometry": {"type": "LineString", "coordinates": [[77.2, 28.6], [77.3, 28.7]]},
            }],
        }

    monkeypatch.setattr(routing, "_get", fake_get)
    with pytest.raises(RoutingError, match="invalid route metrics"):
        await routing.road_route(COORDINATES)


@pytest.mark.asyncio
async def test_road_route_returns_only_validated_geojson(monkeypatch):
    geometry = {
        "type": "LineString",
        "coordinates": [[77.2, 28.6], [77.21, 28.61]],
    }

    async def fake_get(path, params):
        return {
            "code": "Ok",
            "routes": [{"distance": 120.5, "duration": 35, "geometry": geometry}],
        }

    monkeypatch.setattr(routing, "_get", fake_get)
    result = await routing.road_route(COORDINATES)
    assert result == {
        "distance_meters": 120.5,
        "duration_seconds": 35,
        "geometry": geometry,
    }


@pytest.mark.asyncio
async def test_road_route_rejects_out_of_range_geometry_coordinates(monkeypatch):
    async def fake_get(path, params):
        return {
            "code": "Ok",
            "routes": [{
                "distance": 120,
                "duration": 35,
                "geometry": {"type": "LineString", "coordinates": [[200, 28.6], [77.2, 28.7]]},
            }],
        }

    monkeypatch.setattr(routing, "_get", fake_get)
    with pytest.raises(RoutingError, match="invalid route coordinates"):
        await routing.road_route(COORDINATES)
