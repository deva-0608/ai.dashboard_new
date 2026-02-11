from typing import TypedDict, List, Dict, Any, Optional
import pandas as pd


# -----------------------------
# Frontend-ready specifications
# -----------------------------

class ChartSpec(TypedDict):
    id: str
    option: Dict[str, Any]


class KPI(TypedDict):
    name: str
    value: str


# -----------------------------
# LangGraph Shared State
# -----------------------------

class DashboardState(TypedDict):
    """
    Fully dynamic, dataset-agnostic AI dashboard state
    with memory, A2A protocol, and multi-file support.
    """

    # -----------------------------
    # Request context
    # -----------------------------
    report_type: str
    report_id: int
    project_name: str
    session_id: str

    # -----------------------------
    # User input
    # -----------------------------
    prompt: str

    # -----------------------------
    # Memory (persistent via session store)
    # -----------------------------
    chat_history: List[Dict[str, str]]
    memory: Dict[str, Any]            # evolving semantic memory
    filters: Dict[str, Any]           # active constraints
    previous_charts: List[str]        # IDs of previously shown charts
    chart_contexts: List[Dict]        # full context of previous charts

    # -----------------------------
    # A2A Protocol
    # -----------------------------
    a2a_bus: Any                      # A2ABus instance

    # -----------------------------
    # Data
    # -----------------------------
    dataframe: pd.DataFrame
    schema: Dict[str, Any]            # inferred schema + stats
    excel_files: List[str]            # list of Excel files in report

    # -----------------------------
    # AI reasoning outputs
    # -----------------------------
    intent: Dict[str, Any]            # LLM-derived intent
    analysis_plan: Dict[str, Any]     # LLM-generated plan (JSON)

    # -----------------------------
    # Execution outputs
    # -----------------------------
    aggregated_data: Dict[str, Any]

    # -----------------------------
    # Final dashboard
    # -----------------------------
    charts: List[ChartSpec]
    kpis: List[KPI]
    summary: str
    suggested_prompts: List[str]

    # -----------------------------
    # Debug / traceability
    # -----------------------------
    debug: Dict[str, Any]
