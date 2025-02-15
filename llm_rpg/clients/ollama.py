from typing import List, Dict, Any
from ollama import ChatResponse, GenerateResponse
from ollama import Client
from ..templates.base_client import BaseClient

class OllamaW(BaseClient):
    def __init__(self, model_name,
                 host:str=None,
                 **options):
        self.model_name = model_name
        self.model_options = options

        if host is not None and host!='':
            self.host = host
        else:
            self.host = "http://localhost:11434"

        self.client = Client(host=self.host)

    def set_model(self, model_name):
        self.model_name = model_name
        self.client = Client(self.host)
        return self.client

    def chat(self, messages: List[Dict[Any, Any]]) -> ChatResponse:
        return self.client.chat(model=self.model_name,
                           options=self.model_options,
                           messages=messages
                           )

    def stream(self, messages: List[Dict[Any, Any]]) -> GenerateResponse:
        """
        stream
        for x in response:
            print(x.message.content)

        :param messages:
        :return:
        """
        return self.client.chat(model=self.model_name,
                                options=self.model_options,
                                messages=messages,
                                stream=True)
