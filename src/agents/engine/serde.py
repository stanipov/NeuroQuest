from __future__ import annotations

import inspect

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from src.baml_client import types as baml_types


def build_serde() -> JsonPlusSerializer:
    """Build the checkpointer serde used by the engine.

    LangGraph's default msgpack serializer warns on unregistered types and will
    block them in a future version. The engine stores BAML Pydantic models and
    enums in checkpointed state, so register every type generated into
    `src.baml_client.types` explicitly.
    """
    allowed = [
        obj
        for _, obj in inspect.getmembers(baml_types, inspect.isclass)
        if obj.__module__ == baml_types.__name__
    ]
    return JsonPlusSerializer(allowed_msgpack_modules=allowed)
