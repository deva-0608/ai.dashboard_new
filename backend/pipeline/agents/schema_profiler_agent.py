import pandas as pd
from state import DashboardState
from utils.llm_factory import LLMFactory
from langchain_core.messages import SystemMessage, HumanMessage
from utils.json_utils import safe_json_loads


SCHEMA_PROMPT = """
You are a data schema expert and analyst.

Given dataset metadata, classify EVERY column into exactly ONE category:
- categorical: text/category data useful for grouping (status, type, name, gender, class, etc.)
- numeric: numbers useful for aggregation (amounts, scores, counts, prices, etc.)
- datetime: date or timestamp columns
- identifiers: ID columns, row numbers, keys, serial numbers — columns that uniquely identify rows and have NO analytical value for charts

IMPORTANT: Be strict about identifiers. Any column that:
- Contains "id", "ID", "_id", "key", "index", "serial", "no", "number" in its name
- Has nearly unique values per row (unique count close to row count)
- Is just an auto-increment or reference number
...MUST be classified as "identifiers", NOT as numeric or categorical.

Also provide:
- recommended_chart_types: best chart types for this data
- data_domain: domain this data belongs to (sales, HR, healthcare, telecom, finance, etc.)
- analysis_suggestions: 2-3 specific analytical questions this data can answer
  (e.g. "How does churn rate differ by gender?", "What is the average tenure by contract type?")

Return ONLY valid JSON:

{
  "categorical": ["col1", "col2"],
  "numeric": ["col3", "col4"],
  "datetime": ["col5"],
  "identifiers": ["id_col"],
  "recommended_chart_types": ["bar", "line", "pie"],
  "data_domain": "telecom",
  "analysis_suggestions": [
    "Compare churn rate across contract types",
    "Analyze monthly charges by gender and senior status"
  ]
}
"""


def schema_profiler_agent(state: DashboardState) -> DashboardState:
    df = state["dataframe"]

    # Build detailed column profile with richer stats
    profile = {
        "columns": [
            {
                "name": col,
                "dtype": str(df[col].dtype),
                "unique": int(df[col].nunique()),
                "nulls": int(df[col].isna().sum()),
                "sample_values": [str(v) for v in df[col].dropna().head(5).tolist()],
                "unique_ratio": round(df[col].nunique() / max(len(df), 1), 2),
            }
            for col in df.columns
        ],
        "row_count": len(df),
        "column_count": len(df.columns)
    }

    llm = LLMFactory.get_llm(temperature=0)

    response = llm.invoke([
        SystemMessage(content=SCHEMA_PROMPT),
        HumanMessage(content=str(profile))
    ])

    try:
        schema = safe_json_loads(response.content)
        if not isinstance(schema, dict):
            raise ValueError("Schema is not a dict")
    except Exception as e:
        schema = {
            "categorical": [],
            "numeric": [],
            "datetime": [],
            "identifiers": [],
            "recommended_chart_types": ["bar", "line", "pie"],
            "data_domain": "unknown",
            "analysis_suggestions": [],
        }
        state.setdefault("debug", {})
        state["debug"]["schema_error"] = str(e)
        state["debug"]["schema_raw"] = response.content

    # ── HARD FILTER: strip identifiers from categorical & numeric ──
    identifiers = set(schema.get("identifiers", []))

    # Auto-detect identifiers the LLM may have missed
    for col_info in profile["columns"]:
        col_name = col_info["name"]
        col_lower = col_name.lower()
        unique_ratio = col_info["unique_ratio"]

        is_id_name = any(kw in col_lower for kw in [
            " id", "_id", "id ", "id\t",
            "key", "index", "serial", "number", "no.",
            "report_id", "project_id", "review_id", "row", "record",
        ])
        # Also catch standalone "Code" columns that are UUIDs (but NOT "Project Code" with few values)
        is_code_uuid = (col_lower.strip() == "code" or col_lower.endswith("_code")) and unique_ratio > 0.8

        is_nearly_unique = unique_ratio > 0.85

        if (is_id_name or is_code_uuid) and is_nearly_unique:
            identifiers.add(col_name)

    schema["identifiers"] = list(identifiers)

    # Remove identifiers from chart-eligible columns
    schema["categorical"] = [c for c in schema.get("categorical", []) if c not in identifiers]
    schema["numeric"] = [c for c in schema.get("numeric", []) if c not in identifiers]
    schema["datetime"] = [c for c in schema.get("datetime", []) if c not in identifiers]

    state["schema"] = schema

    print(f"[Schema] domain={schema.get('data_domain')}, identifiers={list(identifiers)}")
    print(f"[Schema] categorical={schema['categorical']}, numeric={schema['numeric']}")

    # A2A: Share schema info
    a2a_bus = state.get("a2a_bus")
    if a2a_bus:
        a2a_bus.publish(
            sender="schema_profiler",
            receiver="all",
            msg_type="schema_info",
            payload={
                "schema": schema,
                "row_count": len(df),
                "column_count": len(df.columns),
                "data_domain": schema.get("data_domain", "unknown"),
                "recommended_charts": schema.get("recommended_chart_types", []),
                "excluded_identifiers": list(identifiers),
                "analysis_suggestions": schema.get("analysis_suggestions", []),
            }
        )

    return state
