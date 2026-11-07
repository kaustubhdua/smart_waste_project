"""Public compatibility API for the shared Sugeno fuzzy priority engine."""
from backend.app.priority import (
    FuzzyPrioritySystem,
    calculate_priority as _calculate_priority,
)


def create_fuzzy_system():
    """Create a reusable fuzzy priority inference system."""
    return FuzzyPrioritySystem()


def calculate_priority(fill_pct, hours_elapsed, criticality_str, fuzzy_sim=None):
    """Calculate collection urgency with the shared fuzzy inference engine."""
    return _calculate_priority(
        fill_pct, hours_elapsed, criticality_str, fuzzy_system=fuzzy_sim
    )


if __name__ == "__main__":
    system = create_fuzzy_system()
    print("Zero-order Sugeno fuzzy priority engine")
    print(calculate_priority(88.5, 30, "High", system))
    print(calculate_priority(20.0, 5, "Low", system))
