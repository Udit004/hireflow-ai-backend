from app.graph.workflow import WorkflowState


def blueprint_node(state: WorkflowState) -> WorkflowState:
    payload = state["request"]
    total = payload.question_count

    mcq_count = max(2, total // 2)
    code_count = max(1, total // 4)
    scenario_count = max(1, total - mcq_count - code_count)

    return {
        "blueprint": {
            "mcq": mcq_count,
            "code": code_count,
            "scenario": scenario_count,
            "focus_topics": state.get("key_requirements", []),
        }
    }
