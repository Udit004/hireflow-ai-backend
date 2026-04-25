from typing import Literal, cast

from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.schemas.response import TestQuestion
from app.utils.helpers import generate_json_with_optional_gemini


DifficultyLevel = Literal["easy", "medium", "hard"]


def _fallback_mcq(topic: str, difficulty: DifficultyLevel) -> TestQuestion:
    return TestQuestion(
        question_type="mcq",
        question=(
            f"A team is building a production feature around '{topic}'. "
            "Which approach best reduces delivery risk while preserving quality?"
        ),
        options=[
            "Skip test planning to accelerate implementation",
            "Define acceptance criteria, test critical paths, and monitor rollout",
            "Rely on ad-hoc manual checks near release",
            "Delay requirement clarification until integration stage",
        ],
        expected_answer="Define acceptance criteria, test critical paths, and monitor rollout",
        difficulty=difficulty,
    )


def _to_mcq(item: object, difficulty: DifficultyLevel, topic: str) -> TestQuestion:
    if not isinstance(item, dict):
        return _fallback_mcq(topic, difficulty)

    question = str(item.get("question", "")).strip()
    options_raw = item.get("options", [])
    expected = str(item.get("expected_answer", "")).strip()

    options = [str(opt).strip() for opt in options_raw if str(opt).strip()] if isinstance(options_raw, list) else []
    if len(options) < 4:
        return _fallback_mcq(topic, difficulty)

    options = options[:4]
    if expected not in options:
        expected = options[0]

    if not question:
        return _fallback_mcq(topic, difficulty)

    return TestQuestion(
        question_type="mcq",
        question=question,
        options=options,
        expected_answer=expected,
        difficulty=difficulty,
    )


def mcq_agent_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")
    blueprint = state.get("blueprint", {})
    requirements = blueprint.get("focus_topics") or state.get("key_requirements", ["problem solving"])
    count = int(blueprint.get("mcq", 2))

    prompt = f"""
You are a senior assessment designer for hiring.
Generate high-quality multiple-choice interview questions from the provided hiring context.

Role: {payload.role_title}
Difficulty: {payload.difficulty}
Question count: {count}
Topics:
{requirements}

Return ONLY JSON with this schema:
{{
  "questions": [
    {{
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "expected_answer": "exactly one option"
    }}
  ]
}}

Rules:
- Questions must test applied judgement, not definition recall.
- Include realistic constraints/trade-offs seen in industry work.
- Avoid trivial wording or obvious distractors.
- Keep each question concise and unambiguous.
- expected_answer must exactly match one option.
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
        topic = str(requirements[idx % len(requirements)]) if requirements else "problem solving"
        item = generated[idx] if idx < len(generated) else {}
        items.append(_to_mcq(item=item, difficulty=payload.difficulty, topic=topic))

    return {"mcq_items": items}
