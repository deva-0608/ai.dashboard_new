from state import DashboardState
from session_store import SessionStore


def memory_agent(state: DashboardState) -> DashboardState:
    """
    Enhanced memory agent that:
    1. Loads persistent session context
    2. Injects chat history and previous chart context
    3. Publishes memory context to A2A bus for other agents
    """

    session_id = state.get("session_id", "default")
    session = SessionStore.get_or_create(session_id)

    # Load persistent state from session
    state["chat_history"] = session.chat_history.copy()
    state["memory"] = session.memory.copy()
    state["filters"] = session.filters.copy()
    state["previous_charts"] = session.previous_charts.copy()
    state["chart_contexts"] = session.chart_contexts.copy()

    # Add current user message to history
    session.add_chat("user", state["prompt"])
    state["chat_history"] = session.chat_history.copy()

    # Publish memory context to A2A bus for other agents
    a2a_bus = state.get("a2a_bus")
    if a2a_bus:
        context_summary = session.get_context_summary()
        a2a_bus.publish(
            sender="memory_agent",
            receiver="all",
            msg_type="memory_context",
            payload={
                "context_summary": context_summary,
                "previous_chart_ids": state["previous_charts"],
                "chart_contexts": state["chart_contexts"][-5:],
                "key_insights": state["memory"].get("key_insights", [])[-5:],
                "active_filters": state["filters"],
            }
        )

    return state
