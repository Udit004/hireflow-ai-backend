from typing import cast

from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.utils.helpers import generate_json_with_optional_gemini, normalize_sentences


def _fallback_blueprint(question_count: int, difficulty: str, requirements: list[str]) -> dict:
    if question_count <= 4:
        scenario_count = 1
    elif difficulty == "hard":
        scenario_count = max(2, round(question_count * 0.35))
    else:
        scenario_count = max(1, round(question_count * 0.25))
    scenario_count = min(scenario_count, question_count - 1)
    mcq_count = question_count - scenario_count

    focus_topics = [item.strip() for item in requirements if item.strip()][:6]
    return {
        "mcq": mcq_count,
        "scenario": scenario_count,
        "focus_topics": focus_topics,
    }


def jd_decomposer_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")
    fallback_requirements = normalize_sentences(payload.job_description, limit=6)
    fallback_plan = {
        "key_requirements": fallback_requirements,
        "blueprint": _fallback_blueprint(
            question_count=payload.question_count,
            difficulty=payload.difficulty,
            requirements=fallback_requirements,
        ),
    }

    prompt = f"""
Extract hiring requirements and create a question blueprint.

Role title: {payload.role_title}
Difficulty target: {payload.difficulty}
Total questions required: {payload.question_count}
Job description:
{payload.job_description}

Return ONLY JSON with this schema:
{{
  "key_requirements": ["requirement", "..."],
  "blueprint": {{
    "mcq": number,
    "scenario": number,
    "focus_topics": ["topic", "..."]
  }}
}}

Rules:
- Return exactly 6 requirements.
- Keep each requirement specific, testable, and under 10 words.
- Prefer technical and role-critical requirements.
- Use only mcq and scenario types.
- Ensure mcq + scenario equals total questions required.
- Keep scenario >= 1.
"""
    settings = get_settings()
    parsed = generate_json_with_optional_gemini(
        prompt=prompt,
        settings=settings,
        fallback_data=fallback_plan,
        max_output_tokens=360,
        model=settings.gemini_planner_model,
        temperature=settings.gemini_planner_temperature,
    )

    raw_requirements = parsed.get("key_requirements", []) if isinstance(parsed, dict) else []
    requirements = [str(item).strip() for item in raw_requirements if str(item).strip()]
    if not requirements:
        requirements = fallback_requirements
    requirements = requirements[:6]

    parsed_blueprint = parsed.get("blueprint", {}) if isinstance(parsed, dict) else {}
    if not isinstance(parsed_blueprint, dict):
        parsed_blueprint = {}

    fallback_from_requirements = _fallback_blueprint(
        question_count=payload.question_count,
        difficulty=payload.difficulty,
        requirements=requirements,
    )
    mcq_count = int(parsed_blueprint.get("mcq", fallback_from_requirements["mcq"]))
    scenario_count = int(parsed_blueprint.get("scenario", fallback_from_requirements["scenario"]))
    if mcq_count < 0:
        mcq_count = 0
    if scenario_count < 0:
        scenario_count = 0
    if mcq_count + scenario_count != payload.question_count:
        scenario_count = fallback_from_requirements["scenario"]
        mcq_count = fallback_from_requirements["mcq"]

    raw_topics = parsed_blueprint.get("focus_topics", requirements)
    focus_topics = [str(item).strip() for item in raw_topics if str(item).strip()] if isinstance(raw_topics, list) else []
    if not focus_topics:
        focus_topics = fallback_from_requirements["focus_topics"]

    return {
        "jd_breakdown": " | ".join(requirements),
        "key_requirements": requirements,
        "blueprint": {
            "mcq": mcq_count,
            "scenario": scenario_count,
            "focus_topics": focus_topics[:6],
        },
    }
