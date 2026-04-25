from typing import Literal, cast

from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.schemas.response import TestQuestion
from app.utils.helpers import generate_json_with_optional_gemini


DifficultyLevel = Literal["easy", "medium", "hard"]
MAX_QUESTIONS_PER_CALL = 5


_MCQ_FALLBACK_VARIANTS = [
    (
        "A team is shipping a change that affects multiple clients for '{topic}'. Which release approach is safest?",
        [
            "Ship directly to all clients at once",
            "Use a versioned rollout with backward compatibility",
            "Avoid tests to reduce delay",
            "Hide the change behind no feature flag",
        ],
        "Use a versioned rollout with backward compatibility",
    ),
    (
        "An integration for '{topic}' is causing inconsistent behavior in staging. What should the team do first?",
        [
            "Ignore staging and wait for production feedback",
            "Trace the failing path, isolate the regression, and verify assumptions",
            "Rewrite the entire service immediately",
            "Remove the integration without analysis",
        ],
        "Trace the failing path, isolate the regression, and verify assumptions",
    ),
    (
        "A deadline is tight for work involving '{topic}', but quality risk is rising. What is the best next step?",
        [
            "Cut validation entirely to finish faster",
            "Clarify scope, protect critical tests, and agree on trade-offs",
            "Pause all communication until launch day",
            "Ship without checking edge cases",
        ],
        "Clarify scope, protect critical tests, and agree on trade-offs",
    ),
]


def _fallback_mcq(topic: str, difficulty: DifficultyLevel) -> TestQuestion:
    template, options, expected_answer = _MCQ_FALLBACK_VARIANTS[len(topic) % len(_MCQ_FALLBACK_VARIANTS)]
    return TestQuestion(
        question_type="mcq",
        question=template.format(topic=topic),
        options=options,
        expected_answer=expected_answer,
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


def _build_mcq_prompt(payload: JDTestRequest, count: int, topics: list[str]) -> str:
        return f"""
Generate high-quality multiple-choice interview questions.

Role: {payload.role_title}
Difficulty: {payload.difficulty}
Question count: {count}
Topics:
{topics}

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
- Each question must focus on one distinct requirement or decision point.
- Use concrete production constraints, failure modes, or trade-offs.
- Avoid generic stems like 'A team is building a production feature'.
- Avoid repeated phrasing across items.
- Keep each question under 30 words.
- Keep each option under 15 words.
- Do not include full code blocks or full SQL queries.
- expected_answer must exactly match one option.
- Make distractors plausibly wrong, not obviously wrong.
"""


def _chunk_topics(requirements: list[str], start: int, count: int) -> list[str]:
    if not requirements:
        return ["problem solving"]
    return [str(requirements[(start + index) % len(requirements)]) for index in range(count)]


def mcq_agent_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")
    blueprint = state.get("blueprint", {})
    requirements = blueprint.get("focus_topics") or state.get("key_requirements", ["problem solving"])
    count = int(blueprint.get("mcq", 2))
    settings = get_settings()
    items: list[TestQuestion] = []

    for start in range(0, count, MAX_QUESTIONS_PER_CALL):
        batch_count = min(MAX_QUESTIONS_PER_CALL, count - start)
        batch_topics = _chunk_topics(list(requirements), start, batch_count)
        prompt = _build_mcq_prompt(payload, batch_count, batch_topics)
        parsed = generate_json_with_optional_gemini(
            prompt=prompt,
            settings=settings,
            fallback_data={"questions": []},
            max_output_tokens=min(2048, max(800, 260 * batch_count)),
            model=settings.gemini_generation_model,
            temperature=settings.gemini_generation_temperature,
        )

        generated = parsed.get("questions", []) if isinstance(parsed, dict) else []
        for idx in range(batch_count):
            topic = batch_topics[idx] if idx < len(batch_topics) else "problem solving"
            item = generated[idx] if idx < len(generated) else {}
            items.append(_to_mcq(item=item, difficulty=payload.difficulty, topic=topic))

    return {"mcq_items": items}
