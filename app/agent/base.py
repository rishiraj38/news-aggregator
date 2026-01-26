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
        self.api_keys = [
            key for key in [os.getenv("GROQ_API_KEY"), os.getenv("GROQ_API_KEY2")]
            if key
        ]
        if not self.api_keys:
             raise ValueError("No GROQ_API_KEY or GROQ_API_KEY2 found in environment.")
        
        self.current_key_index = 0
        self.model = model
        self._init_client()

    def _init_client(self):
        self.client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=self.api_keys[self.current_key_index]
        )
        # Log safely (mask key)
        key_masked = self.api_keys[self.current_key_index][:8] + "..."
        logger.info(f"Initialized Groq client with key #{self.current_key_index + 1} ({key_masked})")

    def _rotate_key(self):
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            logger.warning(f"⚠️ Rate Limit hit. Switching to API Key #{self.current_key_index + 1}...")
            self._init_client()
            return True
        return False

    @retry(
        retry=retry_if_exception_type(APIError),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def get_completion(self, messages, **kwargs):
        """
        Wrapper for chat.completions.create with manual failover for Rate Limits
        and Tenacity retry for other API Errors.
        """
        try:
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs
            )
        except RateLimitError as e:
            # Try switching key
            if self._rotate_key():
                # Retry immediately with new key
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **kwargs
                )
            else:
                # No keys left or single key, re-raise to let Tenacity/Caller handle it
                logger.error("Rate limit reached and no other keys available.")
                raise e

