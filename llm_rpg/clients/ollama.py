from typing import List, Dict, Any, Union
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

    def chat(self, messages: List[Dict[Any, Any]],
             options:Union[Any,Dict[Any,Any]]=None) -> ChatResponse:
        """
        response.message.content
        :param messages:
        :return: Dict[str, Any] -> {
                "message": LLM reponse,
                "stats": {
                    'promt_tokens': count of prompt tokens
                    'promt_eval_duration': prompt evaluation duration in ms,
                    'eval_tokens': count of response tokens,
                    'eval_duration': generation duration in ms
                }
            }
        """
        if options is None:
            opts = self.model_options
        else:
            opts = options
        raw_response =  self.client.chat(model=self.model_name,
                           options=opts,
                           messages=messages)
        response = {
            'message': raw_response.message.content,
            'stats': {
                'promt_tokens': raw_response.prompt_eval_count,
                'promt_eval_duration': raw_response.prompt_eval_duration/10**6,
                'eval_tokens': raw_response.eval_count,
                'eval_duration': raw_response.eval_duration/10**6
            }
        }
        return response

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
