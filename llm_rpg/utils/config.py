import logging
from typing import Dict, Any
from llm_rpg.clients.llm_factory import LLMFactory

logger = logging.getLogger(__name__)


def setup_llms(config: dict) -> Dict[str, Any]:
    """Setup LLM clients based on configuration dict"""
    llm_clients = {}
    llm_types = ["lore_llm", "npc_ai_llm", "game_ai_llm", "input_validator"]

    llm_providers = config.get("llm_providers", {})

    for llm_type in llm_types:
        llm_config = llm_providers.get(llm_type)
        if llm_config is not None:
            llm_clients[llm_type] = LLMFactory.create_llm_client(llm_config)
            logging.info(f"Created {llm_type} client: {llm_config.get('provider')}")
        else:
            llm_clients[llm_type] = None

    return llm_clients


def get_lore_generation_params(
    config: dict, user_params: Dict[str, Any]
) -> Dict[str, Any]:
    """Combine configuration and user parameters for lore generation"""
    lore_config = config.get("lore_generation", {}).copy()
    lore_config.update(user_params)  # User params take precedence

    return lore_config
