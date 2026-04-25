from typing import cast

from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.schemas.response import TestQuestion
from app.utils.helpers import generate_json_with_optional_gemini


def _fallback_scenario(topic: str, difficulty: str) -> TestQuestion:
    return TestQuestion(
        question_type="scenario",
        question=(
            f"Your team is responsible for a critical deliverable involving '{topic}', "
            "but timeline and quality goals are in conflict. Describe your approach."
        ),
        expected_answer=(
            "Candidate should prioritize impact, align stakeholders, surface risks early, "
            "and define measurable execution checkpoints."
        ),
        difficulty=difficulty,
    )


def _to_scenario(item: object, difficulty: str, topic: str) -> TestQuestion:
    if not isinstance(item, dict):
        return _fallback_scenario(topic, difficulty)

    question = str(item.get("question", "")).strip()
    expected = str(item.get("expected_answer", "")).strip()

    if not question or not expected:
        return _fallback_scenario(topic, difficulty)

    return TestQuestion(
        question_type="scenario",
        question=question,
        expected_answer=expected,
        difficulty=difficulty,
    )


def scenario_agent_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")
    blueprint = state.get("blueprint", {})
    requirements = blueprint.get("focus_topics") or state.get("key_requirements", ["collaboration"])
    count = int(blueprint.get("scenario", 1))

    prompt = f"""
You are a principal interviewer building scenario-based hiring questions.

Role: {payload.role_title}
Difficulty: {payload.difficulty}
Question count: {count}
Topics:
{requirements}

Return ONLY JSON with this schema:
{{
  "questions": [
    {{
      "question": "scenario prompt",
      "expected_answer": "what an excellent candidate should cover"
    }}
  ]
}}

Rules:
- Scenarios must be realistic and role-relevant.
- Include ambiguity, trade-offs, risk, and stakeholder impact.
- Avoid generic behavioral prompts.
- expected_answer should describe concrete evaluation criteria.
"""
    settings = get_settings()
    parsed = generate_json_with_optional_gemini(
        prompt=prompt,
        settings=settings,
        fallback_data={"questions": []},
    )

    generated = parsed.get("questions", []) if isinstance(parsed, dict) else []
    items: list[TestQuestion] = []
    for idx in range(count):
        topic = str(requirements[idx % len(requirements)]) if requirements else "collaboration"
        item = generated[idx] if idx < len(generated) else {}
        items.append(_to_scenario(item=item, difficulty=payload.difficulty, topic=topic))

    return {"scenario_items": items}
