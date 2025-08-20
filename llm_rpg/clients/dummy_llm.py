import random
import time
from typing import Dict, List, Any, Generator


class DummyLLM:
    def __init__(self, is_reasoner: bool = False):
        """
        Initialize the DummyLLM.

        :param is_reasoner: Whether to include reasoning in responses
        """
        self.is_reasoner = is_reasoner
        self.total_length = random.randint(20, 80)
        self.word_pool = ["The", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog",
                     "Python", "code", "generation", "example", "streaming", "response",
                     "artificial", "intelligence", "language", "model", "hello", "world"]
        self.sleep_s = 0.05

    def chat(self, messages: List[Dict[Any, Any]], *args, **kwargs):
        """Emulates fake response"""
        prompt_words = 0
        for msg in messages:
            prompt_words += len(msg.split(' '))
        response = {
            'message': self._gen_fake_content(),
            "stats": {
                'prompt_tokens': prompt_words,
                'prompt_eval_duration': random.randint(1, 100),
                'eval_tokens': random.randint(1, prompt_words),
                'eval_duration': random.randint(1, 100),
            }
        }
        return  response

    def _gen_fake_content(self):
        """Generates a fake content by randomly choosing words till the max lenght is reached"""
        content_parts = []
        remaining_length = self.total_length
        while remaining_length > 0:
            word = random.choice(self.word_pool)
            if len(word) + (1 if content_parts else 0) <= remaining_length:
                content_parts.append(word)
                remaining_length -= len(word) + (1 if content_parts else 0)

        return " ".join(content_parts)

    def stream(self, messages: List[Dict[Any, Any]], *args, **kwargs) -> Generator[Any, None, None]:
        """
        Streams dummy responses that emulate an LLM.

        :param messages: List of message dictionaries (ignored in dummy implementation)
        :return: Generator yielding streamed responses
        """

        full_content = self._gen_fake_content()

        # Split into chunks of random size (1-5 characters)
        position = 0
        while position < len(full_content):
            chunk_size = random.randint(1, 5)
            chunk = full_content[position:position + chunk_size]
            position += chunk_size

            # Add small delay to emulate network
            time.sleep(self.sleep_s)

            if self.is_reasoner:
                # For reasoning mode, yield a dictionary
                yield {
                    "content": chunk,
                    "reasoning": f"Dummy reasoning for: '{chunk}'"
                }
            else:
                # Normal mode, just yield the content chunk
                yield chunk