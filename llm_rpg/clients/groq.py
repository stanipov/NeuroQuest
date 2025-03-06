from typing import List, Dict, Any
from groq import Groq
from ..templates.base_client import BaseClient
from groq.types.chat import ChatCompletion
import logging
logger = logging.getLogger(__name__)

class GroqW(BaseClient):
    def __init__(self, model_name,
                 api_key:str,
                 *args, **kwargs):
        self.model_name = model_name
        self.__api_key = api_key
        self.client = Groq(api_key=self.__api_key)
        if 'temperature' in kwargs:
            self._T = kwargs['temperature']

    def set_model(self, model_name):
        self.model_name = model_name
        self.client = Groq(api_key=self.__api_key)
        return self.client

    def chat(self, messages: List[Dict[Any, Any]], *args, **kwargs) -> Dict[str, Any]:
        """
        response.choices[0].message.content
        :param messages:
        :param args:
        :param kwargs:
        :return: Dict[str, Any] -> {
                "message": LLM response,
                "stats": {
                    'promt_tokens': count of prompt tokens
                    'promt_eval_duration': prompt evaluation duration in ms,
                    'eval_tokens': count of response tokens,
                    'eval_duration': generation duration in ms
                }
            }
        """
        if 'temperature' in kwargs:
            temp = kwargs.pop('temperature')
        else:
            temp = self._T
        # exclude possible streaming
        if "stream" in kwargs:
            _ = kwargs.pop('stream')
        raw_response = self.client.chat.completions.create(messages=messages,
                                                   model=self.model_name,
                                                   temperature=temp,
                                                   **kwargs)

        response = {
            'message': raw_response.choices[0].message.content,
            "stats": {
                'prompt_tokens': raw_response.usage.prompt_tokens,
                'prompt_eval_duration': raw_response.usage.prompt_time*1000,
                'eval_tokens': raw_response.usage.completion_tokens,
                'eval_duration': raw_response.usage.completion_time*1000,
                }
        }

        return response

    def stream(self, messages: List[Dict[Any, Any]], *args, **kwargs) -> ChatCompletion:
        """
        for x in response:
            print(x.choices[0].delta.content)
        :param messages:
        :param args:
        :param kwargs:
        :return:
        """
        return self.client.chat.completions.create(messages=messages,
                                                   model=self.model_name,
                                                   stream=True,
                                                   **kwargs)

