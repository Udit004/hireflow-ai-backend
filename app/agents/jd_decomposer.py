from app.graph.workflow import WorkflowState
from app.utils.helpers import normalize_sentences


def jd_decomposer_node(state: WorkflowState) -> WorkflowState:
    payload = state["request"]
    requirements = normalize_sentences(payload.job_description, limit=8)

    return {
        "jd_breakdown": " | ".join(requirements),
        "key_requirements": requirements,
    }
