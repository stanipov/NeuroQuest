import requests
from typing import List, Dict, Any
from pydantic import BaseModel
from openai import OpenAI
from llm_rpg.templates.base_client import BaseClient
import json

class LocalLLMClient(BaseClient):
    """Wrapper for a local LLM server compatible with the OpenAI API (e.g., llama.cpp server)."""

    def __init__(self, model_name: str = None, base_url: str = "http://localhost:8000/v1", api_key: str = "not-needed", *args, **kwargs):
        """
        Initializes the local LLM client.

        :param model_name: The name of the model to use.
        :param base_url: The base URL of the local server exposing OpenAI-compatible API.
        :param api_key: Placeholder API key (often not required for local LLMs).
        """
        super().__init__(model_name, *args, **kwargs)
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def chat(self, messages: List[Dict[Any, Any]], *args, **kwargs) -> Dict[str, Any]:
        response = self.client.chat.completions.create(model=self.model_name, messages=messages, **kwargs)

        result = {
            "message": response.choices[0].message.content,
            "stats": {
                "prompt_tokens": response.usage.prompt_tokens,
                "prompt_eval_duration": getattr(response, "prompt_eval_duration", None),
                "eval_tokens": response.usage.completion_tokens,
                "eval_duration": getattr(response, "eval_duration", None)
            }
        }
        return result

    def struct_output(self, messages: List[Dict[Any, Any]], response_model: BaseModel, **kwargs) -> Any:
        system_message = []
        try:
            system_message = self.enforce_struct_output(response_model)
        except Exception as e:
            system_message = []

        response = self.client.chat.completions.create(model=self.model_name,
                                                       messages=system_message+messages,
                                                       **kwargs)
        structured = response_model.parse_raw(response.choices[0].message.content)
        result = {
            "message": structured,
            "stats": {
                "prompt_tokens": response.usage.prompt_tokens,
                "prompt_eval_duration": getattr(response, "prompt_eval_duration", None),
                "eval_tokens": response.usage.completion_tokens,
                "eval_duration": getattr(response, "eval_duration", None)
            }
        }
        return result

    def stream(self, messages: List[Dict[Any, Any]], **kwargs) -> Any:
        stream = self.client.chat.completions.create(model=self.model_name,messages=messages,stream=True,**kwargs)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta["content"]


class LocalLLMClientR(BaseClient):
    """Wrapper for a local LLM server compatible with the OpenAI API (e.g., llama.cpp server)."""

    def __init__(self, model_name: str = None, base_url: str = "http://localhost:8000/v1", api_key: str = "not-needed", *args, **kwargs):
        super().__init__(model_name, *args, **kwargs)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key  # usually not needed locally

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def chat(self, messages: List[Dict[Any, Any]], **kwargs) -> Dict[str, Any]:
        payload = {
            "model": self.model_name,
            "messages": messages,
            **kwargs
        }
        resp = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload)
        resp.raise_for_status()
        response = resp.json()

        result = {
            "message": response["choices"][0]["message"]["content"],
            "stats": {
                "prompt_tokens": response.get("usage", {}).get("prompt_tokens"),
                "prompt_eval_duration": response.get("prompt_eval_duration"),
                "eval_tokens": response.get("usage", {}).get("completion_tokens"),
                "eval_duration": response.get("eval_duration"),
            }
        }
        return result

    def struct_output(self, messages: List[Dict[Any, Any]], response_model: BaseModel, **kwargs) -> Any:
        payload = {
            "model": self.model_name,
            "messages": messages,
            **kwargs
        }
        resp = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload)
        resp.raise_for_status()
        response = resp.json()

        structured = response_model.parse_raw(response["choices"][0]["message"]["content"])
        result = {
            "message": structured,
            "stats": {
                "prompt_tokens": response.get("usage", {}).get("prompt_tokens"),
                "prompt_eval_duration": response.get("prompt_eval_duration"),
                "eval_tokens": response.get("usage", {}).get("completion_tokens"),
                "eval_duration": response.get("eval_duration"),
            }
        }
        return result

    def stream(self, messages: List[Dict[Any, Any]], **kwargs) -> Any:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            **kwargs
        }
        with requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload, stream=True) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                if line.startswith(b"data: "):
                    chunk = line[len(b"data: "):]
                    if chunk == b"[DONE]":
                        break
                    data = json.loads(chunk.decode("utf-8"))
                    delta = data["choices"][0]["delta"]
                    if "content" in delta and delta["content"]:
                        yield delta["content"]
