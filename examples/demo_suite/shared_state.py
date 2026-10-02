"""Mutable process state shared by the generated tests."""

STATE = {}
_REGISTRY = None


def registry():
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = set()
    return _REGISTRY
