"""Module to define different types used through Meeshkan codebase"""
from typing import NewType, Dict, Any, List
from numbers import Number

Token = NewType("Token", str)
Payload = Dict[str, Any]
HistoryByScalar = Dict[str, List[Number]]
