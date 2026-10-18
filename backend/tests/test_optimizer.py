import pytest
from app.optimizer import optimize_cvrp, OptimizationError

def test_optimizer_respects_capacity_and_visits_each_stop():
    matrix = [[0, 100, 200], [100, 0, 120], [200, 120, 0]]
    result = optimize_cvrp(matrix, [0, 20, 30], [60])
    visited = [i for route in result["routes"] for i in route["stop_indices"]]
    assert sorted(visited) == [1, 2]
    assert result["routes"][0]["load_liters"] == 50

def test_demand_above_every_vehicle_is_rejected():
    with pytest.raises(OptimizationError):
        optimize_cvrp([[0, 1], [1, 0]], [0, 100], [50])

def test_invalid_matrix_rejected():
    with pytest.raises(ValueError):
        optimize_cvrp([[0, 1], [1]], [0, 1], [10])
