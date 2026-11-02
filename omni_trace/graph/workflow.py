import os
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from omni_trace.graph.state import AgentState
from omni_trace.graph.nodes import (
    router_node,
    retriever_node,
    sql_analytics_node,
    synthesis_node,
    critic_node,
    refine_query_node,
    human_approval_node,
    report_node,
    fallback_node
)
from omni_trace.graph.edges import route_after_critic

def build_incident_graph(checkpointer=None, enable_hitl: bool = True):
    """
    Constructs the OmniTrace cyclic StateGraph for autonomous SRE incident triage.
    Supports durable checkpointing and human-in-the-loop interruption gates.
    """
    workflow = StateGraph(AgentState)

    # Register all nodes
    workflow.add_node("router", router_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("sql_analytics", sql_analytics_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("refine_query", refine_query_node)
    workflow.add_node("human_approval_gate", human_approval_node)
    workflow.add_node("report", report_node)
    workflow.add_node("fallback", fallback_node)

    # Parallel branching from router
    workflow.add_edge(START, "router")
    workflow.add_edge("router", "retriever")
    workflow.add_edge("router", "sql_analytics")

    # Converge into synthesis
    workflow.add_edge("retriever", "synthesis")
    workflow.add_edge("sql_analytics", "synthesis")

    # Synthesis into Critic (Self-RAG)
    workflow.add_edge("synthesis", "critic")

    # Conditional routing based on Critic Groundedness & Safety
    workflow.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "human_approval_gate": "human_approval_gate",
            "report": "report",
            "refine_query": "refine_query",
            "fallback": "fallback"
        }
    )

    # Cyclical self-correction edge
    workflow.add_edge("refine_query", "retriever")

    # Terminal edges
    workflow.add_edge("human_approval_gate", "report")
    workflow.add_edge("report", END)
    workflow.add_edge("fallback", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    interrupt_nodes = ["human_approval_gate"] if enable_hitl else []

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_nodes
    )
