import json
from typing import Any

import httpx

from ion_pulse.core.config import get_settings
from ion_pulse.services.translations import TranslatedContent, Translator, UnconfiguredTranslator


class OpenAiCompatibleTranslator:
    def __init__(self, *, api_base_url: str, api_key: str, model: str) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def translate(
        self,
        *,
        title: str,
        summary: str,
        body: str,
        source_locale: str,
        target_locale: str,
    ) -> TranslatedContent:
        system_prompt = (
            f"Translate the supplied Ion Pulse game-media content from {source_locale} to "
            f"{target_locale}. Preserve meaning, links, and paragraph structure. Return only "
            "JSON with non-empty string fields: title, summary, body. "
            "If body starts with <!-- ion-pulse:blocks -->, preserve that marker and all HTML "
            "tags and attributes exactly; translate only text and image alt descriptions."
        )
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{self.api_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"Title: {title}\nSummary: {summary}\n\nBody:\n{body}",
                        },
                    ],
                },
            )
            response.raise_for_status()
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("Translation provider returned no completion content") from error
        return parse_translation(content)


def parse_translation(content: str) -> TranslatedContent:
    try:
        payload: Any = json.loads(content)
        title = payload["title"]
        summary = payload["summary"]
        body = payload["body"]
    except (TypeError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("Translation provider returned invalid JSON") from error
    if not all(isinstance(value, str) and value.strip() for value in (title, summary, body)):
        raise ValueError("Translation provider returned empty fields")
    return TranslatedContent(title=title, summary=summary, body=body)


def configured_translator() -> Translator:
    settings = get_settings()
    if settings.translation_provider == "openai_compatible" and settings.translation_api_key:
        return OpenAiCompatibleTranslator(
            api_base_url=settings.translation_api_base_url,
            api_key=settings.translation_api_key,
            model=settings.translation_model,
        )
    return UnconfiguredTranslator()
