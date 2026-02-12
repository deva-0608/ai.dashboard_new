import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any

from dotenv import load_dotenv
load_dotenv()

# --------------------------------------------------
# Internal imports
# --------------------------------------------------
from config import settings
from excel_loader import (
    validate_report_type,
    load_excel_dataframe,
    load_all_excel_dataframes,
    dataframe_to_response,
    find_excel_file,
    find_all_excel_files,
    find_all_excel_in_report_type,
)
from state import DashboardState
from pipeline.runner import run_dashboard_pipeline
from session_store import SessionStore
from utils.llm_factory import LLMFactory

# --------------------------------------------------
# App setup
# --------------------------------------------------
app = FastAPI(
    title="AI Dashboard Backend",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# 1. HEALTH CHECK
# --------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-dashboard-backend",
        "llm": LLMFactory.info(),
    }


# --------------------------------------------------
# 2. REPORT LIST
# --------------------------------------------------
@app.get("/reports/design/{report_type}-list")
def list_reports(report_type: str):
    validate_report_type(report_type)

    base_dir = settings.DATA_ROOT / report_type
    results = []

    if not base_dir.exists():
        return results

    for report_dir in base_dir.iterdir():
        if not report_dir.is_dir():
            continue

        try:
            excel_files = find_all_excel_files(report_type, report_dir.name)
            results.append({
                "report_id": report_dir.name,
                "project_name": excel_files[0].stem if excel_files else "Unknown",
                "excel_files": [f.name for f in excel_files],
                "file_count": len(excel_files),
            })
        except HTTPException:
            continue

    return results


# --------------------------------------------------
# 3. LIST ALL EXCEL FILES in a report type
# --------------------------------------------------
@app.get("/reports/design/{report_type}/all-files")
def list_all_excel_files(report_type: str):
    """Fetch all Excel files across all reports of a type."""
    validate_report_type(report_type)
    return find_all_excel_in_report_type(report_type)


# --------------------------------------------------
# 4. LIST EXCEL FILES in a specific report
# --------------------------------------------------
@app.get("/reports/design/{report_type}/detail/{report_id}/files")
def list_report_files(report_type: str, report_id: str):
    """List all Excel files in a specific report folder."""
    validate_report_type(report_type)
    try:
        files = find_all_excel_files(report_type, report_id)
        return [
            {"file_name": f.name, "project_name": f.stem}
            for f in files
        ]
    except HTTPException:
        return []


# --------------------------------------------------
# 5. REPORT DETAIL – LOAD EXCEL DATA
# --------------------------------------------------
@app.get("/reports/design/{report_type}/detail/{report_id}/data")
async def report_detail_data(report_type: str, report_id: str, file_name: str = None):
    validate_report_type(report_type)

    df, project_name = load_excel_dataframe(report_type, report_id, file_name)
    return dataframe_to_response(df.head(10), project_name)


# --------------------------------------------------
# 6. CHATBOT -> DASHBOARD (main AI endpoint)
# --------------------------------------------------
@app.post("/reports/design/{report_type}/detail/{report_id}/chat")
async def chat_and_generate_dashboard(
    report_type: str,
    report_id: str,
    payload: Dict[str, Any]
):
    validate_report_type(report_type)

    prompt = payload.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    session_id = payload.get("session_id", str(uuid.uuid4()))
    file_name = payload.get("file_name", None)

    # --------------------------------------------------
    # Load Excel (already auto-cleaned & typed)
    # --------------------------------------------------
    df, project_name = load_excel_dataframe(report_type, report_id, file_name)

    # --------------------------------------------------
    # Re-apply any custom columns from session
    # --------------------------------------------------
    from custom_columns import apply_formula, parse_formula_string
    session = SessionStore.get_or_create(session_id)
    custom_cols = session.memory.get("custom_columns", {})
    for cname, cformula in custom_cols.items():
        _, expr = parse_formula_string(cformula)
        if expr:
            df, err = apply_formula(df, cname, expr)
            if not err:
                print(f"[Main] Re-applied custom column: {cname}")

    # --------------------------------------------------
    # Build INITIAL state
    # --------------------------------------------------
    from utils.schema_utils import infer_schema
    schema = infer_schema(df)

    # Get Excel file list
    try:
        excel_files = [f.name for f in find_all_excel_files(report_type, report_id)]
    except Exception:
        excel_files = []

    state: DashboardState = {
        # Context
        "report_type": report_type,
        "report_id": int(report_id),
        "project_name": project_name,
        "session_id": session_id,

        # User input
        "prompt": prompt,

        # Memory (loaded from session by memory_agent)
        "chat_history": [],
        "memory": {},
        "filters": {},
        "previous_charts": [],
        "chart_contexts": [],

        # A2A bus (initialized by runner)
        "a2a_bus": None,

        # Data
        "dataframe": df,
        "schema": schema,
        "excel_files": excel_files,

        # Reasoning outputs
        "intent": {},
        "analysis_plan": {},

        # Execution outputs
        "aggregated_data": {},

        # Final dashboard outputs
        "charts": [],
        "kpis": [],
        "summary": "",
        "suggested_prompts": [],

        # Debug / trace
        "debug": {}
    }

    # --------------------------------------------------
    # Run LangGraph pipeline
    # --------------------------------------------------
    result_state = run_dashboard_pipeline(state)

    # --------------------------------------------------
    # Return FRONTEND-READY RESPONSE
    # --------------------------------------------------
    from utils.json_sanitize import sanitize_for_json
    return sanitize_for_json({
        "project_name": project_name,
        "session_id": session_id,
        "summary": result_state["summary"],
        "kpis": result_state["kpis"],
        "charts": result_state["charts"],
        "suggested_prompts": result_state.get("suggested_prompts", []),
        "excel_files": excel_files,
        "chart_count": len(result_state["charts"]),
        "kpi_count": len(result_state["kpis"]),
    })


# --------------------------------------------------
# 7. CUSTOM COLUMNS
# --------------------------------------------------
@app.post("/reports/design/{report_type}/detail/{report_id}/custom-column")
async def add_custom_column(
    report_type: str,
    report_id: str,
    payload: Dict[str, Any]
):
    """
    Apply a user-defined formula to create a new column.
    Payload: { "formula": "Revenue = Price * Quantity", "session_id": "...", "file_name": "..." }
    Returns: { "success": true, "column_name": "Revenue", "sample_values": [...], "columns": [...] }
    """
    from custom_columns import parse_formula_string, validate_formula, apply_formula, get_column_suggestions

    validate_report_type(report_type)

    formula_str = payload.get("formula", "")
    session_id = payload.get("session_id", "default")
    file_name = payload.get("file_name", None)

    if not formula_str:
        raise HTTPException(status_code=400, detail="Formula is required")

    # Parse "name = expression"
    col_name, expression = parse_formula_string(formula_str)
    if not col_name or not expression:
        raise HTTPException(
            status_code=400,
            detail="Invalid formula format. Use: column_name = expression (e.g., Revenue = Price * Quantity)"
        )

    # Load data
    df, project_name = load_excel_dataframe(report_type, report_id, file_name)

    # Validate
    is_valid, error = validate_formula(expression, list(df.columns))
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    # Apply
    df, error = apply_formula(df, col_name, expression)
    if error:
        raise HTTPException(status_code=400, detail=error)

    # Store in session for reuse
    session = SessionStore.get_or_create(session_id)
    if "custom_columns" not in session.memory:
        session.memory["custom_columns"] = {}
    session.memory["custom_columns"][col_name] = formula_str

    # Return preview
    sample = df[col_name].dropna().head(5).tolist()
    return {
        "success": True,
        "column_name": col_name,
        "formula": formula_str,
        "sample_values": [round(float(v), 2) if isinstance(v, (int, float)) else v for v in sample],
        "total_rows": int(df[col_name].notna().sum()),
        "columns": list(df.columns),
    }


@app.get("/reports/design/{report_type}/detail/{report_id}/formula-suggestions")
async def get_formula_suggestions(report_type: str, report_id: str, file_name: str = None):
    """Get smart formula suggestions based on the data schema."""
    from custom_columns import get_column_suggestions, _detect_date_columns

    validate_report_type(report_type)
    df, _ = load_excel_dataframe(report_type, report_id, file_name)

    suggestions = get_column_suggestions(df)

    # Detect date columns properly (including string dates)
    date_cols = _detect_date_columns(df)
    native_datetime = df.select_dtypes(include=["datetime64"]).columns.tolist()
    all_dates = list(dict.fromkeys(native_datetime + date_cols))  # dedupe, preserve order

    # Categorical = object columns that are NOT dates
    date_set = set(all_dates)
    categorical = [c for c in df.select_dtypes(include=["object", "category"]).columns
                   if c not in date_set]

    columns = {
        "numeric": df.select_dtypes(include=["number"]).columns.tolist(),
        "datetime": all_dates,
        "categorical": categorical,
    }
    return {"suggestions": suggestions, "columns": columns}


# --------------------------------------------------
# 8. SESSION INFO
# --------------------------------------------------
@app.get("/session/{session_id}")
def get_session_info(session_id: str):
    session = SessionStore.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@app.get("/sessions")
def list_sessions():
    return SessionStore.list_sessions()


# --------------------------------------------------
# 8. LLM INFO
# --------------------------------------------------
@app.get("/llm/info")
def llm_info():
    return LLMFactory.info()
