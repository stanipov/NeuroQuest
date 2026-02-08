from typing import Dict, Any, Optional
import os
import logging

from llm_rpg.clients.ollama import OllamaW
from llm_rpg.clients.deepseek import DeepSeekW_OAI
from llm_rpg.clients.groq import GroqW
from llm_rpg.clients.dummy_llm import DummyLLM
from llm_rpg.clients.llamacpp import LocalLLMClient

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory class for creating LLM clients based on configuration"""

    @staticmethod
    def create_llm_client(llm_config: Dict[str, Any]) -> Any:
        """
        Create LLM client based on configuration

        Args:
            llm_config: Configuration dictionary for the LLM

        Returns:
            LLM client instance
        """
        provider = llm_config.get('provider', '').lower()
        model = llm_config.get('model', '')
        api_key_env = llm_config.get('api_key_env', '')
        props = llm_config.get("props", {})

        # For providers that don't require API key (local LLMs), set default placeholder
        if not os.environ.get(api_key_env, '') and provider in ['llamacpp', 'ollama']:
            api_key = 'not-needed'

        if not api_key and provider not in ['llamacpp', 'ollama', 'dummy']:
            logger.warning(f"No API key found for {provider}. Using DummyLLM instead.")
            return DummyLLM()

        try:
            if provider == 'deepseek':
                # Use OpenAI-compatible interface for DeepSeek
                api_key = os.environ.get(api_key_env, '')
                return DeepSeekW_OAI(model, api_key, **props)

            elif provider == 'groq':
                api_key = os.environ.get(api_key_env, '')
                return GroqW(model, api_key, **props)

            elif provider == 'llamacpp':
                # Use OpenAI-compatible interface for llama.cpp server
                base_url = llm_config.get('base_url', 'http://localhost:9000/v1')
                return LocalLLMClient(model, base_url=base_url, api_key=api_key, **props)

            elif provider == 'ollama':
                base_url = llm_config.get('base_url', 'http://localhost:11434')
                return OllamaW(model, host=base_url, **props)

            elif provider == 'dummy':
                return DummyLLM()

            else:
                logger.error(f"Unknown LLM provider: {provider}. Using DummyLLM.")
                return DummyLLM()

        except Exception as e:
            logger.error(f"Error creating {provider} client: {e}. Using DummyLLM.")
            return DummyLLM()