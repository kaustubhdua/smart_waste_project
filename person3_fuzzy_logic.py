import numpy as np


def create_fuzzy_system():
    """Compatibility shim; the current priority engine is a heuristic, not fuzzy inference."""
    return None


def calculate_priority(fill_pct, hours_elapsed, criticality_str, fuzzy_sim=None):
    """Return a deterministic heuristic priority score in [0, 100].

    This is deliberately named/documented as a weighted heuristic. It does not
    implement fuzzy membership rules or a fuzzy inference engine.
    """
    fill_pct = float(fill_pct)
    hours_elapsed = float(hours_elapsed)
    if not np.isfinite(fill_pct) or not np.isfinite(hours_elapsed):
        raise ValueError("fill_pct and hours_elapsed must be finite")
    fill_pct = min(max(fill_pct, 0.0), 100.0)
    hours_elapsed = min(max(hours_elapsed, 0.0), 72.0)
    fill_weight = 1.0 / (1.0 + np.exp(-0.1 * (fill_pct - 65.0)))
    time_weight = min(hours_elapsed / 48.0, 1.0)
    crit_map = {"Low": 0.8, "Medium": 1.0, "High": 1.3}
    crit_mult = crit_map.get(criticality_str, 1.0)
    base_score = (fill_weight * 70.0) + (time_weight * 30.0)
    return round(float(np.clip(base_score * crit_mult, 0.0, 100.0)), 2)


if __name__ == "__main__":
    print("Deterministic heuristic priority engine")
    print(calculate_priority(88.5, 30, "High"))
    print(calculate_priority(20.0, 5, "Low"))
