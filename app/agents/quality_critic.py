from typing import cast

from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.schemas.response import TestQuestion
from app.utils.helpers import generate_json_with_optional_gemini


def _shorten(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= limit else f"{cleaned[:limit].rstrip()}..."


def _question_to_dict(item: TestQuestion) -> dict:
    return {
        "question_type": item.question_type,
        "question": _shorten(item.question, 220),
        "options": [_shorten(option, 80) for option in item.options] if item.options else None,
        "expected_answer": _shorten(item.expected_answer, 220),
        "difficulty": item.difficulty,
    }


def _normalized_question(text: str) -> str:
    return " ".join(text.lower().split())


def _is_weak_question(item: TestQuestion) -> bool:
    if len(item.question.split()) < 8:
        return True
    if item.question_type == "mcq":
        if not item.options or len(item.options) < 4:
            return True
        normalized_options = {_normalized_question(option) for option in item.options if option.strip()}
        if len(normalized_options) < 4:
            return True
        if item.expected_answer not in item.options:
            return True
    if item.question_type == "scenario":
        if len(item.expected_answer.split()) < 8:
            return True
    return False


def _needs_llm_critic(items: list[TestQuestion], target_count: int) -> bool:
    if len(items) < target_count:
        return True

    seen: set[str] = set()
    for item in items[:target_count]:
        key = _normalized_question(item.question)
        if key in seen:
            return True
        seen.add(key)
        if _is_weak_question(item):
            return True

    return False


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


MAX_QUESTIONS_PER_CALL = 5


_PADDING_VARIANTS = [
    (
        "A release is almost ready, but the team discovered conflicting feedback on '{topic}'. How would you decide what to change now versus later?",
        "Candidate should prioritize user impact; validate the risk; align stakeholders on trade-offs; and define a tracked follow-up plan.",
    ),
    (
        "A teammate wants to ship a shortcut around '{topic}' to meet the deadline. What criteria would you use to evaluate that choice?",
        "Candidate should assess correctness; operational risk; maintainability; and whether the shortcut affects users or future changes.",
    ),
    (
        "The team must choose between adding scope and protecting reliability for '{topic}'. How do you drive the decision?",
        "Candidate should compare impact; separate essentials from extras; surface constraints early; and agree on measurable acceptance checks.",
    ),
    (
        "A critical deliverable for '{topic}' is blocked by a late requirement change. What process helps the team move forward?",
        "Candidate should re-scope work; rank options by impact; communicate the trade-off; and track execution with clear owners.",
    ),
]


def _build_critic_prompt(payload: JDTestRequest, requirements: list[str], batch: list[TestQuestion]) -> str:
        return f"""
You are a strict hiring assessment quality reviewer.
Rewrite these questions to be sharper, more varied, and more discriminating.

Role: {payload.role_title}
Difficulty: {payload.difficulty}
Batch size: {len(batch)}
Key requirements:
{requirements}

Input questions:
{[_question_to_dict(item) for item in batch]}

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
- Rewrite every question; do not preserve generic wording.
- Each item must probe a different skill or trade-off.
- Prefer concrete production situations over abstract phrasing.
- Remove trivial, generic, or repetitive questions.
- For mcq, provide exactly 4 concise options and one correct answer.
- Keep mcq question under 30 words and option under 15 words.
- Keep scenario under 85 words.
- Scenario expected_answer must be 4 rubric points joined by '; '.
- Keep the same batch size.
"""


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
    curated: list[TestQuestion] = []

    for start in range(0, len(fallback_curated), MAX_QUESTIONS_PER_CALL):
        batch = fallback_curated[start : start + MAX_QUESTIONS_PER_CALL]
        prompt = _build_critic_prompt(payload, requirements, batch)
        parsed = generate_json_with_optional_gemini(
            prompt=prompt,
            settings=settings,
            fallback_data={"questions": [_question_to_dict(item) for item in batch]},
            max_output_tokens=min(2048, max(800, 240 * len(batch))),
            model=settings.gemini_critic_model,
            temperature=settings.gemini_critic_temperature,
        )

        generated = parsed.get("questions", []) if isinstance(parsed, dict) else []
        batch_curated: list[TestQuestion] = []
        for candidate in generated:
            coerced = _coerce_question(candidate, payload.difficulty)
            if coerced:
                batch_curated.append(coerced)
            if len(batch_curated) == len(batch):
                break

        if len(batch_curated) != len(batch):
            batch_curated = batch

        curated.extend(batch_curated)

    curated = curated[:target_count]

    while len(curated) < target_count:
        added = False
        base_index = len(curated)
        for offset in range(len(_PADDING_VARIANTS)):
            topic = str(requirements[(base_index + offset) % len(requirements)]) if requirements else "delivery trade-offs"
            template, expected_answer = _PADDING_VARIANTS[(base_index + offset) % len(_PADDING_VARIANTS)]
            candidate = TestQuestion(
                question_type="scenario",
                question=template.format(topic=topic),
                expected_answer=expected_answer,
                difficulty=payload.difficulty,
            )
            if any(_normalized_question(existing.question) == _normalized_question(candidate.question) for existing in curated):
                continue
            curated.append(candidate)
            added = True
            break
        if not added:
            break

    return {"curated_questions": curated}
