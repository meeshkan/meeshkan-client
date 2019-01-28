"""Serializer class to control Pyro4 (de)serialization"""
import importlib
from typing import List

__all__ = []  # type: List[str]

class Serializer:
    # Uses old encoding, see https://stackoverflow.com/a/27527728/4133131
    # recurse==True also packs relevant modules etc and imports if needed and declared in a different module...
    LIB = importlib.import_module('dill')
    ENCODING = 'cp437'
    NAME = 'dill'

    @staticmethod
    def serialize(content):
        return Serializer.LIB.dumps(content, recurse=True).decode(Serializer.ENCODING)

    @staticmethod
    def deserialize(content):
        return Serializer.LIB.loads(content.encode(Serializer.ENCODING))

    @staticmethod
    def deserialize_func_as_str(func_name):
        return "import {lib}\ndef {func_name}(content):\n" \
               "    return {lib}.loads(content.encode('{encoding}'))\n\n".format(func_name=func_name,
                                                                                 lib=Serializer.NAME,
                                                                                 encoding=Serializer.ENCODING)
