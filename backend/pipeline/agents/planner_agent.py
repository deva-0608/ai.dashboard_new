from typing import Dict, Any, List
from state import DashboardState
from utils.llm_factory import LLMFactory
from langchain_core.messages import SystemMessage, HumanMessage
from utils.json_utils import safe_json_loads


PLANNER_PROMPT = """
You are a senior BI analytics planner that designs MEANINGFUL, INSIGHTFUL dashboards.

THINK LIKE A DATA ANALYST:
- What STORY does this data tell?
- What COMPARISONS are interesting? (e.g., lagged days by workflow, duration by priority)
- What GROUPINGS reveal patterns? (use hue for stacked/grouped bars)
- Use EXISTING analytical columns (like Lagged Days, Duration, Progress) — these are the GOLD

CRITICAL DATA RULES:
1. NEVER use a datetime/date column as the Y-axis of a bar/line/area chart
   - Date columns (Start Date, Target Date, etc.) are ONLY for x-axis in trend charts
   - If user asks about "lagged days" or "duration", use the Lagged Days / duration NUMERIC column, NOT the date column
2. NEVER use identifier columns (report_id, project_id, id, code, review_id, etc.) for charts
3. Only use columns listed in allowed_columns — check CAREFULLY before using
4. The y-axis MUST be a NUMERIC column with an aggregation function
5. The x-axis should be a CATEGORICAL column (for grouping) or datetime (for trends)

ABOUT HUE (GROUPED CHARTS):
- Use hue for AT LEAST 2-3 charts — grouped bars and multi-line are powerful
- Example: "Average Lagged Days by Workflow, grouped by Priority" → x=Workflow, y=Lagged Days, hue=Priority
- suggested_hue_columns lists the BEST columns for grouping — USE THEM
- Pie charts: NO hue (single dimension only)

ABOUT DERIVED/EXISTING COLUMNS:
- If "Lagged Days" or similar duration column exists, it's the MOST important numeric column
- Use it as y-axis: average/sum/max lagged days by category
- Use bins (like Lagged Days_group) as hue for extra insight

SUPPORTED CHART TYPES (ONLY these exact strings):
"bar", "line", "pie", "scatter", "area", "boxplot", "histogram", "radar", "heatmap", "gauge", "funnel", "treemap"

CHART TYPE GUIDE:
- "boxplot": shows distribution of a numeric column across categories (min, Q1, median, Q3, max, outliers)
  x = categorical column, y = numeric column, aggregation = "raw"
- "histogram": shows frequency distribution of a numeric column (auto-binned)
  x = any column (ignored), y = numeric column, aggregation = "raw", optional hue for grouped histograms
  Add "bins": 10 (or any number) to control bin count

UNSUPPORTED (NEVER USE): violin, waterfall, sankey, sunburst

CHART TITLE RULES:
- Title MUST describe the INSIGHT, matching the actual chart type
- "Average Lagged Days by Workflow" ✓  (bar chart showing avg Lagged Days per Workflow)
- "Boxplot of Sales" ✗ (boxplot is not supported)
- "Target Date by Status" ✗ (can't plot a date as bar height)

JSON FORMAT:
{
  "kpis": [
    {"name": "Business-friendly name", "metric": {"column": "numeric_col", "aggregation": "mean"}}
  ],
  "charts": [
    {
      "id": "unique_id",
      "type": "bar",
      "x": "categorical_column",
      "y": {"column": "NUMERIC_column", "aggregation": "mean"},
      "hue": "grouping_column or null",
      "title": "Descriptive insight title",
      "radar_metrics": ["col1", "col2"],
      "max_value": 100
    }
  ]
}

Return ONLY valid JSON. No explanations.
"""


VALID_CHART_TYPES = {"bar", "line", "pie", "scatter", "area", "boxplot", "histogram", "radar", "heatmap", "gauge", "funnel", "treemap"}

TYPE_FALLBACK = {
    "violin": "boxplot", "waterfall": "bar",
    "donut": "pie", "doughnut": "pie", "stacked_bar": "bar", "stacked_area": "area",
    "grouped_bar": "bar", "column": "bar", "bubble": "scatter",
    "sankey": "funnel", "sunburst": "treemap",
}


def planner_agent(state: DashboardState) -> DashboardState:
    llm = LLMFactory.get_llm(temperature=0.15)
    schema = state.get("schema", {})
    df = state.get("dataframe")

    # Build rich context
    context = {
        "current_question": state["prompt"],
        "allowed_columns": {
            "categorical": schema.get("categorical", []),
            "numeric": schema.get("numeric", []),
            "datetime": schema.get("datetime", []),
        },
        "EXCLUDED_never_use": schema.get("identifiers", []),
        "suggested_hue_columns": schema.get("suggested_hue_columns", []),
        "key_numeric_columns_for_analysis": schema.get("key_numeric_columns", []),
        "key_categorical_columns_for_grouping": schema.get("key_categorical_columns", []),
        "derived_columns_info": schema.get("derived_columns", []),
        "intent": state.get("intent", {}),
        "previous_charts": state.get("previous_charts", []),
        "row_count": len(df) if df is not None else 0,
        "data_domain": schema.get("data_domain", "unknown"),
    }

    # Chat history for context continuity
    chat_history = state.get("chat_history", [])
    if chat_history:
        recent = chat_history[-6:]
        context["conversation_history"] = [
            f"{m['role']}: {m['content'][:300]}" for m in recent
        ]

    # A2A context
    a2a_bus = state.get("a2a_bus")
    if a2a_bus:
        memory_msgs = a2a_bus.get_all_of_type("memory_context")
        if memory_msgs:
            payload = memory_msgs[-1]["payload"]
            context["previous_insights"] = payload.get("key_insights", [])
            context["previous_chart_contexts"] = payload.get("chart_contexts", [])

        intent_msgs = a2a_bus.get_all_of_type("intent_info")
        if intent_msgs:
            context["intent_analysis"] = intent_msgs[-1]["payload"]

        enrichment_msgs = a2a_bus.get_all_of_type("enrichment_info")
        if enrichment_msgs:
            context["enrichment"] = enrichment_msgs[-1]["payload"]

    response = llm.invoke([
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=str(context))
    ])

    try:
        plan = safe_json_loads(response.content)
        plan.setdefault("kpis", [])
        plan.setdefault("charts", [])

        # ── VALIDATION PIPELINE ──
        identifiers = set(schema.get("identifiers", []))
        datetime_cols = set(schema.get("datetime", []))
        numeric_cols = set(schema.get("numeric", []))
        categorical_cols = set(schema.get("categorical", []))

        # 1. Fix chart types
        plan["charts"] = _fix_chart_types(plan["charts"])

        # 2. Fix titles
        plan["charts"] = _fix_chart_titles(plan["charts"])

        # 3. Fix y-axis: must be numeric, never a date
        plan["charts"] = _fix_y_axis(plan["charts"], datetime_cols, numeric_cols, categorical_cols, schema)

        # 4. Strip identifiers
        plan["charts"] = _strip_identifier_charts(plan["charts"], identifiers)
        plan["kpis"] = _strip_identifier_kpis(plan["kpis"], identifiers)

        # 5. Strip KPIs that use date columns
        plan["kpis"] = _strip_date_kpis(plan["kpis"], datetime_cols)

        # 6. Ensure minimums
        if len(plan["kpis"]) < 2:
            plan["kpis"] = _ensure_min_kpis(plan["kpis"], schema)
        if len(plan["charts"]) < 4:
            plan["charts"] = _ensure_min_charts(plan["charts"], schema)

    except Exception as e:
        plan = {"kpis": [], "charts": []}
        state.setdefault("debug", {})
        state["debug"]["planner_error"] = str(e)
        state["debug"]["planner_raw"] = response.content

    state["analysis_plan"] = plan

    if a2a_bus:
        a2a_bus.publish(
            sender="planner_agent", receiver="all", msg_type="plan_info",
            payload={
                "kpi_count": len(plan.get("kpis", [])),
                "chart_count": len(plan.get("charts", [])),
                "chart_types": [c.get("type") for c in plan.get("charts", [])],
            }
        )

    return state


# ============================================================
# Validation Helpers
# ============================================================

def _fix_chart_types(charts: List[dict]) -> List[dict]:
    for c in charts:
        ctype = c.get("type", "bar").lower().strip()
        if ctype not in VALID_CHART_TYPES:
            mapped = TYPE_FALLBACK.get(ctype, "bar")
            print(f"[Planner] Mapped unsupported type '{ctype}' → '{mapped}'")
            c["type"] = mapped
        else:
            c["type"] = ctype
    return charts


def _fix_chart_titles(charts: List[dict]) -> List[dict]:
    wrong_words = {"boxplot", "box plot", "histogram", "violin", "waterfall", "sankey", "sunburst", "bubble"}
    for c in charts:
        title = c.get("title", "")
        title_lower = title.lower()
        for wrong_word in wrong_words:
            if wrong_word in title_lower:
                x = c.get("x", "")
                y_col = c.get("y", {}).get("column", "") if isinstance(c.get("y"), dict) else ""
                hue = c.get("hue")
                parts = [_pretty(y_col), "by", _pretty(x)]
                if hue:
                    parts += ["and", _pretty(hue)]
                c["title"] = " ".join(parts)
                print(f"[Planner] Fixed title: '{title}' → '{c['title']}'")
                break
    return charts


def _fix_y_axis(charts: List[dict], datetime_cols: set, numeric_cols: set,
                categorical_cols: set, schema: dict) -> List[dict]:
    """
    CRITICAL: Ensure y-axis is ALWAYS a numeric column, never a date.
    If a chart uses a date column as y, swap it to the best available numeric column.
    """
    key_numeric = schema.get("key_numeric_columns", [])
    all_numeric = list(numeric_cols)
    fallback_y = key_numeric[0] if key_numeric else (all_numeric[0] if all_numeric else None)

    fixed = []
    for c in charts:
        ctype = c.get("type", "bar")
        y_spec = c.get("y", {})
        y_col = y_spec.get("column", "") if isinstance(y_spec, dict) else ""
        x_col = c.get("x", "")

        # Check if y is a date column → fix it
        if y_col in datetime_cols:
            if fallback_y:
                old_y = y_col
                c["y"] = {"column": fallback_y, "aggregation": "mean"}
                c["title"] = f"Average {_pretty(fallback_y)} by {_pretty(x_col)}"
                if c.get("hue"):
                    c["title"] += f" and {_pretty(c['hue'])}"
                print(f"[Planner] Fixed y-axis: date column '{old_y}' → numeric '{fallback_y}'")
            else:
                continue  # skip this chart entirely

        # Check if x is numeric and y is categorical (swapped)
        if x_col in numeric_cols and y_col in categorical_cols:
            c["x"], c["y"]["column"] = y_col, x_col
            print(f"[Planner] Swapped x/y: x was numeric, y was categorical")

        # Check if y column actually exists in numeric
        if y_col and y_col not in numeric_cols and ctype not in ("gauge", "radar"):
            if y_col not in datetime_cols and fallback_y:
                # Try to use it anyway (might be a derived column)
                pass

        fixed.append(c)
    return fixed


def _strip_identifier_charts(charts: List[dict], identifiers: set) -> List[dict]:
    clean = []
    for c in charts:
        x = c.get("x", "")
        y_col = c.get("y", {}).get("column", "") if isinstance(c.get("y"), dict) else ""
        if x in identifiers or y_col in identifiers:
            continue
        if c.get("hue", "") in identifiers:
            c["hue"] = None
        clean.append(c)
    return clean


def _strip_identifier_kpis(kpis: List[dict], identifiers: set) -> List[dict]:
    return [k for k in kpis if k.get("metric", {}).get("column", "") not in identifiers]


def _strip_date_kpis(kpis: List[dict], datetime_cols: set) -> List[dict]:
    """Remove KPIs that try to aggregate date columns (meaningless)."""
    return [k for k in kpis if k.get("metric", {}).get("column", "") not in datetime_cols]


def _pretty(col_name: str) -> str:
    return col_name.replace("_", " ").replace("  ", " ").title() if col_name else ""


def _ensure_min_kpis(existing_kpis, schema):
    kpis = existing_kpis.copy()
    identifiers = set(schema.get("identifiers", []))
    datetime_cols = set(schema.get("datetime", []))
    key_numeric = schema.get("key_numeric_columns", [])
    numeric = [c for c in key_numeric if c not in identifiers and c not in datetime_cols]
    if not numeric:
        numeric = [c for c in schema.get("numeric", []) if c not in identifiers and c not in datetime_cols]

    agg_types = [("Average", "mean"), ("Total", "sum"), ("Maximum", "max"), ("Count", "count")]
    for col in numeric:
        if len(kpis) >= 2:
            break
        for label, agg in agg_types:
            if len(kpis) >= 2:
                break
            name = f"{label} {_pretty(col)}"
            if not any(k.get("name") == name for k in kpis):
                kpis.append({"name": name, "metric": {"column": col, "aggregation": agg}})
    return kpis


def _ensure_min_charts(existing_charts, schema):
    charts = existing_charts.copy()
    identifiers = set(schema.get("identifiers", []))
    datetime_cols = set(schema.get("datetime", []))
    categorical = [c for c in schema.get("key_categorical_columns", schema.get("categorical", []))
                    if c not in identifiers]
    key_numeric = schema.get("key_numeric_columns", [])
    numeric = [c for c in key_numeric if c not in identifiers and c not in datetime_cols]
    if not numeric:
        numeric = [c for c in schema.get("numeric", []) if c not in identifiers and c not in datetime_cols]
    hue_cols = schema.get("suggested_hue_columns", [])

    if not categorical or not numeric:
        return charts

    existing_ids = {c.get("id") for c in charts}
    hue_col = next((h for h in hue_cols if h != categorical[0]), None)

    templates = [
        {"type": "bar", "id": "auto_bar", "use_hue": True},
        {"type": "pie", "id": "auto_pie", "use_hue": False},
        {"type": "line", "id": "auto_line", "use_hue": True},
        {"type": "area", "id": "auto_area", "use_hue": False},
    ]

    for t in templates:
        if len(charts) >= 4:
            break
        if t["id"] in existing_ids:
            continue

        x_col = categorical[0]
        y_col = numeric[0]
        hue = hue_col if t["use_hue"] and hue_col else None

        title = f"{_pretty(y_col)} by {_pretty(x_col)}"
        if hue:
            title += f" and {_pretty(hue)}"

        charts.append({
            "id": t["id"], "type": t["type"], "x": x_col,
            "y": {"column": y_col, "aggregation": "mean"},
            "hue": hue, "title": title,
        })

    return charts
