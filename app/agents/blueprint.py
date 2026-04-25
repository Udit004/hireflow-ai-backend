from typing import cast

from app.graph.workflow import WorkflowState
from app.schemas.request import JDTestRequest


def _split_question_counts(total: int) -> tuple[int, int]:
    mcq_count = max(1, round(total * 0.7))
    scenario_count = total - mcq_count
    if scenario_count < 1:
        scenario_count = 1
        mcq_count = total - scenario_count
    return mcq_count, scenario_count


def blueprint_node(state: WorkflowState) -> WorkflowState:
    payload = cast(JDTestRequest, state.get("request"))
    if payload is None:
        raise ValueError("Missing required 'request' in workflow state")
    total = payload.question_count
    requirements = state.get("key_requirements", [])
    existing_blueprint = state.get("blueprint", {})

    fallback_focus_topics = [str(item).strip() for item in requirements if str(item).strip()]
    if not fallback_focus_topics:
        fallback_focus_topics = [payload.role_title.strip() or "role fundamentals"]

    fallback_mcq, fallback_scenario = _split_question_counts(total)

    if not isinstance(existing_blueprint, dict):
        existing_blueprint = {}

    mcq_count = fallback_mcq
    scenario_count = fallback_scenario

    parsed_mcq = existing_blueprint.get("mcq")
    parsed_scenario = existing_blueprint.get("scenario")
    if isinstance(parsed_mcq, int) and isinstance(parsed_scenario, int):
        if parsed_mcq >= 1 and parsed_scenario >= 1 and parsed_mcq + parsed_scenario == total:
            mcq_count = parsed_mcq
            scenario_count = parsed_scenario

    raw_topics = existing_blueprint.get("focus_topics", fallback_focus_topics)
    focus_topics = [str(item).strip() for item in raw_topics if str(item).strip()] if isinstance(raw_topics, list) else []
    if not focus_topics:
        focus_topics = fallback_focus_topics

    return {
        "blueprint": {
            "mcq": mcq_count,
            "scenario": scenario_count,
            "focus_topics": focus_topics[:6],
        }
    }
