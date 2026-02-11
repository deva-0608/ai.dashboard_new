"""
Data Enrichment Agent
---------------------
Runs BEFORE planning. Analyzes the dataframe and creates meaningful
derived columns + annotates the schema with analytical context.

Creates:
  - Duration from date pairs (end - start) if not already present
  - Rate / percentage columns from related numerics
  - Bins for continuous variables (age groups, duration tiers)
  - Month/year extractions from dates for trend analysis

Detects:
  - Existing lag/duration columns already in the data
  - Best hue columns for grouped analysis
  - Key analytical columns (the "interesting" ones)
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from state import DashboardState


def data_enrichment_agent(state: DashboardState) -> DashboardState:
    df: pd.DataFrame = state["dataframe"].copy()
    schema = state.get("schema", {})

    derived_info: List[Dict] = []
    hue_candidates: List[str] = []
    key_numeric_columns: List[str] = []   # most analytically interesting numeric columns
    key_categorical_columns: List[str] = []  # most interesting for grouping

    # ── 0. Parse string date columns into actual datetime ──
    _parse_string_dates(df, schema)

    # ── 1. Detect EXISTING duration/lag/days columns ──
    existing_duration_cols = _find_existing_duration_columns(df, schema)
    if existing_duration_cols:
        for col in existing_duration_cols:
            # Ensure it's in numeric schema
            if col not in schema.get("numeric", []):
                schema.setdefault("numeric", []).append(col)
            # Force numeric conversion
            df[col] = pd.to_numeric(df[col], errors="coerce")
            key_numeric_columns.append(col)
            derived_info.append({
                "column": col,
                "formula": "pre-existing in data",
                "type": "duration",
                "description": f"Duration/lag column already in the dataset — USE THIS for lag/duration analysis",
            })
            print(f"[Enrichment] Found existing duration column: '{col}'")

    # ── 2. Create duration columns from date pairs (only if none exist) ──
    if not existing_duration_cols:
        datetime_cols = schema.get("datetime", [])
        date_like_cols = _find_date_columns(df, datetime_cols)

        if len(date_like_cols) >= 2:
            pairs = _find_date_pairs(date_like_cols, df)
            for start_col, end_col, duration_col in pairs:
                if duration_col in df.columns:
                    continue
                try:
                    s = pd.to_datetime(df[start_col], errors="coerce")
                    e = pd.to_datetime(df[end_col], errors="coerce")
                    duration = (e - s).dt.days
                    if duration.notna().sum() > len(df) * 0.2:
                        df[duration_col] = duration
                        derived_info.append({
                            "column": duration_col,
                            "formula": f"({end_col} - {start_col}).days",
                            "type": "duration",
                            "description": f"Calculated duration in days between {start_col} and {end_col}",
                        })
                        schema.setdefault("numeric", []).append(duration_col)
                        key_numeric_columns.append(duration_col)
                        print(f"[Enrichment] Created '{duration_col}' = {end_col} - {start_col}")
                except Exception as e:
                    print(f"[Enrichment] Failed duration for {start_col}/{end_col}: {e}")

    # ── 3. Identify best hue columns for grouped analysis ──
    categorical = schema.get("categorical", [])
    identifiers = set(schema.get("identifiers", []))

    for col in categorical:
        if col in identifiers or col not in df.columns:
            continue
        nunique = df[col].nunique()
        # Good hue: 2-8 distinct values
        if 2 <= nunique <= 8:
            hue_candidates.append(col)
        # Key categorical: anything with 2-20 values is interesting for analysis
        if 2 <= nunique <= 20:
            key_categorical_columns.append(col)

    # Sort hue candidates: prefer 2-5 values (cleaner grouped charts)
    hue_candidates.sort(key=lambda c: abs(df[c].nunique() - 3))

    # ── 4. Identify key numeric columns (non-trivial, analytically interesting) ──
    all_numeric = [c for c in schema.get("numeric", []) if c in df.columns and c not in identifiers]
    for col in all_numeric:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) > 0 and series.std() > 0:
            if col not in key_numeric_columns:
                key_numeric_columns.append(col)

    # ── 5. Create bins for duration/continuous columns ──
    for col in key_numeric_columns[:5]:
        col_lower = col.lower()
        if any(kw in col_lower for kw in ["day", "duration", "lag", "age", "tenure", "month"]):
            try:
                series = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(series) > 15 and series.nunique() > 5:
                    bin_col = f"{col}_group"
                    if bin_col not in df.columns:
                        df[bin_col] = pd.qcut(
                            pd.to_numeric(df[col], errors="coerce"),
                            q=4, labels=["Low", "Medium-Low", "Medium-High", "High"],
                            duplicates="drop"
                        )
                        derived_info.append({
                            "column": bin_col,
                            "formula": f"quartile_bins({col})",
                            "type": "binned",
                            "description": f"{col} grouped into quartiles for categorical analysis",
                        })
                        schema.setdefault("categorical", []).append(bin_col)
                        hue_candidates.append(bin_col)
                        print(f"[Enrichment] Created bins '{bin_col}'")
            except Exception:
                pass

    # ── 6. Extract month/year from date columns for trends ──
    datetime_cols_all = _find_date_columns(df, schema.get("datetime", []))
    for col in datetime_cols_all[:3]:  # limit
        try:
            parsed = pd.to_datetime(df[col], errors="coerce")
            if parsed.notna().sum() > len(df) * 0.4:
                month_col = f"{col}_month"
                if month_col not in df.columns:
                    df[month_col] = parsed.dt.strftime("%Y-%m")
                    schema.setdefault("categorical", []).append(month_col)
                    derived_info.append({
                        "column": month_col,
                        "formula": f"month_of({col})",
                        "type": "time_extract",
                        "description": f"Year-month extracted from {col} for trend analysis",
                    })
                    key_categorical_columns.append(month_col)
                    print(f"[Enrichment] Extracted month '{month_col}'")
        except Exception:
            pass

    # ── Save everything ──
    state["dataframe"] = df
    state["schema"] = schema
    state["schema"]["suggested_hue_columns"] = hue_candidates[:5]
    state["schema"]["derived_columns"] = derived_info
    state["schema"]["key_numeric_columns"] = key_numeric_columns[:8]
    state["schema"]["key_categorical_columns"] = key_categorical_columns[:8]

    # A2A
    a2a_bus = state.get("a2a_bus")
    if a2a_bus:
        a2a_bus.publish(
            sender="data_enrichment_agent",
            receiver="all",
            msg_type="enrichment_info",
            payload={
                "derived_columns": derived_info,
                "hue_candidates": hue_candidates[:5],
                "key_numeric_columns": key_numeric_columns[:8],
                "key_categorical_columns": key_categorical_columns[:8],
                "total_rows": len(df),
                "total_columns": len(df.columns),
            }
        )

    print(f"[Enrichment] Done: {len(derived_info)} enrichments, "
          f"{len(hue_candidates)} hue candidates, "
          f"key_numeric={key_numeric_columns[:5]}, key_cat={key_categorical_columns[:5]}")
    return state


# ============================================================
# Helpers
# ============================================================

def _parse_string_dates(df: pd.DataFrame, schema: dict):
    """
    Detect columns that are dates stored as strings and mark them
    in the datetime schema. Don't modify the actual column (planner
    should use derived columns), just annotate.
    """
    datetime_cols = list(schema.get("datetime", []))

    for col in df.columns:
        if col in datetime_cols:
            continue
        if df[col].dtype != object:
            continue
        col_lower = col.lower()
        if any(kw in col_lower for kw in [
            "date", "time", "created", "updated", "start", "end",
            "deadline", "due", "target", "launch", "expire", "birth",
            "join", "close", "open", "begin", "finish", "actual",
        ]):
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                valid_ratio = parsed.notna().sum() / max(len(df), 1)
                if valid_ratio > 0.3:
                    datetime_cols.append(col)
                    # Also remove from categorical if it got classified there
                    if col in schema.get("categorical", []):
                        schema["categorical"].remove(col)
            except Exception:
                pass

    schema["datetime"] = datetime_cols


def _find_existing_duration_columns(df: pd.DataFrame, schema: dict) -> List[str]:
    """
    Detect columns that already contain duration/lag/days data.
    These are gold — the user likely wants to analyze them.
    """
    found = []
    all_cols = list(df.columns)

    for col in all_cols:
        col_lower = col.lower()
        if any(kw in col_lower for kw in [
            "lag", "duration", "days", "elapsed", "delay",
            "lead time", "leadtime", "turnaround", "time spent",
            "cycle time", "aging", "overdue",
        ]):
            # Verify it's numeric-ish
            try:
                series = pd.to_numeric(df[col], errors="coerce")
                if series.notna().sum() > len(df) * 0.2:
                    found.append(col)
            except Exception:
                pass

    return found


def _find_date_columns(df: pd.DataFrame, known_datetime: List[str]) -> List[str]:
    """Find all columns that look like dates (including string dates)."""
    date_cols = list(known_datetime)

    for col in df.columns:
        if col in date_cols:
            continue
        col_lower = col.lower()
        if any(kw in col_lower for kw in [
            "date", "time", "created", "updated", "start", "end",
            "deadline", "due", "target", "launch", "expire", "birth",
            "join", "close", "open", "begin", "finish", "actual",
        ]):
            try:
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() > len(df) * 0.2:
                    date_cols.append(col)
            except Exception:
                pass

    return date_cols


def _find_date_pairs(date_cols: List[str], df: pd.DataFrame) -> List[Tuple[str, str, str]]:
    """Find logical (start, end) date pairs and name the duration column."""
    pairs = []
    used = set()

    start_keywords = ["start", "begin", "open", "create", "join", "launch", "birth"]
    end_keywords = ["end", "finish", "close", "complete", "target", "deadline", "due",
                     "expire", "death", "actual end"]

    for s_col in date_cols:
        s_lower = s_col.lower()
        for e_col in date_cols:
            if s_col == e_col or e_col in used or s_col in used:
                continue
            e_lower = e_col.lower()

            is_start = any(kw in s_lower for kw in start_keywords)
            is_end = any(kw in e_lower for kw in end_keywords)

            if is_start and is_end:
                # Name the duration column
                base = s_lower
                for kw in start_keywords + ["date", "_", " "]:
                    base = base.replace(kw, "")
                base = base.strip()
                if base:
                    duration_name = f"{base}_duration_days"
                else:
                    duration_name = f"calc_duration_days"

                try:
                    s_dt = pd.to_datetime(df[s_col], errors="coerce")
                    e_dt = pd.to_datetime(df[e_col], errors="coerce")
                    valid = (e_dt - s_dt).dt.days
                    if valid.dropna().count() > len(df) * 0.2:
                        pairs.append((s_col, e_col, duration_name))
                        used.add(s_col)
                        used.add(e_col)
                except Exception:
                    pass

    return pairs
