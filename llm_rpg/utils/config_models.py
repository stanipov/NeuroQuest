from pydantic import BaseModel, Field
from typing import Optional


class LLMProps(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 2000


class LLMConfig(BaseModel):
    provider: str
    model: str
    api_key_env: str
    base_url: Optional[str] = None
    props: LLMProps = Field(default_factory=LLMProps)


class PathsConfig(BaseModel):
    game_folder: str = "game"
    log_folder: str = "game/logs"
    saved_games_folder: str = "game/saved_games"
    config_folder: str = "config"


class LoreGenerationConfig(BaseModel):
    num_world_rules_per_category: int = 4
    num_npc_rules_per_category: int = 3
    max_generation_retries: int = 3
    temperature_cooldown_step: float = 0.1
    temperature_min: float = 0.5
    sleep_sec: int = 0
    api_delay: int = 0


class GameConfig(BaseModel):
    auto_save: bool = True
    max_chat_history: int = 100
    npc_chat_history: int = 20
    aux_chat_history: int = 100


class TemperatureConfig(BaseModel):
    lore_world_gen: float = 1.5
    lore_npc_gen: float = 0.75
    lore_inventory_desc: float = 0.25
    lore_action_rules: float = 0.9
    npc_response: float = 0.75
    gameplay_action: float = 0.9


class AppConfig(BaseModel):
    dotenv_path: Optional[str] = None
    paths: PathsConfig = Field(default_factory=PathsConfig)
    llm_providers: dict[str, LLMConfig] = Field(default_factory=dict)
    lore_generation: LoreGenerationConfig = Field(default_factory=LoreGenerationConfig)
    game: GameConfig = Field(default_factory=GameConfig)
    temperatures: TemperatureConfig = Field(default_factory=TemperatureConfig)

    class Config:
        extra = "ignore"
