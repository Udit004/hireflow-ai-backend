from app.graph.workflow import WorkflowState
from app.schemas.response import TestQuestion


def mcq_agent_node(state: WorkflowState) -> WorkflowState:
    payload = state["request"]
    blueprint = state.get("blueprint", {})
    requirements = state.get("key_requirements", ["problem solving"])
    count = int(blueprint.get("mcq", 2))

    items: list[TestQuestion] = []
    for idx in range(count):
        topic = requirements[idx % len(requirements)]
        items.append(
            TestQuestion(
                question_type="mcq",
                question=f"Which approach best demonstrates strong {topic} capability?",
                options=[
                    "Choose the first pattern seen online",
                    "Define constraints and test edge cases",
                    "Skip validation to move faster",
                    "Avoid documenting assumptions",
                ],
                expected_answer="Define constraints and test edge cases",
                difficulty=payload.difficulty,
            )
        )

    return {"mcq_items": items}
