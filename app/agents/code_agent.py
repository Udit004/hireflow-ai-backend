from app.graph.workflow import WorkflowState
from app.schemas.response import TestQuestion


def code_agent_node(state: WorkflowState) -> WorkflowState:
    payload = state["request"]
    blueprint = state.get("blueprint", {})
    requirements = state.get("key_requirements", ["backend development"])
    count = int(blueprint.get("code", 1))

    items: list[TestQuestion] = []
    for idx in range(count):
        topic = requirements[idx % len(requirements)]
        items.append(
            TestQuestion(
                question_type="code",
                question=(
                    f"Write a clean, testable Python function for '{topic}' that includes "
                    "input validation and clear error handling."
                ),
                expected_answer=(
                    "Candidate should provide modular code, tests or test strategy, and discuss "
                    "time/space complexity and edge cases."
                ),
                difficulty=payload.difficulty,
            )
        )

    return {"code_items": items}
