from collections.abc import Iterable
import json
import re
from typing import Any

from app.core.config import Settings


def normalize_sentences(text: str, limit: int = 8) -> list[str]:
    chunks = re.split(r"[\n\r\t\-\*\u2022\.]+", text)
    cleaned = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 8]
    if not cleaned:
        return ["general technical capability"]
    return cleaned[:limit]


def _fallback_summary(prompt: str) -> str:
    return (
        "This test targets role-relevant technical depth, practical implementation quality, "
        "and scenario-based decision making aligned with the JD."
    )


def _extract_text_from_response(response: Any) -> str:
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, Iterable):
        return " ".join(str(part) for part in content).strip()
    return str(content).strip()


def _extract_json_blob(text: str) -> str:
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    object_match = re.search(r"\{[\s\S]*\}", cleaned)
    array_match = re.search(r"\[[\s\S]*\]", cleaned)

    if object_match and array_match:
        return min([object_match.group(0), array_match.group(0)], key=lambda item: cleaned.index(item))
    if object_match:
        return object_match.group(0)
    if array_match:
        return array_match.group(0)
    return cleaned


def generate_with_optional_gemini(prompt: str, settings: Settings) -> str:
    if not settings.google_api_key:
        return _fallback_summary(prompt)

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=settings.temperature,
            google_api_key=settings.google_api_key,
        )
        response = llm.invoke(prompt)
        return _extract_text_from_response(response)
    except Exception:
        return _fallback_summary(prompt)


def generate_json_with_optional_gemini(
    prompt: str,
    settings: Settings,
    fallback_data: dict[str, Any] | list[Any],
) -> dict[str, Any] | list[Any]:
    if not settings.google_api_key:
        return fallback_data

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            temperature=settings.temperature,
            google_api_key=settings.google_api_key,
        )
        response = llm.invoke(prompt)
        text = _extract_text_from_response(response)
        json_blob = _extract_json_blob(text)
        parsed = json.loads(json_blob)
        if isinstance(parsed, (dict, list)):
            return parsed
        return fallback_data
    except Exception:
        return fallback_data
