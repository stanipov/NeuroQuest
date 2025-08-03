from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union
from pydantic import BaseModel


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
    def chat(self, messages: List[Dict[Any, Any]], *arg, **kwargs) -> Dict[str, Any]:
        """
        Sends messages to an LLM instance for processing.

        :param messages: A list of message dictionaries, each containing a 'content' key.
        :return: Dict[str, Any] ->
            response = {
                "message": LLM response,
                "stats": {
                    'prompt_tokens': count of prompt tokens
                    'prompt_eval_duration': prompt evaluation duration in ms,
                    'eval_tokens': count of response tokens,
                    'eval_duration': generation duration in ms
                }
            }
        """

    @abstractmethod
    def struct_output(self, messages: List[Dict[Any, Any]], response_model:BaseModel, **kwargs) -> Any:
        """
        Sends messages to an LLM instance for processing and return Pydantic structured output
        :param messages: A list of message dictionaries, each containing a 'content' key.
        :param response_model: Pydantic.BaseModel
        :return: Dict[str, Any] ->
            response = {
                "message": Pydantic.BaseModel,
                "stats": {
                    'prompt_tokens': count of prompt tokens
                    'prompt_eval_duration': prompt evaluation duration in ms,
                    'eval_tokens': count of response tokens,
                    'eval_duration': generation duration in ms
                }
            }
        """

    @abstractmethod
    def stream(self, messages: List[Dict[Any, Any]]) -> Any:
        """
        Sends messages to an LLM instance for streaming responses. The results are returned as streaming data.

        :param messages: A list of message dictionaries, each containing a 'content' key.
        :return: Returns the raw output
        """