import os
from abc import ABC
from openai import OpenAI, RateLimitError, APIError
from dotenv import load_dotenv
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import logging

load_dotenv()
logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, model: str):
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY")
        )
        self.model = model

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def get_completion(self, messages, **kwargs):
        """
        Wrapper for chat.completions.create with built-in retry logic
        for handling Groq Rate Limits (429) & API Errors.
        """
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )

