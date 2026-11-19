import json
import logging

from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Raised when the LLM is unavailable or returns unusable output.

    Callers catch this and fall back to deterministic code paths, so a Groq
    outage or a malformed JSON reply never breaks the chat.
    """


class GroqService:
    def __init__(self):
        self.client = (
            Groq(api_key=settings.groq_api_key, timeout=20.0, max_retries=2)
            if settings.groq_api_key
            else None
        )

    @property
    def available(self) -> bool:
        return self.client is not None

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Return a parsed JSON object, or raise LLMError."""
        if not self.client:
            raise LLMError("GROQ_API_KEY is not configured")
        try:
            response = self.client.chat.completions.create(
                model=settings.groq_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            raw = response.choices[0].message.content
        except Exception as exc:  # network, auth, rate limit, timeout ...
            logger.warning("Groq JSON call failed: %s", exc)
            raise LLMError(f"Groq request failed: {exc}") from exc

        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            logger.warning("Groq returned invalid JSON: %r", raw)
            raise LLMError("Groq returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise LLMError("Groq JSON was not an object")
        return data

    def answer(self, system_prompt: str, user_prompt: str) -> str:
        """Return plain text, or raise LLMError."""
        if not self.client:
            raise LLMError("GROQ_API_KEY is not configured")
        try:
            response = self.client.chat.completions.create(
                model=settings.groq_model,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = (response.choices[0].message.content or "").strip()
        except Exception as exc:
            logger.warning("Groq answer call failed: %s", exc)
            raise LLMError(f"Groq request failed: {exc}") from exc
        if not text:
            raise LLMError("Groq returned an empty answer")
        return text