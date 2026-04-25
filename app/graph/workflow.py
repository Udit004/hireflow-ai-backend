from typing import TypedDict

from langgraph.graph import END, StateGraph


class WorkflowState(TypedDict, total=False):
    request: object
    jd_breakdown: str
    key_requirements: list[str]
    blueprint: dict
    mcq_items: list
    code_items: list
    scenario_items: list
    curated_questions: list
    final_response: object


def build_workflow():
    from app.agents.assembler import assembler_node
    from app.agents.blueprint import blueprint_node
    from app.agents.code_agent import code_agent_node
    from app.agents.jd_decomposer import jd_decomposer_node
    from app.agents.mcq_agent import mcq_agent_node
    from app.agents.quality_critic import quality_critic_node
    from app.agents.scenario_agent import scenario_agent_node

    graph = StateGraph(WorkflowState)

    graph.add_node("jd_decomposer", jd_decomposer_node)
    graph.add_node("blueprint_step", blueprint_node)
    graph.add_node("mcq_agent", mcq_agent_node)
    graph.add_node("code_agent", code_agent_node)
    graph.add_node("scenario_agent", scenario_agent_node)
    graph.add_node("quality_critic", quality_critic_node)
    graph.add_node("assembler", assembler_node)

    graph.set_entry_point("jd_decomposer")
    graph.add_edge("jd_decomposer", "blueprint_step")
    graph.add_edge("blueprint_step", "mcq_agent")
    graph.add_edge("blueprint_step", "code_agent")
    graph.add_edge("blueprint_step", "scenario_agent")
    graph.add_edge("mcq_agent", "quality_critic")
    graph.add_edge("code_agent", "quality_critic")
    graph.add_edge("scenario_agent", "quality_critic")
    graph.add_edge("quality_critic", "assembler")
    graph.add_edge("assembler", END)

    return graph.compile()
