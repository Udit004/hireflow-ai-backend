from collections.abc import Iterable
import re

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
        if isinstance(response.content, str):
            return response.content.strip()
        if isinstance(response.content, Iterable):
            return " ".join(str(part) for part in response.content).strip()
        return str(response.content).strip()
    except Exception:
        return _fallback_summary(prompt)
