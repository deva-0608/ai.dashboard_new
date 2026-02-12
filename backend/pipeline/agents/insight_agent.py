from state import DashboardState
from utils.llm_factory import LLMFactory
from langchain_core.messages import SystemMessage, HumanMessage
from session_store import SessionStore
from utils.json_utils import safe_json_loads


INSIGHT_PROMPT = """
You are a senior business intelligence analyst writing an executive summary.

Given the dashboard data (KPIs, chart aggregations, and previous context),
write a clear, actionable summary for a business user.

Requirements:
1. Start with a one-line headline insight
2. Highlight 2-3 key patterns or findings
3. Point out any anomalies or notable trends
4. Keep it concise (max 200 words)
5. Use bullet points for clarity
6. Reference specific numbers from the KPIs

Do NOT mention technical details like chart types or aggregation methods.
Focus on BUSINESS meaning.
"""


SUGGEST_PROMPT = """
You are an AI analytics assistant. Given the data schema and the user's current
question, suggest 3-5 SHORT follow-up questions the user might want to ask next.

These should be:
- Directly relevant to the available columns and data
- Different from the question just asked — explore NEW angles
- Actionable: each should produce interesting charts or KPIs
- Concise: max 10 words each
- Diverse: mix of trends, comparisons, distributions, correlations

AVAILABLE COLUMNS:
{columns_info}

NUMERIC COLUMNS (good for metrics/Y-axis): {numeric_cols}
CATEGORICAL COLUMNS (good for grouping/X-axis): {categorical_cols}
DATE COLUMNS: {date_cols}
DERIVED/ENRICHED COLUMNS: {derived_cols}
HUE CANDIDATES (good for grouped analysis): {hue_cols}

USER JUST ASKED: "{user_prompt}"
CHARTS JUST GENERATED: {chart_types}

Return ONLY a JSON array of 3-5 strings. Example:
["Compare sales by region", "Show monthly trend of revenue", "Distribution of customer ages"]
"""


def _build_suggest_context(state: DashboardState) -> dict:
    """Build context dict for the suggestion prompt."""
    schema = state.get("schema", {})
    a2a_bus = state.get("a2a_bus")

    # Column lists from schema
    numeric_cols = schema.get("numeric", [])
    categorical_cols = schema.get("categorical", [])
    date_cols = schema.get("datetime", [])

    # Enrichment info from A2A bus
    derived_cols = []
    hue_cols = []
    if a2a_bus:
        enrichment_msgs = a2a_bus.get_all_of_type("enrichment_info")
        if enrichment_msgs:
            payload = enrichment_msgs[-1].get("payload", {})
            raw_derived = payload.get("derived_columns", [])
            # derived_columns is List[Dict] with {"column": ..., "formula": ...}
            derived_cols = [
                d.get("column", "") if isinstance(d, dict) else str(d)
                for d in raw_derived
            ]
            hue_cols = payload.get("suggested_hue_columns", [])
            # Merge enrichment numeric/categorical
            numeric_cols = list(set(numeric_cols + payload.get("key_numeric_columns", [])))
            categorical_cols = list(set(categorical_cols + payload.get("key_categorical_columns", [])))

    # All columns
    df = state.get("dataframe")
    all_cols = list(df.columns) if df is not None else []

    # Chart types just generated
    charts = state.get("charts", [])
    chart_types = [c.get("type", "unknown") for c in charts]

    return {
        "columns_info": ", ".join(all_cols[:30]),
        "numeric_cols": ", ".join(numeric_cols[:15]) or "none",
        "categorical_cols": ", ".join(categorical_cols[:10]) or "none",
        "date_cols": ", ".join(date_cols[:5]) or "none",
        "derived_cols": ", ".join(derived_cols[:10]) or "none",
        "hue_cols": ", ".join(hue_cols[:6]) or "none",
        "user_prompt": state.get("prompt", ""),
        "chart_types": ", ".join(chart_types) or "none",
    }


def _generate_suggested_prompts(state: DashboardState) -> list:
    """Use LLM to produce 3-5 contextual follow-up prompts."""
    try:
        llm = LLMFactory.get_llm(temperature=0.7)
        ctx = _build_suggest_context(state)
        prompt_text = SUGGEST_PROMPT.format(**ctx)

        response = llm.invoke([
            SystemMessage(content="You produce JSON arrays only."),
            HumanMessage(content=prompt_text),
        ])

        suggestions = safe_json_loads(response.content)

        if isinstance(suggestions, list):
            # Filter: keep only strings, max 5
            suggestions = [s.strip() for s in suggestions if isinstance(s, str) and s.strip()]
            return suggestions[:5]

        return []
    except Exception as e:
        print(f"[Insight] Suggestion generation failed: {e}")
        return _fallback_suggestions(state)


def _fallback_suggestions(state: DashboardState) -> list:
    """Deterministic fallback if LLM suggestion fails."""
    schema = state.get("schema", {})
    numeric = schema.get("numeric", [])
    categorical = schema.get("categorical", [])
    prompts = []

    if numeric and categorical:
        prompts.append(f"Show {numeric[0]} by {categorical[0]}")
    if len(numeric) >= 2:
        prompts.append(f"Correlation between {numeric[0]} and {numeric[1]}")
    if categorical:
        prompts.append(f"Distribution across {categorical[0]}")
    if numeric:
        prompts.append(f"Trend analysis of {numeric[0]}")
    prompts.append("Give me a complete overview of this data")

    return prompts[:5]


def insight_agent(state: DashboardState) -> DashboardState:
    llm = LLMFactory.get_llm(temperature=0.4)

    # Build rich context for insight generation
    context_parts = []

    # KPIs
    kpis = state.get("kpis", [])
    if kpis:
        kpi_text = ", ".join([f"{k['name']}: {k['value']}" for k in kpis if k.get('value') is not None])
        context_parts.append(f"KPIs: {kpi_text}")

    # Aggregated data summary
    agg_data = state.get("aggregated_data", {})
    for cid, data in agg_data.items():
        if isinstance(data, dict) and "error" in data:
            continue
        import pandas as pd
        if isinstance(data, pd.DataFrame):
            context_parts.append(f"Chart '{cid}': {len(data)} data points, columns: {list(data.columns)}")
        elif isinstance(data, dict):
            context_parts.append(f"Chart '{cid}': {data}")

    # A2A context
    a2a_bus = state.get("a2a_bus")
    if a2a_bus:
        memory_msgs = a2a_bus.get_all_of_type("memory_context")
        if memory_msgs:
            prev_insights = memory_msgs[-1]["payload"].get("key_insights", [])
            if prev_insights:
                context_parts.append(f"Previous session insights: {prev_insights[-3:]}")

    # User question
    context_parts.append(f"User asked: {state['prompt']}")

    response = llm.invoke([
        SystemMessage(content=INSIGHT_PROMPT),
        HumanMessage(content="\n".join(context_parts))
    ])

    state["summary"] = response.content

    # ── Generate follow-up suggestions ──
    state["suggested_prompts"] = _generate_suggested_prompts(state)

    # Save insight to session memory
    session_id = state.get("session_id", "default")
    session = SessionStore.get_or_create(session_id)

    # Store AI response in chat history
    session.add_chat("assistant", response.content)

    # Extract and store key insight (first line)
    first_line = response.content.strip().split("\n")[0][:200]
    session.add_insight(first_line)

    # Store chart contexts in session
    for chart in state.get("charts", []):
        chart_option = chart.get("option", {})
        session.add_chart_context(
            chart_id=chart.get("id", ""),
            chart_type=chart.get("type", "unknown"),
            title=chart_option.get("title", {}).get("text", ""),
            columns_used=[]
        )

    return state
