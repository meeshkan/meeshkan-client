"""Module to define different types used through Meeshkan codebase"""
from typing import NewType, Dict, Any, List, Tuple
import time

class ScalarTimePairing(object):
    def __init__(self, value: float, timevalue=None):
        self.value = value
        self.time = timevalue if timevalue is not None else time.monotonic()

Token = NewType("Token", str)
Payload = Dict[str, Any]
# Keys are scalar names, value is a list of tuples, indicating wall time and value for that scalar
HistoryByScalar = Dict[str, List[ScalarTimePairing]]
