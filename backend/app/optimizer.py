from ortools.constraint_solver import pywrapcp, routing_enums_pb2

class OptimizationError(RuntimeError):
    pass

def optimize_cvrp(distance_matrix_m: list[list[float]], demands_liters: list[float], vehicle_capacities_liters: list[float], depot: int = 0) -> dict:
    """Solve CVRP using a real road-distance matrix; index 0 is the depot."""
    n = len(distance_matrix_m)
    if n < 2 or len(demands_liters) != n:
        raise ValueError("Matrix and demand dimensions must match and include a depot plus a stop")
    if not vehicle_capacities_liters or any(c <= 0 for c in vehicle_capacities_liters):
        raise ValueError("At least one vehicle with positive capacity is required")
    if any(len(row) != n for row in distance_matrix_m):
        raise ValueError("Distance matrix must be square")
    if any(d < 0 for d in demands_liters) or demands_liters[depot] != 0:
        raise ValueError("Demands must be non-negative and depot demand must be zero")
    # OR-Tools integer callbacks: convert meters to rounded integer meters and
    # liters to milliliters to preserve practical precision for small bins.
    matrix = [[int(round(v)) for v in row] for row in distance_matrix_m]
    demands = [int(round(v * 1000)) for v in demands_liters]
    capacities = [int(round(v * 1000)) for v in vehicle_capacities_liters]
    if any(demands[i] > max(capacities) for i in range(n) if i != depot):
        raise OptimizationError("A stop demand exceeds every vehicle's capacity")
    manager = pywrapcp.RoutingIndexManager(n, len(capacities), depot)
    routing = pywrapcp.RoutingModel(manager)
    def distance(from_index, to_index):
        return matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]
    distance_index = routing.RegisterTransitCallback(distance)
    routing.SetArcCostEvaluatorOfAllVehicles(distance_index)
    def demand(from_index):
        return demands[manager.IndexToNode(from_index)]
    demand_index = routing.RegisterUnaryTransitCallback(demand)
    routing.AddDimensionWithVehicleCapacity(demand_index, 0, capacities, True, "Capacity")
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromSeconds(3)
    solution = routing.SolveWithParameters(params)
    if solution is None:
        raise OptimizationError("No feasible solution found; check vehicle capacity and stop demands")
    routes, total_distance = [], 0
    for vehicle_id in range(len(capacities)):
        index = routing.Start(vehicle_id)
        nodes, load, distance_m = [], 0.0, 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != depot:
                nodes.append(node)
                load += demands_liters[node]
            next_index = solution.Value(routing.NextVar(index))
            distance_m += matrix[node][manager.IndexToNode(next_index)]
            index = next_index
        total_distance += distance_m
        routes.append({"vehicle_index": vehicle_id, "stop_indices": nodes, "load_liters": round(load, 3), "capacity_liters": vehicle_capacities_liters[vehicle_id], "capacity_utilization": round(load / vehicle_capacities_liters[vehicle_id], 4), "distance_meters": distance_m})
    return {"routes": routes, "total_distance_meters": total_distance, "solver": "OR-Tools CVRP with road-distance matrix"}
