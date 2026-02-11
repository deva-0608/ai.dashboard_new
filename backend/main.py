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
# 7. SESSION INFO
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
