from app.graph.workflow import WorkflowState
from app.schemas.response import TestQuestion


def scenario_agent_node(state: WorkflowState) -> WorkflowState:
    payload = state["request"]
    blueprint = state.get("blueprint", {})
    requirements = state.get("key_requirements", ["collaboration"])
    count = int(blueprint.get("scenario", 1))

    items: list[TestQuestion] = []
    for idx in range(count):
        topic = requirements[idx % len(requirements)]
        items.append(
            TestQuestion(
                question_type="scenario",
                question=(
                    f"A project deadline is at risk because of gaps in {topic}. "
                    "How would you handle stakeholders, priorities, and delivery quality?"
                ),
                expected_answer=(
                    "Candidate should show communication clarity, prioritization, risk handling, "
                    "and measurable action plan."
                ),
                difficulty=payload.difficulty,
            )
        )

    return {"scenario_items": items}
