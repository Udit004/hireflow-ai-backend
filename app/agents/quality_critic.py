from typing import cast

from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.schemas.response import TestQuestion
from app.utils.helpers import generate_json_with_optional_gemini


def _question_to_dict(item: TestQuestion) -> dict:
    return {
        "question_type": item.question_type,
        "question": item.question,
        "options": item.options,
        "expected_answer": item.expected_answer,
        "difficulty": item.difficulty,
    }


def _coerce_question(item: object, difficulty: str) -> TestQuestion | None:
    if not isinstance(item, dict):
        return None

    question_type = str(item.get("question_type", "")).strip().lower()
    question = str(item.get("question", "")).strip()
    expected = str(item.get("expected_answer", "")).strip()
    if question_type not in {"mcq", "scenario"}:
        return None
    if not question or not expected:
        return None

    if question_type == "mcq":
        options_raw = item.get("options", [])
        if not isinstance(options_raw, list):
            return None
        options = [str(opt).strip() for opt in options_raw if str(opt).strip()]
        if len(options) < 4:
            return None
        options = options[:4]
        if expected not in options:
            expected = options[0]
        return TestQuestion(
            question_type="mcq",
            question=question,
            options=options,
            expected_answer=expected,
            difficulty=difficulty,
        )

    return TestQuestion(
        question_type="scenario",
        question=question,
        expected_answer=expected,
        difficulty=difficulty,
    )


def quality_critic_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")
    target_count = payload.question_count
    requirements = state.get("key_requirements", [])

    combined: list[TestQuestion] = []
    combined.extend(state.get("mcq_items", []))
    combined.extend(state.get("scenario_items", []))

    fallback_curated = combined[:target_count]

    settings = get_settings()
    prompt = f"""
You are a strict hiring assessment quality reviewer.
Evaluate and improve the following generated interview questions.

Role: {payload.role_title}
Difficulty: {payload.difficulty}
Target total questions: {target_count}
Key requirements:
{requirements}

Input questions:
{[_question_to_dict(item) for item in combined]}

Return ONLY JSON with this schema:
{{
  "questions": [
    {{
      "question_type": "mcq or scenario",
      "question": "...",
      "options": ["A", "B", "C", "D"],
      "expected_answer": "..."
    }}
  ]
}}

Rules:
- Keep only mcq and scenario questions.
- Remove trivial or repetitive questions.
- Rewrite weak items to be industry-relevant and non-obvious.
- For mcq, provide exactly 4 high-quality options and one correct answer.
- Output exactly target total questions.
"""
    parsed = generate_json_with_optional_gemini(
        prompt=prompt,
        settings=settings,
        fallback_data={"questions": [_question_to_dict(item) for item in fallback_curated]},
    )

    generated = parsed.get("questions", []) if isinstance(parsed, dict) else []
    curated: list[TestQuestion] = []
    for candidate in generated:
        coerced = _coerce_question(candidate, payload.difficulty)
        if coerced:
            curated.append(coerced)
        if len(curated) == target_count:
            break

    if not curated:
        curated = fallback_curated

    while len(curated) < target_count:
        curated.append(
            TestQuestion(
                question_type="scenario",
                question=(
                    "A critical release is at risk after late requirement changes from multiple "
                    "stakeholders. What decision process would you use to protect quality and timeline?"
                ),
                expected_answer=(
                    "Candidate should define prioritization criteria, align stakeholders on trade-offs, "
                    "mitigate key risks, and track execution with measurable checkpoints."
                ),
                difficulty=payload.difficulty,
            )
        )

    return {"curated_questions": curated}
