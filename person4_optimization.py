import numpy as np
from ortools.constraint_solver import routing_enums_pb2, pywrapcp


def create_distance_matrix(locations):
    """Calculates pairwise Euclidean distances between bin coordinates."""
    num_locs = len(locations)
    dist_matrix = np.zeros((num_locs, num_locs))
    for i in range(num_locs):
        for j in range(num_locs):
            if i != j:
                # Scaled distance to simulate city block distances
                dist_matrix[i][j] = (
                    np.linalg.norm(
                        np.array(locations[i]) - np.array(locations[j])
                    )
                    * 100000
                )
    return dist_matrix.astype(int).tolist()


def solve_vrp(bins_data, num_vehicles=2, vehicle_capacity=1000):
    """Solves the Capacitated Vehicle Routing Problem (CVRP) using Google OR-Tools.

    :param bins_data: List of dicts containing 'latitude', 'longitude', and
    'waste_volume'
    :param num_vehicles: Number of available collection trucks
    :param vehicle_capacity: Capacity limit per truck
    :return: Dict containing routes and total distance
    """
    if not isinstance(bins_data, list):
        raise TypeError("bins_data must be a list")
    if not isinstance(num_vehicles, int) or isinstance(num_vehicles, bool) or num_vehicles < 1:
        raise ValueError("num_vehicles must be a positive integer")
    if isinstance(vehicle_capacity, (list, tuple)):
        if len(vehicle_capacity) != num_vehicles:
            raise ValueError("vehicle_capacity list must match num_vehicles")
        if any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not np.isfinite(value)
            or value <= 0
            for value in vehicle_capacity
        ):
            raise ValueError("every vehicle capacity must be a positive finite number")
        vehicle_capacities = list(vehicle_capacity)
    else:
        if not isinstance(vehicle_capacity, (int, float)) or isinstance(vehicle_capacity, bool) or not np.isfinite(vehicle_capacity) or vehicle_capacity <= 0:
            raise ValueError("vehicle_capacity must be a positive finite number or a per-vehicle list")
        vehicle_capacities = [vehicle_capacity] * num_vehicles
    if not bins_data:
        return {}

    for index, bin_record in enumerate(bins_data):
        if not isinstance(bin_record, dict):
            raise TypeError(f"bin record {index} must be a dictionary")
        for key, low, high in (("latitude", -90, 90), ("longitude", -180, 180)):
            value = bin_record.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not np.isfinite(value) or not low <= value <= high:
                raise ValueError(f"bin record {index} has invalid {key}")
        demand = bin_record.get("waste_volume", 50)
        if not isinstance(demand, (int, float)) or isinstance(demand, bool) or not np.isfinite(demand) or demand < 0:
            raise ValueError(f"bin record {index} has invalid waste_volume")
        if demand > vehicle_capacity:
            raise ValueError(f"bin record {index} exceeds vehicle capacity")

    # Depot is assumed at index 0 (city center/waste hub)
    depot_location = [28.5355, 77.3910]
    locations = [depot_location] + [
        [b["latitude"], b["longitude"]] for b in bins_data
    ]

    # Demands in liters (0 for depot)
    demands = [0] + [int(b.get("waste_volume", 50)) for b in bins_data]

    distance_matrix = create_distance_matrix(locations)

    # Setup OR-Tools Data Model
    data = {
        "distance_matrix": distance_matrix,
        "demands": demands,
        "vehicle_capacities": vehicle_capacities,
        "num_vehicles": num_vehicles,
        "depot": 0,
    }

    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]), data["num_vehicles"], data["depot"]
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        data["vehicle_capacities"],  # vehicle maximum capacities
        True,  # start capacity at zero
        "Capacity",
    )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    solution = routing.SolveWithParameters(search_parameters)

    routes = {}
    if solution:
        for vehicle_id in range(data["num_vehicles"]):
            index = routing.Start(vehicle_id)
            route = []
            route_load = 0
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_load += data["demands"][node_index]
                if node_index != 0:  # Exclude depot from bin list
                    route.append(node_index - 1)  # Adjust back to bin index
                index = solution.Value(routing.NextVar(index))
            routes[f"Vehicle_{vehicle_id + 1}"] = {
                "route_bin_indices": route,
                "total_load": route_load,
            }
    if solution is None:
        raise RuntimeError("No feasible collection routes found for the supplied bins and capacity")
    return routes


if __name__ == "__main__":
    print("Testing Route Optimization Module...")
    # Sample bins needing pickup
    sample_bins = [
        {"latitude": 28.5410, "longitude": 77.3950, "waste_volume": 180},
        {"latitude": 28.5290, "longitude": 77.3880, "waste_volume": 400},
        {"latitude": 28.5500, "longitude": 77.4010, "waste_volume": 250},
        {"latitude": 28.5210, "longitude": 77.3750, "waste_volume": 320},
    ]

    optimized_routes = solve_vrp(
        sample_bins, num_vehicles=2, vehicle_capacity=600
    )
    for vehicle, info in optimized_routes.items():
        print(
            f"🚛 {vehicle}: Bins to visit {info['route_bin_indices']} | Total Load: {info['total_load']} L"
        )