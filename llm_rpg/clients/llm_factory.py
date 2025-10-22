from typing import Dict, Any, Optional
import os
import logging

from llm_rpg.clients.ollama import OllamaW
from llm_rpg.clients.deepseek import DeepSeekW_OAI
from llm_rpg.clients.groq import GroqW
from llm_rpg.clients.dummy_llm import DummyLLM

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
        temperature = llm_config.get('temperature', 0.7)
        max_tokens = llm_config.get('max_tokens', 2000)

        # Get API key from environment
        api_key = os.environ.get(api_key_env, '')

        if not api_key and provider not in ['ollama', 'dummy']:
            logger.warning(f"No API key found for {provider}. Using DummyLLM instead.")
            return DummyLLM()

        try:
            if provider == 'deepseek':
                # Use OpenAI-compatible interface for DeepSeek
                return DeepSeekW_OAI(model, api_key, temperature=temperature, max_tokens=max_tokens)

            elif provider == 'groq':
                return GroqW(model, api_key, temperature=temperature, max_tokens=max_tokens)

            elif provider == 'ollama':
                return OllamaW(model, temperature=temperature, max_tokens=max_tokens)

            elif provider == 'dummy':
                return DummyLLM()

            else:
                logger.error(f"Unknown LLM provider: {provider}. Using DummyLLM.")
                return DummyLLM()

        except Exception as e:
            logger.error(f"Error creating {provider} client: {e}. Using DummyLLM.")
            return DummyLLM()