from typing import cast

from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.utils.helpers import generate_json_with_optional_gemini, normalize_sentences


def jd_decomposer_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")
    fallback_requirements = normalize_sentences(payload.job_description, limit=8)

    prompt = f"""
You are a senior hiring panel specialist.
Extract the most important, measurable requirements from this job description.

Role title: {payload.role_title}
Difficulty target: {payload.difficulty}
Job description:
{payload.job_description}

Return ONLY JSON with this schema:
{{
  "key_requirements": ["short requirement", "..."]
}}

Rules:
- Return 5 to 10 requirements.
- Each requirement must be specific and testable.
- Avoid generic filler like "good communication" unless the JD clearly emphasizes it.
- Keep each requirement under 14 words.
"""
    settings = get_settings()
    parsed = generate_json_with_optional_gemini(
        prompt=prompt,
        settings=settings,
        fallback_data={"key_requirements": fallback_requirements},
    )

    raw_requirements = parsed.get("key_requirements", []) if isinstance(parsed, dict) else []
    requirements = [str(item).strip() for item in raw_requirements if str(item).strip()]
    if not requirements:
        requirements = fallback_requirements

    return {
        "jd_breakdown": " | ".join(requirements),
        "key_requirements": requirements,
    }
