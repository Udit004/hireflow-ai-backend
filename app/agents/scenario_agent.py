from typing import cast

from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.schemas.response import TestQuestion
from app.utils.helpers import generate_json_with_optional_gemini


_SCENARIO_FALLBACK_VARIANTS = [
    (
        "A production change for '{topic}' is ready, but two stakeholders disagree on the launch criteria. How do you proceed?",
        "Candidate should align stakeholders; clarify decision criteria; reduce risk with measurable checkpoints; and document trade-offs.",
    ),
    (
        "A deployment involving '{topic}' is at risk because of an unresolved defect close to release. What is your approach?",
        "Candidate should assess severity; protect the user impact boundary; communicate options; and choose a controlled release path.",
    ),
    (
        "The team is under pressure to ship work related to '{topic}', but the design is still evolving. What do you do?",
        "Candidate should separate must-have from nice-to-have; confirm assumptions; assign ownership; and track decisions visibly.",
    ),
]


def _fallback_scenario(topic: str, difficulty: str) -> TestQuestion:
    template, expected_answer = _SCENARIO_FALLBACK_VARIANTS[len(topic) % len(_SCENARIO_FALLBACK_VARIANTS)]
    return TestQuestion(
        question_type="scenario",
        question=template.format(topic=topic),
        expected_answer=expected_answer,
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


def _build_scenario_prompt(payload: JDTestRequest, count: int, topics: list[str]) -> str:
        return f"""
Generate scenario-based hiring questions.

Role: {payload.role_title}
Difficulty: {payload.difficulty}
Question count: {count}
Topics:
{topics}

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
- Each scenario must probe a different execution or decision skill.
- Include ambiguity, trade-offs, risk, and stakeholder impact.
- Avoid generic behavioral prompts and repeated stems.
- Keep each scenario under 85 words.
- expected_answer must be a 4-point rubric joined by '; '.
- Each rubric point must be under 10 words.
- Make the rubric specific enough to distinguish good from average answers.
"""


def _chunk_topics(requirements: list[str], start: int, count: int) -> list[str]:
    if not requirements:
        return ["collaboration"]
    return [str(requirements[(start + index) % len(requirements)]) for index in range(count)]


def scenario_agent_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")
    blueprint = state.get("blueprint", {})
    requirements = blueprint.get("focus_topics") or state.get("key_requirements", ["collaboration"])
    count = int(blueprint.get("scenario", 1))
    settings = get_settings()
    items: list[TestQuestion] = []

    for start in range(0, count, 5):
        batch_count = min(5, count - start)
        batch_topics = _chunk_topics(list(requirements), start, batch_count)
        prompt = _build_scenario_prompt(payload, batch_count, batch_topics)
        parsed = generate_json_with_optional_gemini(
            prompt=prompt,
            settings=settings,
            fallback_data={"questions": []},
            max_output_tokens=min(2048, max(700, 220 * batch_count)),
            model=settings.gemini_generation_model,
            temperature=settings.gemini_generation_temperature,
        )

        generated = parsed.get("questions", []) if isinstance(parsed, dict) else []
        for idx in range(batch_count):
            topic = batch_topics[idx] if idx < len(batch_topics) else "collaboration"
            item = generated[idx] if idx < len(generated) else {}
            items.append(_to_scenario(item=item, difficulty=payload.difficulty, topic=topic))

    return {"scenario_items": items}
