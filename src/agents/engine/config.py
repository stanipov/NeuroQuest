from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class EngineConfig(BaseModel):
    history_window: int = 10  # messages passed to game/narration prompts
    npc_window: int = 6  # npc_history window per NPC
    sqlite_path: str = "data/engine_checkpoints.db"

    @classmethod
    def from_json(cls, path: str = "configs/engine.json") -> EngineConfig:
        config_path = Path(path)
        if config_path.exists():
            return cls(**json.loads(config_path.read_text()))
        return cls()
