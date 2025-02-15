from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseClient(ABC):
    """Base class for wrapping different LLM API implementations"""

    def __init__(self, model_name=None, *args, **kwargs) -> Any:
        """
        Initializes the base class with model configuration.

        :param model_name: The name of the LLM model or API endpoint (e.g., 'ollama', 'llama2')
        :type model_name: str
        """
        self.model_name = model_name


    def set_model(self, model_name: str) -> Any:
        """
        Sets the language model name.

        :param model_name: The name of the LLM model or API endpoint to set.
        :type model_name: str
        :return: This method is abstract and will be overridden by subclasses.
        """
        self.model_name = model_name

    @abstractmethod
    def chat(self, messages: List[Dict[Any, Any]]) -> Any:
        """
        Sends messages to an LLM instance for processing.

        :param messages: A list of message dictionaries, each containing a 'content' key.
        :return: Returns the raw output
        """

    @abstractmethod
    def stream(self, messages: List[Dict[Any, Any]]) -> Any:
        """
        Sends messages to an LLM instance for streaming responses. The results are returned as streaming data.

        :param messages: A list of message dictionaries, each containing a 'content' key.
        :return: Returns the raw output
        """