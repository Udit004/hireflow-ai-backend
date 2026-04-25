from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest
from app.schemas.response import TestResponse
from typing import cast


def assembler_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")

    role_title = payload.role_title

    curated_questions = state.get("curated_questions", [])
    mcq_count = sum(1 for item in curated_questions if getattr(item, "question_type", "") == "mcq")
    scenario_count = sum(1 for item in curated_questions if getattr(item, "question_type", "") == "scenario")

    blueprint = state.get("blueprint", {})
    topics = blueprint.get("focus_topics", []) if isinstance(blueprint, dict) else []
    cleaned_topics = [str(topic).strip() for topic in topics if str(topic).strip()]
    topic_summary = ", ".join(cleaned_topics[:4]) if cleaned_topics else "role-critical skills"

    summary = (
        f"Assessment for {role_title}: {mcq_count} MCQ and {scenario_count} scenario questions, "
        f"calibrated for {payload.difficulty} difficulty and focused on {topic_summary}."
    )

    final_response = TestResponse(
        role_title=role_title,
        summary=summary,
        total_questions=len(curated_questions),
        questions=curated_questions,
    )

    return {"final_response": final_response}
