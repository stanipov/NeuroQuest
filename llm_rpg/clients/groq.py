from typing import List, Dict, Any
from groq import Groq
from ..templates.base_client import BaseClient
from groq.types.chat import ChatCompletion

class GroqW(BaseClient):
    def __init__(self, model_name,
                 api_key:str,
                 *args):
        self.model_name = model_name
        self.__api_key = api_key
        self.client = Groq(api_key=self.__api_key)

    def set_model(self, model_name):
        self.model_name = model_name
        self.client = Groq(api_key=self.__api_key)
        return self.client

    def chat(self, messages: List[Dict[Any, Any]], *args, **kwargs) -> ChatCompletion:
        return self.client.chat.completions.create(messages=messages,
                                                   model=self.model_name,
                                                   **kwargs)

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

