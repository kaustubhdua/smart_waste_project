import asyncio

import pytest

import app.routing as routing
from app.routing import RoutingError


COORDINATES = [(28.6, 77.2), (28.61, 77.21)]


def run(coroutine):
    return asyncio.run(coroutine)


def test_road_matrix_returns_validated_distance_and_duration_matrices(monkeypatch):
    async def fake_get(path, params):
        assert path == "table/v1/driving/77.2,28.6;77.21,28.61"
        assert params == {"annotations": "distance,duration"}
        return {
            "code": "Ok",
            "distances": [[0, 120.5], [120.5, 0]],
            "durations": [[0, 35], [35, 0]],
        }

    monkeypatch.setattr(routing, "_get", fake_get)
    result = run(routing.road_matrix(COORDINATES))
    assert result["distances_meters"] == [[0, 120.5], [120.5, 0]]
    assert result["durations_seconds"] == [[0, 35], [35, 0]]


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
def test_road_matrix_rejects_incomplete_or_invalid_provider_data(
    monkeypatch, distances, durations
):
    async def fake_get(path, params):
        return {"code": "Ok", "distances": distances, "durations": durations}

    monkeypatch.setattr(routing, "_get", fake_get)
    with pytest.raises(RoutingError):
        run(routing.road_matrix(COORDINATES))


def test_get_rejects_non_object_provider_json(monkeypatch):
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
        run(routing._get("table/v1/driving/example", {}))


def test_road_route_rejects_invalid_metrics(monkeypatch):
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
        run(routing.road_route(COORDINATES))


def test_road_route_returns_only_validated_geojson(monkeypatch):
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
    result = run(routing.road_route(COORDINATES))
    assert result == {
        "distance_meters": 120.5,
        "duration_seconds": 35,
        "geometry": geometry,
    }


def test_road_route_rejects_out_of_range_geometry_coordinates(monkeypatch):
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
        run(routing.road_route(COORDINATES))


def test_road_route_rejects_boolean_geometry_coordinates(monkeypatch):
    async def fake_get(path, params):
        return {
            "code": "Ok",
            "routes": [{
                "distance": 120,
                "duration": 35,
                "geometry": {"type": "LineString", "coordinates": [[True, 28.6], [77.2, 28.7]]},
            }],
        }

    monkeypatch.setattr(routing, "_get", fake_get)
    with pytest.raises(RoutingError, match="invalid route coordinates"):
        run(routing.road_route(COORDINATES))


def test_ors_matrix_uses_validated_distance_and_duration_data(monkeypatch):
    monkeypatch.setattr(routing.settings, "routing_provider", "ors")
    monkeypatch.setattr(routing.settings, "ors_api_key", "test-key")

    async def fake_post(path, body):
        assert path == "matrix/driving-car"
        assert body == {
            "locations": [[77.2, 28.6], [77.21, 28.61]],
            "metrics": ["distance", "duration"],
            "units": "m",
        }
        return {"distances": [[0, 120.5], [120.5, 0]], "durations": [[0, 35], [35, 0]]}

    monkeypatch.setattr(routing, "_ors_post", fake_post)
    result = run(routing.road_matrix(COORDINATES))
    assert result["distances_meters"] == [[0, 120.5], [120.5, 0]]
    assert result["durations_seconds"] == [[0, 35], [35, 0]]


def test_ors_route_returns_validated_geojson(monkeypatch):
    monkeypatch.setattr(routing.settings, "routing_provider", "ors")
    monkeypatch.setattr(routing.settings, "ors_api_key", "test-key")
    geometry = {"type": "LineString", "coordinates": [[77.2, 28.6], [77.21, 28.61]]}

    async def fake_post(path, body):
        assert path == "directions/driving-car/geojson"
        assert body["coordinates"] == [[77.2, 28.6], [77.21, 28.61]]
        return {"features": [{
            "type": "Feature",
            "properties": {"summary": {"distance": 120.5, "duration": 35}},
            "geometry": geometry,
        }]}

    monkeypatch.setattr(routing, "_ors_post", fake_post)
    result = run(routing.road_route(COORDINATES))
    assert result == {"distance_meters": 120.5, "duration_seconds": 35, "geometry": geometry}


def test_ors_route_rejects_invalid_provider_geometry(monkeypatch):
    monkeypatch.setattr(routing.settings, "routing_provider", "ors")
    monkeypatch.setattr(routing.settings, "ors_api_key", "test-key")

    async def fake_post(path, body):
        return {"features": [{
            "properties": {"summary": {"distance": 120.5, "duration": 35}},
            "geometry": {"type": "LineString", "coordinates": [[181, 28.6], [77.21, 28.61]]},
        }]}

    monkeypatch.setattr(routing, "_ors_post", fake_post)
    with pytest.raises(RoutingError, match="invalid route coordinates"):
        run(routing.road_route(COORDINATES))
