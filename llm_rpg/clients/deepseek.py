from markdown_it.common.utils import escapeHtml

from llm_rpg.templates.base_client import BaseClient
from typing import List, Dict, Any, Union, Optional, Type, Generator
import pydantic
from pydantic import BaseModel
import json
import requests

# --------------------------- Custom ValidationError for failed validation of Pydantic Model ---------------------------
class ValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)

    def __str__(self):
        return f"{self.message} (Error Code: {self.error_code})"

# --- Thank you, DeepSeek
# -------------------------------- requests based client --------------------------------
class DeepSeekW_requests(BaseClient):
    """Client for DeepSeek API using requests library"""

    def __init__(self, model_name: str,
                 api_key: str,
                 **kwargs) -> None:
        """
        Initializes the DeepSeek client.

        :param model_name: Name of the DeepSeek model (default: 'deepseek-chat')
        :param api_key: Your DeepSeek API key
        """
        super().__init__(model_name)
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.is_reasoner = "reasoner" in model_name.lower()
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # default temperature
        self._T = 1.0
        if 'temperature' in kwargs:
            self._T = kwargs['temperature']

    def set_model(self, model_name: str) -> None:
        """
        Sets the DeepSeek model name.

        :param model_name: Name of the DeepSeek model
        """
        self.model_name = model_name
        self.is_reasoner = "reasoner" in model_name.lower()

    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to make API requests"""
        url = f"{self.base_url}/{endpoint}"
        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()

    def chat(self,
             messages: List[Dict[Any, Any]],
             **kwargs) -> Dict[str, Any]:
        """
        Sends messages to DeepSeek API for processing.

        :param messages: List of message dictionaries
        :return: Dictionary with response and stats
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self._T,
            **kwargs
        }

        response = self._make_request("chat/completions", payload)

        result = {
            "message": response["choices"][0]["message"]["content"],
            "stats": {
                'prompt_tokens': response["usage"]["prompt_tokens"],
                'prompt_eval_duration': -1,  # Not supported by DS
                'eval_tokens': response["usage"]["completion_tokens"],
                'eval_duration': -1,  # Not supported by DS
                'total_tokens': response["usage"]["total_tokens"]
            }
        }

        if self.is_reasoner:
            result["reasoning_content"] = response["choices"][0]["message"].get("reasoning_content", "")
        else:
            result["reasoning_content"] = ""

        return result

    def stream(self, messages: List[Dict[Any, Any]], *args, **kwargs) -> Generator[Dict[str, Any], None, None]:
        """
        Streams responses from DeepSeek API with proper error handling.
        """
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "temperature": self._T,
            **kwargs
        }

        url = f"{self.base_url}/chat/completions"
        with requests.post(url, headers=self.headers, json=payload, stream=True) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                # Skip empty lines and keep-alive messages
                if not line or line == b': OPENROUTER PROCESSING':
                    continue

                try:
                    # Remove 'data: ' prefix if present
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        line_str = line_str[6:].strip()

                    # Skip empty data messages
                    if not line_str or line_str == '[DONE]':
                        continue

                    chunk = json.loads(line_str)

                    if self.is_reasoner:
                        yield {
                            "content": chunk["choices"][0]["delta"].get("content", ""),
                            "reasoning": chunk["choices"][0]["delta"].get("reasoning_content", "")
                        }
                    else:
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:  # Only yield non-empty content
                            yield content

                except json.JSONDecodeError as e:
                    print(f"Failed to decode chunk: {line_str}. Error: {e}")
                    continue
                except KeyError as e:
                    print(f"Malformed chunk missing expected keys: {chunk}. Error: {e}")
                    continue

    def struct_output(self,
                      messages: List[Dict[Any, Any]],
                      pydantic_model: pydantic.BaseModel,
                      **kwargs) -> Dict[str, Any]:
        """
        Generates structured output conforming to the given Pydantic model.

        :param messages: List of message dictionaries
        :param pydantic_model: Pydantic model class for structured output
        :return: Dictionary with structured message, stats, and reasoning
        """
        # Add instruction to format output as JSON matching the pydantic model
        try:
            system_message = self.enforce_struct_output(pydantic_model)
        except Exception as e:
            system_message = []

        # Insert the system message at the beginning
        messages_with_instruction = system_message + messages

        payload = {
            "model": self.model_name,
            "messages": messages_with_instruction,
            "response_format": {"type": "json_object"},
            "temperature": self._T,
            **kwargs
        }

        response = self._make_request("chat/completions", payload)

        # Parse the JSON content
        try:
            json_content = json.loads(response["choices"][0]["message"]["content"])
            structured_message = pydantic_model(**json_content)
        except (json.JSONDecodeError, pydantic.ValidationError) as e:
            raise ValidationError(f"Failed to parse or validate structured output: {str(e)}")

        # Build the result dictionary
        result = {
            "message": structured_message,
            "stats": {
                'prompt_tokens': response["usage"]["prompt_tokens"],
                'prompt_eval_duration': -1,
                'eval_tokens': response["usage"]["completion_tokens"],
                'eval_duration': -1,
                'total_tokens': response["usage"]["total_tokens"]
            }
        }

        # Add reasoning if available
        if self.is_reasoner:
            result["reasoning"] = response["choices"][0]["message"].get("reasoning_content", "")
        else:
            result["reasoning"] = ""

        return result


# -------------------------------- Open AI client based on --------------------------------
from llm_rpg.templates.base_client import BaseClient
from typing import List, Dict, Any, Union, Optional, Type
from openai import OpenAI
import pydantic
import json


class DeepSeekW_OAI(BaseClient):
    """Wrapper for DeepSeek API using OpenAI integration"""

    def __init__(self, model_name: str,
                 api_key: str,
                 **kwargs) -> None:
        """
        Initializes the DeepSeek client.

        :param model_name: Name of the DeepSeek model (default: 'deepseek-chat')
        :param api_key: Your DeepSeek API key
        :param base_url: DeepSeek API base URL
        """
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/"
        )
        self.model_name = model_name
        self.is_reasoner = "reasoner" in model_name.lower()

        # default temperature
        # https://api-docs.deepseek.com/quick_start/parameter_settings
        self._T = 1.0
        if 'temperature' in kwargs:
            self._T = kwargs['temperature']

    def set_model(self, model_name: str) -> None:
        """
        Sets the DeepSeek model name.

        :param model_name: Name of the DeepSeek model
        """
        self.model_name = model_name
        self.is_reasoner = "reasoner" in model_name.lower()

    def chat(self,
             messages: List[Dict[Any, Any]],
             **kwargs) -> Dict[str, Any]:
        """
        Sends messages to DeepSeek API for processing.

        :param messages: List of message dictionaries
        :return: Dictionary with response and stats
        """

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **kwargs
        )

        result = {
            "message": response.choices[0].message.content,
            "stats": {
                'prompt_tokens': response.usage.prompt_tokens,
                'prompt_eval_duration': -1,  # Not supported by DS
                'eval_tokens': response.usage.completion_tokens,
                'eval_duration': -1,  # Not supported by DS
                'total_tokens': response.usage.total_tokens
            }
        }

        if self.is_reasoner:
            result["reasoning_content"] = response.choices[0].message.reasoning_content
        else:
            result["reasoning_content"] = ""

        return result

    def stream(self, messages: List[Dict[Any, Any]], *args, **kwargs) -> Any:
        """
        Streams responses from DeepSeek API.

        :param messages: List of message dictionaries
        :return: Generator yielding streamed responses
        """
        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
            **kwargs
        )

        for chunk in stream:
            if self.is_reasoner:
                yield {
                    "content": chunk.choices[0].delta.content,
                    "reasoning": self._extract_reasoning(chunk)
                }
            else:
                yield chunk.choices[0].delta.content

    def struct_output(self,
                      messages: List[Dict[Any, Any]],
                      pydantic_model: pydantic.BaseModel,
                      **kwargs) -> Dict[str, Any]:
        """
        Generates structured output conforming to the given Pydantic model.

        :param messages: List of message dictionaries
        :param pydantic_model: Pydantic model class for structured output
        :return: Dictionary with structured message, stats, and reasoning
        """
        # Add instruction to format output as JSON matching the pydantic model
        system_message = {
            "role": "system",
            "content": f"""You MUST output a JSON object that strictly follows this schema: {json.dumps(pydantic_model.model_json_schema())}"""
        }

        # Insert the system message at the beginning
        messages_with_instruction = [system_message] + messages

        # Get the response from DeepSeek
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages_with_instruction,
            response_format={"type": "json_object"},
            **kwargs
        )

        # Parse the JSON content
        try:
            json_content = json.loads(response.choices[0].message.content)
            structured_message = pydantic_model(**json_content)
        except (json.JSONDecodeError, pydantic.ValidationError) as e:
            raise ValueError(f"Failed to parse or validate structured output: {str(e)}")

        # Build the result dictionary
        result = {
            "message": structured_message,
            "stats": {
                'prompt_tokens': response.usage.prompt_tokens,
                'prompt_eval_duration': -1,
                'eval_tokens': response.usage.completion_tokens,
                'eval_duration': -1,
                'total_tokens': response.usage.total_tokens
            }
        }

        # Add reasoning if available
        if self.is_reasoner:
            result["reasoning"] = response.choices[0].message.reasoning_content
        else:
            result["reasoning"] = ""

        return result
