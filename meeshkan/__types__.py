"""Module to define different types used through Meeshkan codebase"""
from typing import NewType, Dict, Any, List, Tuple
import time

class ScalarIndexPairing:
    """Represents a coupling between a scalar value and an index. If no index is provided, time.monotonic() is used
    to maintain consistent scale."""
    def __init__(self, value: float, idx=None):
        self.value = value
        self.idx = idx if idx is not None else time.monotonic()

Token = NewType("Token", str)
Payload = Dict[str, Any]
# Keys are scalar names, value is a list of tuples, indicating wall time and value for that scalar
HistoryByScalar = Dict[str, List[ScalarIndexPairing]]
