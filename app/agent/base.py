import logging
import os
import time
from abc import ABC

from dotenv import load_dotenv
from openai import (
    OpenAI,
    RateLimitError,
    APIError,
    APIStatusError,
    APIConnectionError,
)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

load_dotenv()
logger = logging.getLogger(__name__)


def _groq_transient_retry(exc: BaseException) -> bool:
    """
    Do not retry TPM / oversized (413), client quota (429), or other 4xx with the SAME payload.

    Retry only infra-style failures where the identical request might succeed later.
    """
    if isinstance(exc, RateLimitError):
        return False
    if isinstance(exc, APIStatusError):
        if exc.status_code == 413:
            return False
        if exc.status_code == 429:
            return False
        if 400 <= exc.status_code < 500:
            return False
        return exc.status_code >= 500 or exc.status_code == 408
    return isinstance(exc, APIConnectionError)


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
            api_key=self.api_keys[self.current_key_index],
        )
        key_masked = self.api_keys[self.current_key_index][:8] + "..."
        logger.info(
            "Initialized Groq client with key #%s (%s)",
            self.current_key_index + 1,
            key_masked,
        )

    def _rotate_key(self) -> bool:
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            logger.warning(
                "⚠️ Rate limit hit. Switching to API Key #%s...",
                self.current_key_index + 1,
            )
            self._init_client()
            return True
        return False

    @retry(
        retry=retry_if_exception(_groq_transient_retry),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_completion(self, messages, **kwargs):
        """
        chat.completions.create with key rotation on RPM-style 429.

        TPM oversize returns HTTP 413 from Groq with the SAME token estimate —
        swapping keys cannot shrink messages; callers must split/truncate prompts.
        """
        try:
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **kwargs,
            )
        except RateLimitError as e:
            if self._rotate_key():
                pause = float(os.getenv("GROQ_AFTER_KEY_ROTATE_SLEEP", "2") or 0)
                if pause > 0:
                    logger.info("Sleeping %.1fs after Groq API key rotate", pause)
                    time.sleep(pause)
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **kwargs,
                )
            logger.error("Rate limit reached and no other keys available.")
            raise e
        except APIStatusError as e:
            if e.status_code == 429 and self._rotate_key():
                pause = float(os.getenv("GROQ_AFTER_KEY_ROTATE_SLEEP", "2") or 0)
                if pause > 0:
                    logger.info(
                        "Sleeping %.1fs after Groq key rotate (HTTP 429 fallback)",
                        pause,
                    )
                    time.sleep(pause)
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **kwargs,
                )
            raise
