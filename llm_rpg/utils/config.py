import json
import os
from typing import Dict, Any, Optional

import logging

from llm_rpg.clients.llm_factory import LLMFactory

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.config = {}

        if not self.config_path:
            logger.error("Config path not provided")
            raise ValueError("Config path not provided")

        with open(self.config_path, 'r') as f:
            self.config = json.load(f)


    def get_llm_config(self, llm_type: str) -> Dict[str, Any]:
        """Get configuration for specific LLM type"""
        llm_configs = self.config.get('llm_providers', {})
        return llm_configs.get(llm_type, {})


    def get_path_config(self) -> Dict[str, str]:
        """Get path configuration"""
        return self.config.get('paths', {})


    def get_game_config(self) -> Dict[str, Any]:
        """Get game configuration"""
        return self.config.get('game', {})


    def get_lore_config(self) -> Dict[str, Any]:
        """Get lore generation configuration"""
        return self.config.get('lore_generation', {})


def create_default_config() -> Dict[str, Any]:
    """Create a default configuration template"""
    return {
        "paths": {
            "game_folder": "game",
            "log_folder": "game/logs",
            "saved_games_folder": "game/saved_games",
            "config_folder": "config"
        },
        "llm_providers": {
            "lore_llm": {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "api_key_env": "DEEP_SEEK_API_KEY",
                "temperature": 1.0,
                "max_tokens": 4000
            },
            "npc_ai_llm": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "api_key_env": "GROQ_API_KEY",
                "temperature": 0.5,
                "max_tokens": 2000
            },
            "game_ai_llm": {
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "api_key_env": "GROQ_API_KEY",
                "temperature": 0.5,
                "max_tokens": 2000
            }
        },
        "lore_generation": {
            "num_npc_rules": 10,
            "num_world_rules": 10,
            "sleep_sec": 0,
            "api_delay": 0
        },
        "game": {
            "npc_turn_history": 10,
            "game_chat_history": 100
        }
    }


def save_config(config: Dict[str, Any], config_path: str):
    """Save configuration to JSON file"""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def setup_llms(config_manager: ConfigManager) -> Dict[str, Any]:
    """Setup LLM clients based on configuration"""
    llm_clients = {}

    llm_types = ['lore_llm', 'npc_ai_llm', 'game_ai_llm']

    for llm_type in llm_types:
        llm_config = config_manager.get_llm_config(llm_type)
        llm_clients[llm_type] = LLMFactory.create_llm_client(llm_config)
        logging.info(f"Created {llm_type} client: {llm_config.get('provider')}")

    return llm_clients


def get_lore_generation_params(config_manager: ConfigManager, user_params: Dict[str, Any]) -> Dict[str, Any]:
    """Combine configuration and user parameters for lore generation"""
    lore_config = config_manager.get_lore_config()

    # Merge user parameters with configuration (user params take precedence)
    combined_params = lore_config.copy()
    combined_params.update(user_params)

    return combined_params
