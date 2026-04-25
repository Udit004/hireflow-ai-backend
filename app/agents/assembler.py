from app.core.config import get_settings
from app.graph.workflow import WorkflowState
from app.schemas.response import TestResponse
from app.utils.helpers import generate_with_optional_gemini


def assembler_node(state: WorkflowState) -> WorkflowState:
    payload = state.get("request")
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")

    job_description = getattr(payload, "job_description", None)
    if not isinstance(job_description, str):
        raise ValueError("Missing or invalid 'job_description' in request")

    role_title = getattr(payload, "role_title", None)
    if not isinstance(role_title, str):
        raise ValueError("Missing or invalid 'role_title' in request")

    curated_questions = state.get("curated_questions", [])

    settings = get_settings()
    prompt = (
        "Write a concise summary for an interview test created from this job description: "
        f"{job_description[:1000]}"
    )
    summary = generate_with_optional_gemini(prompt=prompt, settings=settings)

    final_response = TestResponse(
        role_title=role_title,
        summary=summary,
        total_questions=len(curated_questions),
        questions=curated_questions,
    )

    return {"final_response": final_response}
