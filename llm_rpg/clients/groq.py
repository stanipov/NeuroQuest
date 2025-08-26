from typing import List, Dict, Any
from groq import Groq
import pydantic
from openai import responses
import json
from ..templates.base_client import BaseClient
from groq.types.chat import ChatCompletion
import logging
logger = logging.getLogger(__name__)

try:
    import instructor
    F_IS_SRUCT = True
except Exception as e:
    logger.warning(f"\"instructor\" is not installed, no structured output!")
    F_IS_SRUCT = False

class GroqW(BaseClient):
    def __init__(self, model_name,
                 api_key:str,
                 *args, **kwargs):
        self.model_name = model_name
        self.__api_key = api_key
        self.client = Groq(api_key=self.__api_key)
        # default temperature
        self._T = 0.5
        if 'temperature' in kwargs:
            self._T = kwargs['temperature']

        if F_IS_SRUCT:
            self.struct_client = instructor.from_groq(self.client)
        else:
            self.struct_client = None

    def set_model(self, model_name):
        self.model_name = model_name
        self.client = Groq(api_key=self.__api_key)
        if F_IS_SRUCT:
            self.struct_client = instructor.from_groq(self.client)
        else:
            self.struct_client = None
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

    def struct_output(self, messages: List[Dict[Any, Any]],
                        pydantic_model: pydantic.BaseModel,
                        **kwargs) -> Dict[str, Any]:
        if 'temperature' in kwargs:
            temp = kwargs.pop('temperature')
        else:
            temp = self._T
        # exclude possible streaming
        if "stream" in kwargs:
            _ = kwargs.pop('stream')

        ans = {
            "message": None,
            "stats": None
        }

        try:
            system_message = [{
                "role": "system",
                "content": f"""You MUST output a JSON object that strictly follows this schema: {json.dumps(pydantic_model.model_json_schema())}"""
            }]
        except Exception as e:
            system_message = []

        if self.struct_client is not None:
            response = None
            try:
                response = self.struct_client.chat.completions.create(model=self.model_name,
                                                             messages=system_message + messages,
                                                             response_model=pydantic_model,
                                                             temperature=temp, **kwargs)
            except Exception as e:
                logger.warning(f"Failed to extract structured output, returning None. Error: {e}")

            ans['message'] = response

        return ans

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

