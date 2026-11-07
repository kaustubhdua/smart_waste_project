"""Zero-order Sugeno fuzzy inference for collection urgency."""
from itertools import product
from math import isfinite


_FILL_SETS = {
    "low": (0.0, 0.0, 30.0, 55.0),
    "medium": (30.0, 45.0, 65.0, 80.0),
    "high": (65.0, 85.0, 100.0, 100.0),
}
_TIME_SETS = {
    "recent": (0.0, 0.0, 8.0, 24.0),
    "aging": (12.0, 24.0, 48.0, 60.0),
    "overdue": (48.0, 60.0, 72.0, 72.0),
}
_CRITICALITY_SETS = {
    "low": (1.0, 1.0, 2.0, 3.0),
    "medium": (2.0, 3.0, 3.0, 4.0),
    "high": (3.0, 4.0, 5.0, 5.0),
}
_FILL_OUTPUTS = {"low": 18.0, "medium": 55.0, "high": 90.0}
_TIME_OUTPUTS = {"recent": 12.0, "aging": 50.0, "overdue": 88.0}
_CRITICALITY_OUTPUTS = {"low": 30.0, "medium": 60.0, "high": 90.0}


def _finite_number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _trapezoid(value: float, points: tuple[float, float, float, float]) -> float:
    """Evaluate a trapezoidal membership function, including shoulder sets."""
    a, b, c, d = points
    if value < a or value > d:
        return 0.0
    if b <= value <= c:
        return 1.0
    if value < b:
        return 1.0 if a == b else (value - a) / (b - a)
    return 1.0 if c == d else (d - value) / (d - c)


def _fuzzify(value: float, sets: dict[str, tuple[float, float, float, float]]):
    return {name: _trapezoid(value, points) for name, points in sets.items()}


def _criticality_value(value) -> float:
    if isinstance(value, str):
        labels = {"low": 1.0, "medium": 3.0, "high": 5.0}
        try:
            return labels[value.strip().lower()]
        except KeyError as exc:
            raise ValueError("criticality must be 1–5 or Low, Medium, High") from exc
    number = _finite_number(value, "criticality")
    if not 1.0 <= number <= 5.0:
        raise ValueError("criticality must be between 1 and 5")
    return number


class FuzzyPrioritySystem:
    """Three-input, 27-rule zero-order Sugeno priority inference system.

    Inputs: fill percentage [0, 100], hours since verified emptying [0, 72],
    and criticality [1, 5]. Each rule fires with the product of its input
    membership degrees. The crisp urgency score is the firing-strength-
    weighted average of the rule consequents.
    """

    def score(self, fill_pct, hours_elapsed, criticality) -> float:
        fill = min(100.0, max(0.0, _finite_number(fill_pct, "fill_pct")))
        hours = min(72.0, max(0.0, _finite_number(hours_elapsed, "hours_elapsed")))
        criticality_number = _criticality_value(criticality)

        fill_memberships = _fuzzify(fill, _FILL_SETS)
        time_memberships = _fuzzify(hours, _TIME_SETS)
        criticality_memberships = _fuzzify(criticality_number, _CRITICALITY_SETS)

        weighted_output = 0.0
        total_strength = 0.0
        for fill_term, time_term, criticality_term in product(
            _FILL_SETS, _TIME_SETS, _CRITICALITY_SETS
        ):
            strength = (
                fill_memberships[fill_term]
                * time_memberships[time_term]
                * criticality_memberships[criticality_term]
            )
            if strength == 0.0:
                continue
            consequent = (
                0.60 * _FILL_OUTPUTS[fill_term]
                + 0.25 * _TIME_OUTPUTS[time_term]
                + 0.15 * _CRITICALITY_OUTPUTS[criticality_term]
            )
            weighted_output += strength * consequent
            total_strength += strength

        if total_strength == 0.0:
            raise RuntimeError("Fuzzy priority rule base did not cover the input")
        return round(min(100.0, max(0.0, weighted_output / total_strength)), 2)


_DEFAULT_SYSTEM = FuzzyPrioritySystem()


def calculate_priority(fill_pct, hours_elapsed, criticality, fuzzy_system=None) -> float:
    """Return a bounded Sugeno fuzzy urgency score in [0, 100]."""
    system = fuzzy_system or _DEFAULT_SYSTEM
    return system.score(fill_pct, hours_elapsed, criticality)
