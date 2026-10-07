from __future__ import annotations

from pathlib import Path
from typing import Self
from uuid import uuid4

import aiosqlite
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from src.agents.engine.config import EngineConfig
from src.agents.engine.nodes import (
    brief,
    classification,
    game_response,
    narration,
    route_classification,
)
from src.agents.engine.npc import npc_act
from src.agents.engine.serde import build_serde
from src.agents.engine.state import GameState, initial_state


def build_graph() -> StateGraph:
    """Wire the game topology; returns an uncompiled `StateGraph`.

    `EngineConfig` is supplied per run through the graph's runtime context
    (`context=`), so it is not bound into the node functions here.
    """
    graph = StateGraph(GameState, context_schema=EngineConfig)

    graph.add_node("classification", classification)
    graph.add_node("npc", npc_act)
    graph.add_node("game_response", game_response)
    graph.add_node("brief", brief)
    graph.add_node("narration", narration)

    graph.add_edge(START, "classification")
    graph.add_conditional_edges("classification", route_classification)
    graph.add_edge("npc", "game_response")
    graph.add_edge("game_response", "narration")
    graph.add_edge("brief", "narration")
    graph.add_edge("narration", END)

    return graph


class Engine:
    """Owns the checkpointer lifecycle and the compiled game graph.

    Use as an async context manager::

        async with Engine(config) as engine:
            thread_id = await engine.new_game(lore)
            state = await engine.turn(thread_id, "look around")
    """

    def __init__(
        self,
        config: EngineConfig | None = None,
        *,
        checkpointer: BaseCheckpointSaver | None = None,
    ):
        self.config = config or EngineConfig()
        self._checkpointer = checkpointer
        self._conn: aiosqlite.Connection | None = None
        self.graph = None

    async def __aenter__(self) -> Self:
        if self._checkpointer is not None:
            saver = self._checkpointer
        else:
            # `from_conn_string` cannot carry our serde, and AsyncSqliteSaver
            # captures the running loop at construction, so open the connection
            # here (inside the loop) rather than in __init__.
            path = Path(self.config.sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(str(path))
            saver = AsyncSqliteSaver(self._conn, serde=build_serde())
            await saver.setup()

        self.graph = build_graph().compile(checkpointer=saver)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    def _cfg(self, thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}

    async def new_game(self, lore: dict, thread_id: str | None = None) -> str:
        """Seed a fresh thread with lore and return its thread id.

        Lore is written once here; later `turn`/`stream_turn` calls send only
        `raw_input`.
        """
        tid = thread_id or str(uuid4())
        await self.graph.aupdate_state(
            self._cfg(tid), initial_state(lore), as_node=START
        )
        return tid

    async def turn(self, thread_id: str, raw_input: str) -> GameState:
        return await self.graph.ainvoke(
            {"raw_input": raw_input}, self._cfg(thread_id), context=self.config
        )

    async def stream_turn(self, thread_id: str, raw_input: str):
        """Run one turn, yielding `updates` and `custom` stream events.

        Narration tokens arrive as `{"type": "custom", "data":
        {"narration_token": ...}}`; `subgraphs=False` keeps narration the only
        streaming point.
        """
        async for event in self.graph.astream(
            {"raw_input": raw_input},
            self._cfg(thread_id),
            stream_mode=["updates", "custom"],
            version="v2",
            subgraphs=False,
            context=self.config,
        ):
            yield event

    async def state(self, thread_id: str):
        return await self.graph.aget_state(self._cfg(thread_id))
