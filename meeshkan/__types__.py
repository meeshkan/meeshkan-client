"""Module to define different types used through Meeshkan codebase"""
from typing import NewType, Dict

Token = NewType("Token", str)
Payload = NewType('Payload', Dict[str, str])