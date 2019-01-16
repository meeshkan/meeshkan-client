"""Serializer class to control Pyro4 (de)serialization"""
import importlib
from typing import List

__all__ = []  # type: List[str]

class BaseSerializer:
    """Base class for serializer object. Provides consistency and shortcuts across the code."""
    def serialize(self, content):
        raise NotImplementedError

    def deserialize(self, content):
        raise NotImplementedError

    def __str__(self):
        raise NotImplementedError

    def __call__(self, content):
        return self.serialize(content)


class DillSerializer(BaseSerializer):
    def __init__(self, encoding='cp437'):
        # Uses old encoding, see https://stackoverflow.com/a/27527728/4133131
        # recurse==True also packs relevant modules etc and imports if needed and declared in a different module...
        self.lib = importlib.import_module('dill')
        self.encoding = encoding

    def __str__(self):
        return self.lib.__name__

    def serialize(self, content):
        return self.lib.dumps(content, recurse=True).decode(self.encoding)

    def deserialize(self, content):
        return self.lib.loads(content.encode(self.encoding))
