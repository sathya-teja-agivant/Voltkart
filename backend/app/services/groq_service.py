import json
from groq import Groq
from app.core.config import settings


class GroqService:
    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.client:
            raise RuntimeError("GROQ_API_KEY is not configured")
        response = self.client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return json.loads(response.choices[0].message.content)

    def answer(self, system_prompt: str, user_prompt: str) -> str:
        if not self.client:
            raise RuntimeError("GROQ_API_KEY is not configured")
        response = self.client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
