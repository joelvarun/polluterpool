"""polluterpool: shared-tail group testing for order-dependent test localization."""

from .suite import Suite
from .oracle import Oracle, ModelOracle, WorkerOracle, PytestOracle, Cost
from .discover import discover_victims
from .baselines import localize_bisect, localize_ddmin
from .pool import localize_pool

__all__ = [
    "Suite",
    "Oracle",
    "ModelOracle",
    "WorkerOracle",
    "PytestOracle",
    "Cost",
    "discover_victims",
    "localize_bisect",
    "localize_ddmin",
    "localize_pool",
]

__version__ = "0.1.0"
