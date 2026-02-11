from state import DashboardState
from utils.llm_factory import LLMFactory
from langchain_core.messages import SystemMessage, HumanMessage
from utils.json_utils import safe_json_loads


INTENT_PROMPT = """
You are an analytics intent classifier.

Given the user's CURRENT question and their PREVIOUS conversation, determine:

1. intent_type: one of [overview, comparison, trend, distribution, correlation, deep-dive, anomaly, duration-analysis]
2. depth: one of [low, medium, high]
3. needs_segmentation: true/false (if comparison between groups is implied)
4. focus_columns: list of columns the user is likely interested in (or empty if general)
5. chart_preference: suggested chart types based on intent (list)
6. kpi_focus: what kind of KPIs to highlight
7. duration_query: true/false — set to true if the user asks about: lagged days, delays, duration, how long, time between dates, overdue, lead time, cycle time

IMPORTANT:
- If the user asks about "lagged days", "duration", "delay", "start to target", "overdue", etc. → set duration_query: true and focus_columns should include any lag/duration column
- If the user references something from a previous message, use the conversation history to understand context
- NEVER suggest using date columns (Start Date, Target Date) as chart metrics. If the user asks about time between dates, they want DURATION (a number), not the date itself.

Return ONLY valid JSON:

{
  "intent_type": "duration-analysis",
  "depth": "medium",
  "needs_segmentation": true,
  "focus_columns": ["Lagged Days"],
  "chart_preference": ["bar", "pie", "scatter"],
  "kpi_focus": "duration_metrics",
  "duration_query": true
}
"""


def intent_agent(state: DashboardState) -> DashboardState:
    llm = LLMFactory.get_llm(temperature=0)

    # Build context with conversation history
    context_parts = [f"Current question: {state['prompt']}"]

    # Include recent conversation history
    chat_history = state.get("chat_history", [])
    if len(chat_history) > 1:
        recent = chat_history[-7:-1]
        if recent:
            context_parts.append("\nPrevious conversation:")
            for m in recent:
                role = m.get("role", "user")
                content = m.get("content", "")[:250]
                context_parts.append(f"  {role}: {content}")

    a2a_bus = state.get("a2a_bus")
    if a2a_bus:
        memory_msgs = a2a_bus.get_all_of_type("memory_context")
        if memory_msgs:
            context_parts.append(f"\nSession context: {memory_msgs[-1]['payload'].get('context_summary', '')}")

        schema_msgs = a2a_bus.get_all_of_type("schema_info")
        if schema_msgs:
            schema_payload = schema_msgs[-1]['payload']
            context_parts.append(f"Data domain: {schema_payload.get('data_domain', 'unknown')}")
            schema = state.get("schema", {})
            context_parts.append(f"Columns: categorical={schema.get('categorical', [])}, numeric={schema.get('numeric', [])}")
            context_parts.append(f"Datetime columns (NOT for y-axis): {schema.get('datetime', [])}")
            context_parts.append(f"EXCLUDED identifiers (never use): {schema.get('identifiers', [])}")

        enrichment_msgs = a2a_bus.get_all_of_type("enrichment_info")
        if enrichment_msgs:
            enr = enrichment_msgs[-1]['payload']
            context_parts.append(f"Key numeric columns for analysis: {enr.get('key_numeric_columns', [])}")
            context_parts.append(f"Derived/duration columns: {[d['column'] for d in enr.get('derived_columns', [])]}")

    response = llm.invoke([
        SystemMessage(content=INTENT_PROMPT),
        HumanMessage(content="\n".join(context_parts))
    ])

    try:
        intent = safe_json_loads(response.content)
    except Exception:
        intent = {
            "intent_type": "overview",
            "depth": "medium",
            "needs_segmentation": False,
            "focus_columns": [],
            "chart_preference": ["bar", "pie", "line"],
            "kpi_focus": "summary_statistics",
            "duration_query": False,
        }

    state["intent"] = intent

    if a2a_bus:
        a2a_bus.publish(
            sender="intent_agent",
            receiver="planner_agent",
            msg_type="intent_info",
            payload=intent
        )

    return state
