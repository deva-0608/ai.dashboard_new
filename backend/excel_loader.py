import pandas as pd
from pathlib import Path
from fastapi import HTTPException
from typing import Dict, Any, Tuple, List

from config import settings


# -------------------------------------------------
# Validation
# -------------------------------------------------
def validate_report_type(report_type: str):
    if report_type not in settings.ALLOWED_REPORT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report type: {report_type}"
        )


# -------------------------------------------------
# Find Excel file(s) dynamically
# -------------------------------------------------
def find_excel_file(report_type: str, report_id: str) -> Path:
    """
    Finds the first Excel file inside a report folder.
    """
    validate_report_type(report_type)

    report_dir = settings.DATA_ROOT / report_type / str(report_id)

    if not report_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Report folder not found: {report_id}"
        )

    excel_files = [
        f for f in report_dir.iterdir()
        if f.is_file() and f.suffix.lower() in settings.EXCEL_EXTENSIONS
    ]

    if len(excel_files) == 0:
        raise HTTPException(
            status_code=404,
            detail="No Excel file found in report folder"
        )

    return excel_files[0]


def find_all_excel_files(report_type: str, report_id: str) -> List[Path]:
    """
    Finds ALL Excel files inside a report folder.
    Supports multi-file dashboards.
    """
    validate_report_type(report_type)

    report_dir = settings.DATA_ROOT / report_type / str(report_id)

    if not report_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Report folder not found: {report_id}"
        )

    excel_files = [
        f for f in report_dir.iterdir()
        if f.is_file() and f.suffix.lower() in settings.EXCEL_EXTENSIONS
    ]

    if len(excel_files) == 0:
        raise HTTPException(
            status_code=404,
            detail="No Excel files found in report folder"
        )

    return excel_files


def find_all_excel_in_report_type(report_type: str) -> List[Dict[str, Any]]:
    """
    Finds ALL Excel files across ALL report IDs for a report type.
    Used for the 'fetch all' feature.
    """
    validate_report_type(report_type)

    base_dir = settings.DATA_ROOT / report_type

    if not base_dir.exists():
        return []

    results = []
    for report_dir in base_dir.iterdir():
        if not report_dir.is_dir():
            continue

        for f in report_dir.iterdir():
            if f.is_file() and f.suffix.lower() in settings.EXCEL_EXTENSIONS:
                results.append({
                    "report_id": report_dir.name,
                    "file_name": f.name,
                    "project_name": f.stem,
                    "path": str(f),
                })

    return results


# -------------------------------------------------
# Load Excel into DataFrame
# -------------------------------------------------
from utils.data_cleaning import clean_dataframe


def load_excel_dataframe(report_type: str, report_id: str, file_name: str = None) -> Tuple[pd.DataFrame, str]:
    """
    Load a specific Excel file (or the first one) from a report folder.
    """
    if file_name:
        validate_report_type(report_type)
        report_dir = settings.DATA_ROOT / report_type / str(report_id)
        excel_path = report_dir / file_name
        if not excel_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_name}")
    else:
        excel_path = find_excel_file(report_type, report_id)

    # Read with appropriate engine
    if excel_path.suffix.lower() == ".xls":
        df = pd.read_excel(excel_path, engine="xlrd")
    else:
        df = pd.read_excel(excel_path)

    # Auto-clean types
    df = clean_dataframe(df)

    project_name = excel_path.stem
    return df, project_name


def load_all_excel_dataframes(report_type: str, report_id: str) -> List[Tuple[pd.DataFrame, str]]:
    """
    Load ALL Excel files from a report folder.
    Returns list of (DataFrame, project_name) tuples.
    """
    excel_files = find_all_excel_files(report_type, report_id)
    results = []

    for excel_path in excel_files:
        try:
            if excel_path.suffix.lower() == ".xls":
                df = pd.read_excel(excel_path, engine="xlrd")
            else:
                df = pd.read_excel(excel_path)

            df = clean_dataframe(df)
            results.append((df, excel_path.stem))
        except Exception as e:
            print(f"[ExcelLoader] Error loading {excel_path}: {e}")
            continue

    return results


# -------------------------------------------------
# Convert DataFrame -> API response
# -------------------------------------------------
def dataframe_to_response(df: pd.DataFrame, project_name: str) -> Dict[str, Any]:
    """
    Converts DataFrame to frontend-safe JSON
    """
    return {
        "project_name": project_name,
        "columns": [str(c) for c in df.columns],
        "rows": df.fillna("").to_dict(orient="records"),
        "row_count": len(df)
    }
