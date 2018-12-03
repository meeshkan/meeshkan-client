"""Module to define different types used through Meeshkan codebase"""
from typing import NewType, Dict, Any, List

Token = NewType("Token", str)
Payload = Dict[str, Any]
HistoryByScalar = Dict[str, List[float]]
