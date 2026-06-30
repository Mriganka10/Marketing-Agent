from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from app.core.config import Settings


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.can_use_openai else None

    def json_completion(self, *, system: str, user: str, fallback: dict[str, Any]) -> dict[str, Any]:
        if not self.client:
            return fallback
        try:
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0.35,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else fallback
        except Exception:
            return fallback

