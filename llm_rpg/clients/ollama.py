from typing import List, Dict, Any, Union
from ollama import ChatResponse, GenerateResponse
from ollama import Client
import pydantic
from ..templates.base_client import BaseClient
import logging
logger = logging.getLogger(__name__)
import json

def clean_json(x: str) -> str:
    x = x.replace('json', '')
    x = x.replace('```', '')
    x = x.replace('`', '')
    return x.strip()

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


    @staticmethod
    def __prepare_response(raw_response):
        response = {}
        promt_eval_d = -1
        eval_duration = -1

        try:
            promt_eval_d = raw_response.prompt_eval_duration / 10 ** 6
        except:
            promt_eval_d = -1

        try:
            eval_duration = raw_response.eval_duration / 10 ** 6
        except:
            eval_duration = -1

        response = {
            'message': raw_response.message.content,
            'stats': {
                'prompt_tokens': raw_response.prompt_eval_count,
                'prompt_eval_duration': promt_eval_d,
                'eval_tokens': raw_response.eval_count,
                'eval_duration': eval_duration
            }
        }

        return response


    def chat(self, messages: List[Dict[Any, Any]],
             **kwargs) -> Dict[str, Any]:
        """
        response.message.content
        :param messages:
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
        options = kwargs.get('options', None)
        if options is None:
            opts = self.model_options
        else:
            opts = options

        if "temperature" in kwargs:
            opts.update({"temperature": kwargs['temperature']})

        raw_response =  self.client.chat(model=self.model_name,
                           options=opts,
                           messages=messages)
        response = self.__prepare_response(raw_response)
        return response


    def struct_output(self, messages: List[Dict[Any, Any]],
                      pydantic_model: pydantic.BaseModel,
                      **kwargs) -> Dict[str, Any]:
        """
        Returns structured output if it can be extracted. If not -- response['message'] = None

        :param messages:
        :param pydantic_model:
        :param kwargs:
        :return: response --> Dict[str, Any] -- 'message': response
                                                'stats': Dict[str, int|float]
        """
        options = kwargs.get('options', None)
        if options is None:
            opts = self.model_options
        else:
            opts = options

        if "temperature" in kwargs:
            opts.update({"temperature": kwargs['temperature']})

        try:
            schema = pydantic_model.model_json_schema()
            system_message = [{
                "role": "system",
                "content": f"Respond matching: {json.dumps(schema)}"
            }]
        except Exception as e:
            system_message = []

        raw_response = self.client.chat(model=self.model_name,
                                        options=opts,
                                        messages=system_message + messages,
                                        format=pydantic_model.model_json_schema())

        msg = raw_response.message.content

        try:
            msg_s = pydantic_model.model_validate_json( clean_json(msg) )
        except Exception as e:
            logger.warning(f"Could not parse the response to the Pydantic model, returning None. Error: {e}")
            msg_s = None

        response = self.__prepare_response(raw_response)
        response['message'] = msg_s

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
