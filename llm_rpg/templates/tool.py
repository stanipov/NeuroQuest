from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union
from .base_client import BaseClient
import pydantic
import json

import logging
logger = logging.getLogger(__name__)

class BaseTool(ABC):
    def __init__(self, llm_client: BaseClient,
                 response_model: pydantic.BaseModel,
                 *args: object, **kwargs: object) -> None:
        """
        Init class
        :param llm_client: BaseClient -- LLM interface/wrapper
        :param response_model: pydantic.BaseModel -- response model
        :param args: -- Any
        :param kwargs: Any
        """
        self.response_model = response_model
        self.llm = llm_client
        # stats for a recent call
        self.stats = {}
        # the last submitted messages
        self.last_submitted_messages = {}

    def add_struct_sys_prompt(self) -> List[Dict[str, str]]:
        """Adds to a system prompt JSON schema of the response model"""
        system_message = []
        try:
            system_message = [{
                "role": "system",
                "content": f"""Respond with a JSON object that strictly follows: {json.dumps(self.response_model.model_json_schema())}"""
            }]
        except Exception as e:
            logger.warning(f"Could not dump pydantic model to JSON: \"{e}\"")
        return system_message

    def submit_messages(self, messages, **kwargs) -> pydantic.BaseModel:
        """Backend to run get structured input"""
        self.last_submitted_messages = messages
        raw_response = self.llm.struct_output(messages, self.response_model, **kwargs)
        try:
            self.stats = raw_response['stats']
        except Exception as e:
            logger.warning(f"Could not get call stats with \"{e}\"")
        return raw_response['message']

    @abstractmethod
    def compile_messages(self, *args, **kwargs):
        pass

    @abstractmethod
    def run(self, *arg, **kwargs):
        pass