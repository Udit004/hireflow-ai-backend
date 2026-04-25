from app.graph.workflow import WorkflowState
from app.schemas.response import TestQuestion


def quality_critic_node(state: WorkflowState) -> WorkflowState:
    payload = state["request"]
    target_count = payload.question_count

    combined: list[TestQuestion] = []
    combined.extend(state.get("mcq_items", []))
    combined.extend(state.get("code_items", []))
    combined.extend(state.get("scenario_items", []))

    curated = combined[:target_count]

    while len(curated) < target_count:
        curated.append(
            TestQuestion(
                question_type="mcq",
                question="What is your approach to validating assumptions before implementation?",
                options=[
                    "Proceed without validation",
                    "Validate assumptions with data and quick experiments",
                    "Only ask after release",
                    "Wait for blockers",
                ],
                expected_answer="Validate assumptions with data and quick experiments",
                difficulty=payload.difficulty,
            )
        )

    return {"curated_questions": curated}
