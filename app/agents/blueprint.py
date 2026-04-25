from typing import cast

from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.utils.helpers import generate_json_with_optional_gemini


def blueprint_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")
    total = payload.question_count
    requirements = state.get("key_requirements", [])

    fallback_mcq = max(3, round(total * 0.65))
    fallback_mcq = min(fallback_mcq, total - 1)
    fallback_scenario = max(1, total - fallback_mcq)

    prompt = f"""
You design hiring assessments.
Create a question distribution plan for a generated test.

Role title: {payload.role_title}
Difficulty: {payload.difficulty}
Requested total questions: {total}
Key requirements:
{requirements}

Return ONLY JSON with this schema:
{{
  "mcq": number,
  "scenario": number,
  "focus_topics": ["topic1", "topic2", "..."]
}}

Rules:
- Use only question types mcq and scenario.
- Ensure mcq + scenario equals requested total exactly.
- Keep scenario >= 1.
- Keep mcq >= 3 when total allows.
- Focus topics must be specific and derived from JD requirements.
"""
    settings = get_settings()
    parsed = generate_json_with_optional_gemini(
        prompt=prompt,
        settings=settings,
        fallback_data={
            "mcq": fallback_mcq,
            "scenario": fallback_scenario,
            "focus_topics": requirements,
        },
    )

    mcq_count = int(parsed.get("mcq", fallback_mcq)) if isinstance(parsed, dict) else fallback_mcq
    scenario_count = int(parsed.get("scenario", fallback_scenario)) if isinstance(parsed, dict) else fallback_scenario

    # Repair any malformed count output from the model.
    if mcq_count < 0:
        mcq_count = 0
    if scenario_count < 0:
        scenario_count = 0
    if mcq_count + scenario_count != total:
        scenario_count = max(1, total - max(1, mcq_count))
        mcq_count = total - scenario_count

    raw_topics = parsed.get("focus_topics", requirements) if isinstance(parsed, dict) else requirements
    focus_topics = [str(item).strip() for item in raw_topics if str(item).strip()]
    if not focus_topics:
        focus_topics = requirements

    return {
        "blueprint": {
            "mcq": mcq_count,
            "scenario": scenario_count,
            "focus_topics": focus_topics,
        }
    }
