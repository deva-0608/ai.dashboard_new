from typing import Dict, Any, List, Set
from state import DashboardState
from utils.llm_factory import LLMFactory
from langchain_core.messages import SystemMessage, HumanMessage
from utils.json_utils import safe_json_loads
import random


PLANNER_PROMPT = """
You are a senior BI analytics planner that designs MEANINGFUL, DIVERSE, INSIGHTFUL dashboards.

████████████████████████████████████████████████████████████
  MANDATORY DIVERSITY — YOUR DASHBOARD MUST HAVE ALL OF THESE
████████████████████████████████████████████████████████████

Every dashboard MUST include AT LEAST these DIFFERENT patterns:

1. **CATEGORICAL DISTRIBUTION** (1-2 charts)
   - Type: "pie" or "funnel"
   - Shows count/proportion of rows per category
   - x = categorical column, y = {"column": same_categorical_column, "aggregation": "count"}
   - NO hue for pie charts
   - Example: "Distribution of Workflow Types" → pie chart counting each Workflow

2. **NUMERIC vs CATEGORICAL** (2-3 charts)
   - Type: "bar", "line", "area", "boxplot"
   - Shows a numeric metric grouped by a category
   - x = categorical, y = numeric with aggregation (mean/sum/max)
   - ⚠️ USE DIFFERENT numeric columns across these charts — do NOT repeat the same Y column
   - Example: "Average Lagged Days by Priority" → bar

3. **NUMERIC vs NUMERIC** (1-2 charts)
   - Type: "scatter"
   - Shows relationship/correlation between TWO numeric columns
   - x = numeric_column_1, y = {"column": "numeric_column_2", "aggregation": "raw"}
   - BOTH axes must be numeric
   - Example: "Correlation of Duration vs Lagged Days"

4. **DISTRIBUTION ANALYSIS** (1 chart)
   - Type: "histogram" or "boxplot"
   - Shows how a numeric column is distributed
   - histogram: x = any, y = {"column": "numeric_col", "aggregation": "raw"}, add "bins": 10-15
   - boxplot: x = categorical, y = {"column": "numeric_col", "aggregation": "raw"}
   - Example: "Distribution of Lagged Days" → histogram

5. **GROUPED/HUE CHART** (1-2 charts)
   - Type: "bar", "line", or "area" WITH a hue column
   - Shows comparison across two dimensions
   - Use suggested_hue_columns for the hue parameter
   - Example: "Average Duration by Workflow, grouped by Priority"

████████████████████████████████████████████████████████████
  Y-AXIS COLUMN ROTATION — CRITICAL
████████████████████████████████████████████████████████████

- You have multiple numeric columns available — USE THEM
- Do NOT use the same numeric column as Y-axis for more than 2 charts
- Spread analysis across different metrics
- Example: if you have [Lagged Days, Duration, Progress, Score],
  chart1: y=Lagged Days, chart2: y=Duration, chart3: y=Progress, chart4: y=Score

████████████████████████████████████████████████████████████
  CRITICAL DATA RULES
████████████████████████████████████████████████████████████

1. NEVER use a datetime/date column as the Y-axis of a bar/line/area chart
   - Date columns are ONLY for x-axis in trend charts
2. NEVER use identifier columns (report_id, project_id, etc.)
3. Only use columns listed in allowed_columns
4. For scatter: BOTH x and y must be NUMERIC columns, aggregation = "raw"
5. For pie: y aggregation should be "count", the column can be same as x
6. For histogram: y aggregation = "raw", add "bins" field
7. For boxplot: y aggregation = "raw"

SUPPORTED CHART TYPES:
"bar", "line", "pie", "scatter", "area", "boxplot", "histogram", "radar", "heatmap", "gauge", "funnel", "treemap"

UNSUPPORTED (NEVER USE): violin, waterfall, sankey, sunburst

MINIMUM: 2-4 KPIs + 5-7 charts (diverse types!)

JSON FORMAT:
{
  "kpis": [
    {"name": "Business-friendly name", "metric": {"column": "numeric_col", "aggregation": "mean"}}
  ],
  "charts": [
    {
      "id": "unique_id",
      "type": "bar|line|pie|scatter|area|boxplot|histogram|radar|heatmap|gauge|funnel|treemap",
      "x": "column_name",
      "y": {"column": "NUMERIC_column", "aggregation": "mean|sum|count|raw|max|min"},
      "hue": "grouping_column or null",
      "title": "Descriptive insight title",
      "bins": 10
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

# Chart patterns for diversity tracking
PATTERN_CATEGORICAL_DIST = "categorical_distribution"  # pie, funnel with count
PATTERN_NUMERIC_VS_CAT = "numeric_vs_categorical"      # bar, line, area, boxplot with cat x, num y
PATTERN_NUMERIC_VS_NUMERIC = "numeric_vs_numeric"       # scatter
PATTERN_DISTRIBUTION = "distribution"                    # histogram, boxplot
PATTERN_GROUPED = "grouped_hue"                          # any chart with hue


def _classify_chart_pattern(chart: dict) -> Set[str]:
    """Classify what diversity patterns a chart satisfies."""
    patterns = set()
    ctype = chart.get("type", "bar")
    y_spec = chart.get("y", {})
    agg = y_spec.get("aggregation", "mean") if isinstance(y_spec, dict) else "mean"
    hue = chart.get("hue")

    if ctype in ("pie", "funnel") and agg == "count":
        patterns.add(PATTERN_CATEGORICAL_DIST)
    if ctype == "scatter":
        patterns.add(PATTERN_NUMERIC_VS_NUMERIC)
    if ctype == "histogram":
        patterns.add(PATTERN_DISTRIBUTION)
    if ctype == "boxplot":
        patterns.add(PATTERN_DISTRIBUTION)
        patterns.add(PATTERN_NUMERIC_VS_CAT)
    if ctype in ("bar", "line", "area") and agg != "count":
        patterns.add(PATTERN_NUMERIC_VS_CAT)
    if ctype in ("bar", "line", "area") and agg == "count" and not hue:
        patterns.add(PATTERN_CATEGORICAL_DIST)
    if hue:
        patterns.add(PATTERN_GROUPED)

    return patterns


def planner_agent(state: DashboardState) -> DashboardState:
    llm = LLMFactory.get_llm(temperature=0.2)
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

        # 6. ★ ENFORCE DIVERSITY — inject missing chart patterns ★
        plan["charts"] = _enforce_diversity(plan["charts"], schema)

        # 7. ★ ENFORCE Y-COLUMN ROTATION — limit same Y usage ★
        plan["charts"] = _enforce_y_rotation(plan["charts"], schema)

        # 8. Ensure minimums
        if len(plan["kpis"]) < 2:
            plan["kpis"] = _ensure_min_kpis(plan["kpis"], schema)
        if len(plan["charts"]) < 5:
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
# Diversity Enforcement
# ============================================================

def _enforce_diversity(charts: List[dict], schema: dict) -> List[dict]:
    """
    Analyze the existing charts for diversity gaps and inject missing patterns.
    Ensures we have:
    - At least 1 categorical distribution (pie/funnel)
    - At least 1 numeric-vs-numeric (scatter)
    - At least 1 distribution chart (histogram/boxplot)
    - At least 1 grouped (hue) chart
    """
    identifiers = set(schema.get("identifiers", []))
    datetime_cols = set(schema.get("datetime", []))
    numeric = [c for c in schema.get("key_numeric_columns", schema.get("numeric", []))
               if c not in identifiers and c not in datetime_cols]
    categorical = [c for c in schema.get("key_categorical_columns", schema.get("categorical", []))
                   if c not in identifiers]
    hue_cols = schema.get("suggested_hue_columns", [])

    if not numeric or not categorical:
        return charts

    # Determine which patterns exist
    all_patterns = set()
    for c in charts:
        all_patterns |= _classify_chart_pattern(c)

    existing_ids = {c.get("id") for c in charts}

    # Track which y-columns are already used
    used_y_cols = [c.get("y", {}).get("column", "") if isinstance(c.get("y"), dict) else ""
                   for c in charts]

    # Pick y-columns that are LESS used
    def pick_fresh_numeric(exclude=None):
        """Pick a numeric column that's used least."""
        from collections import Counter
        counts = Counter(used_y_cols)
        candidates = [n for n in numeric if n != exclude]
        if not candidates:
            candidates = numeric
        candidates.sort(key=lambda n: counts.get(n, 0))
        return candidates[0] if candidates else numeric[0]

    injected = []

    # ─── MISSING: Categorical distribution (pie) ───
    if PATTERN_CATEGORICAL_DIST not in all_patterns:
        cat = categorical[0]
        chart_id = "auto_pie_dist"
        if chart_id not in existing_ids:
            injected.append({
                "id": chart_id, "type": "pie", "x": cat,
                "y": {"column": cat, "aggregation": "count"},
                "hue": None,
                "title": f"Distribution of {_pretty(cat)}",
            })
            all_patterns.add(PATTERN_CATEGORICAL_DIST)
            print(f"[Planner] Injected: pie distribution for '{cat}'")

    # Add a SECOND categorical distribution if we have multiple categorical cols
    if len(categorical) >= 2:
        has_second_pie = any(
            c.get("type") in ("pie", "funnel") and c.get("x") != categorical[0]
            for c in charts + injected
        )
        if not has_second_pie:
            cat2 = categorical[1]
            chart_id = "auto_pie_dist_2"
            if chart_id not in existing_ids:
                injected.append({
                    "id": chart_id, "type": "pie", "x": cat2,
                    "y": {"column": cat2, "aggregation": "count"},
                    "hue": None,
                    "title": f"Distribution of {_pretty(cat2)}",
                })
                print(f"[Planner] Injected: 2nd pie distribution for '{cat2}'")

    # ─── MISSING: Numeric vs Numeric (scatter) ───
    if PATTERN_NUMERIC_VS_NUMERIC not in all_patterns and len(numeric) >= 2:
        n1, n2 = numeric[0], numeric[1]
        chart_id = "auto_scatter"
        if chart_id not in existing_ids:
            injected.append({
                "id": chart_id, "type": "scatter", "x": n1,
                "y": {"column": n2, "aggregation": "raw"},
                "hue": None,
                "title": f"{_pretty(n1)} vs {_pretty(n2)} Correlation",
            })
            all_patterns.add(PATTERN_NUMERIC_VS_NUMERIC)
            print(f"[Planner] Injected: scatter '{n1}' vs '{n2}'")

    # ─── MISSING: Distribution (histogram) ───
    if PATTERN_DISTRIBUTION not in all_patterns and numeric:
        dist_col = pick_fresh_numeric()
        chart_id = "auto_histogram"
        if chart_id not in existing_ids:
            injected.append({
                "id": chart_id, "type": "histogram", "x": dist_col,
                "y": {"column": dist_col, "aggregation": "raw"},
                "hue": None, "bins": 12,
                "title": f"Distribution of {_pretty(dist_col)}",
            })
            all_patterns.add(PATTERN_DISTRIBUTION)
            print(f"[Planner] Injected: histogram for '{dist_col}'")

    # ─── MISSING: Grouped/hue chart ───
    if PATTERN_GROUPED not in all_patterns and hue_cols and categorical:
        hue_col = hue_cols[0]
        x_col = next((c for c in categorical if c != hue_col), categorical[0])
        y_col = pick_fresh_numeric()
        chart_id = "auto_grouped_bar"
        if chart_id not in existing_ids:
            injected.append({
                "id": chart_id, "type": "bar", "x": x_col,
                "y": {"column": y_col, "aggregation": "mean"},
                "hue": hue_col,
                "title": f"Average {_pretty(y_col)} by {_pretty(x_col)} and {_pretty(hue_col)}",
            })
            all_patterns.add(PATTERN_GROUPED)
            print(f"[Planner] Injected: grouped bar '{y_col}' by '{x_col}' hue '{hue_col}'")

    return charts + injected


def _enforce_y_rotation(charts: List[dict], schema: dict) -> List[dict]:
    """
    If the same numeric column is used as Y for too many charts (>2),
    replace some with other available numeric columns.
    """
    from collections import Counter
    identifiers = set(schema.get("identifiers", []))
    datetime_cols = set(schema.get("datetime", []))
    numeric = [c for c in schema.get("key_numeric_columns", schema.get("numeric", []))
               if c not in identifiers and c not in datetime_cols]

    if len(numeric) < 2:
        return charts  # not enough columns to rotate

    y_cols = []
    for c in charts:
        y_spec = c.get("y", {})
        y_col = y_spec.get("column", "") if isinstance(y_spec, dict) else ""
        y_cols.append(y_col)

    counts = Counter(y_cols)
    overused = {col for col, cnt in counts.items() if cnt > 2 and col in numeric}

    if not overused:
        return charts

    # Find underused numeric columns
    underused = [n for n in numeric if counts.get(n, 0) < 2]
    if not underused:
        return charts

    result = []
    fix_idx = 0
    for c in charts:
        y_spec = c.get("y", {})
        y_col = y_spec.get("column", "") if isinstance(y_spec, dict) else ""

        if y_col in overused and counts[y_col] > 2 and fix_idx < len(underused):
            # Only replace non-scatter, non-histogram, non-boxplot (those need specific columns)
            ctype = c.get("type", "bar")
            if ctype in ("bar", "line", "area"):
                new_y = underused[fix_idx]
                old_y = y_col
                c["y"] = {"column": new_y, "aggregation": y_spec.get("aggregation", "mean")}
                x_col = c.get("x", "")
                hue = c.get("hue")
                c["title"] = f"Average {_pretty(new_y)} by {_pretty(x_col)}"
                if hue:
                    c["title"] += f" and {_pretty(hue)}"
                counts[old_y] -= 1
                counts[new_y] = counts.get(new_y, 0) + 1
                fix_idx += 1
                print(f"[Planner] Y-rotation: replaced '{old_y}' → '{new_y}' in {ctype} chart")

        result.append(c)
    return result


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
    wrong_words = {"boxplot", "box plot", "violin", "waterfall", "sankey", "sunburst", "bubble"}
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
    Exception: scatter needs numeric x AND y, pie can use count.
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
        if y_col in datetime_cols and ctype not in ("pie",):
            if fallback_y:
                old_y = y_col
                c["y"] = {"column": fallback_y, "aggregation": "mean"}
                c["title"] = f"Average {_pretty(fallback_y)} by {_pretty(x_col)}"
                if c.get("hue"):
                    c["title"] += f" and {_pretty(c['hue'])}"
                print(f"[Planner] Fixed y-axis: date column '{old_y}' → numeric '{fallback_y}'")
            else:
                continue

        # Check if x is numeric and y is categorical (swapped) — only for bar/line/area
        if ctype in ("bar", "line", "area"):
            if x_col in numeric_cols and y_col in categorical_cols:
                c["x"], c["y"]["column"] = y_col, x_col
                print(f"[Planner] Swapped x/y: x was numeric, y was categorical")

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

    # Spread KPIs across DIFFERENT columns
    used_cols = {k.get("metric", {}).get("column") for k in kpis}
    for col in numeric:
        if len(kpis) >= 3:
            break
        if col in used_cols:
            continue
        agg_label, agg_fn = agg_types[len(kpis) % len(agg_types)]
        name = f"{agg_label} {_pretty(col)}"
        kpis.append({"name": name, "metric": {"column": col, "aggregation": agg_fn}})
        used_cols.add(col)

    # If still short, add more from same columns with different aggs
    for col in numeric:
        for label, agg in agg_types:
            if len(kpis) >= 3:
                break
            name = f"{label} {_pretty(col)}"
            if not any(k.get("name") == name for k in kpis):
                kpis.append({"name": name, "metric": {"column": col, "aggregation": agg}})
    return kpis


def _ensure_min_charts(existing_charts, schema):
    """
    Ensure at least 5 charts with MAXIMUM diversity.
    Uses a template system that covers all major patterns.
    """
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
    existing_types = {c.get("type") for c in charts}

    def next_numeric(idx):
        return numeric[idx % len(numeric)]

    def next_categorical(idx):
        return categorical[idx % len(categorical)]

    templates = []
    ni = 0  # numeric index counter
    ci = 0  # categorical index counter

    # 1. PIE — categorical distribution (if not present)
    if "pie" not in existing_types and categorical:
        cat = next_categorical(ci); ci += 1
        templates.append({
            "id": "ensure_pie", "type": "pie", "x": cat,
            "y": {"column": cat, "aggregation": "count"},
            "hue": None,
            "title": f"Distribution of {_pretty(cat)}",
        })

    # 2. SCATTER — numeric vs numeric (if not present)
    if "scatter" not in existing_types and len(numeric) >= 2:
        n1 = next_numeric(ni); ni += 1
        n2 = next_numeric(ni); ni += 1
        templates.append({
            "id": "ensure_scatter", "type": "scatter", "x": n1,
            "y": {"column": n2, "aggregation": "raw"},
            "hue": None,
            "title": f"{_pretty(n1)} vs {_pretty(n2)}",
        })

    # 3. HISTOGRAM — distribution (if not present)
    if "histogram" not in existing_types and numeric:
        n = next_numeric(ni); ni += 1
        templates.append({
            "id": "ensure_histogram", "type": "histogram", "x": n,
            "y": {"column": n, "aggregation": "raw"},
            "hue": None, "bins": 12,
            "title": f"Distribution of {_pretty(n)}",
        })

    # 4. BAR with hue — grouped comparison
    if hue_cols:
        hue = hue_cols[0]
        x_col = next((c for c in categorical if c != hue), categorical[0])
        y_col = next_numeric(ni); ni += 1
        templates.append({
            "id": "ensure_grouped_bar", "type": "bar", "x": x_col,
            "y": {"column": y_col, "aggregation": "mean"},
            "hue": hue,
            "title": f"Average {_pretty(y_col)} by {_pretty(x_col)} and {_pretty(hue)}",
        })

    # 5. BOXPLOT — distribution by category
    if "boxplot" not in existing_types and numeric and categorical:
        y_col = next_numeric(ni); ni += 1
        x_col = next_categorical(ci); ci += 1
        templates.append({
            "id": "ensure_boxplot", "type": "boxplot", "x": x_col,
            "y": {"column": y_col, "aggregation": "raw"},
            "hue": None,
            "title": f"{_pretty(y_col)} Distribution by {_pretty(x_col)}",
        })

    # 6. BAR — basic numeric by categorical (different columns)
    y_col = next_numeric(ni); ni += 1
    x_col = next_categorical(ci); ci += 1
    templates.append({
        "id": "ensure_bar", "type": "bar", "x": x_col,
        "y": {"column": y_col, "aggregation": "mean"},
        "hue": None,
        "title": f"Average {_pretty(y_col)} by {_pretty(x_col)}",
    })

    # 7. LINE / AREA — trend view
    y_col = next_numeric(ni); ni += 1
    x_col = next_categorical(ci); ci += 1
    templates.append({
        "id": "ensure_line", "type": "line", "x": x_col,
        "y": {"column": y_col, "aggregation": "mean"},
        "hue": None,
        "title": f"{_pretty(y_col)} Trend by {_pretty(x_col)}",
    })

    for t in templates:
        if len(charts) >= 7:
            break
        if t["id"] in existing_ids:
            continue
        charts.append(t)

    return charts
