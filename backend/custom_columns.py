"""
Custom Column Calculator — safely evaluates user-defined formulas
on a DataFrame and stores them in the session for reuse.

Uses pandas DataFrame.eval() for safe arithmetic expressions.
Supports: +, -, *, /, **, //, %, and column references.
Also supports special date operations: date_diff(col1, col2).
"""

import re
import pandas as pd
from typing import Tuple, List, Dict, Optional


# Blocked patterns (prevent code injection)
BLOCKED_PATTERNS = [
    r"__",          # dunder methods
    r"import",      # imports
    r"exec\s*\(",   # execution
    r"compile",     # code compilation
    r"open\s*\(",   # file access
    r"os\.",        # os module
    r"sys\.",       # sys module
    r"subprocess",  # shell access
    r"lambda",      # lambda functions
    r"\bdef\b",     # function definitions
    r"\bclass\b",   # class definitions
]

# Keywords that hint a column looks like a date
DATE_HINTS = ["date", "time", "created", "updated", "start", "end", "target",
              "due", "deadline", "birth", "expir", "issued", "completed", "closed"]


def _detect_date_columns(df: pd.DataFrame) -> List[str]:
    """
    Detect columns that are dates — either already datetime64 dtype,
    or string columns whose name/values look like dates.
    """
    date_cols = []

    for col in df.columns:
        # Already datetime
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
            continue

        # Check if name hints at date
        col_lower = col.lower()
        name_looks_like_date = any(hint in col_lower for hint in DATE_HINTS)

        if not name_looks_like_date:
            continue

        # Check if values are parseable as dates (string, object, or StringDtype)
        col_dtype = str(df[col].dtype).lower()
        if col_dtype in ("object", "string", "str") or "str" in col_dtype:
            sample = df[col].dropna().head(20)
            if len(sample) == 0:
                continue
            try:
                parsed = pd.to_datetime(sample, errors="coerce")
                ratio = parsed.notna().sum() / len(sample)
                if ratio >= 0.6:
                    date_cols.append(col)
            except Exception:
                continue

    return date_cols


def validate_formula(formula: str, df_columns: List[str]) -> Tuple[bool, str]:
    """
    Validate a user formula for safety and correctness.
    Returns (is_valid, error_message).
    """
    if not formula or not formula.strip():
        return False, "Formula cannot be empty"

    # Check for blocked patterns
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, formula, re.IGNORECASE):
            return False, f"Formula contains blocked pattern: {pattern}"

    # Allow date_diff() as a special function — no further column check needed for it
    if "date_diff(" in formula.lower():
        return True, ""

    # Must contain at least one column reference
    has_column_ref = False
    clean_formula = formula.replace("`", "")
    for col in df_columns:
        if col in clean_formula:
            has_column_ref = True
            break

    if not has_column_ref:
        return False, f"Formula must reference at least one column. Available: {df_columns[:10]}"

    # Must contain an operator or function
    operators = ["+", "-", "*", "/", "**", "//", "%"]
    has_operator = any(op in formula for op in operators)
    functions = ["abs(", "log(", "sqrt(", "round(", "clip(", "max(", "min(", "date_diff("]
    has_function = any(fn in formula.lower() for fn in functions)

    if not has_operator and not has_function:
        return False, "Formula must contain an arithmetic operation (+, -, *, /, etc.) or a function like date_diff()"

    return True, ""


def parse_formula_string(input_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse "column_name = expression" format.
    Returns (new_column_name, expression) or (None, None) if invalid.
    """
    input_str = input_str.strip()

    match = re.match(r"^([A-Za-z_][A-Za-z0-9_ ]*?)\s*=\s*(.+)$", input_str)
    if not match:
        return None, None

    col_name = match.group(1).strip()
    expression = match.group(2).strip()

    if not col_name or not expression:
        return None, None

    return col_name, expression


def _try_date_diff(df: pd.DataFrame, expression: str, col_name: str) -> Tuple[pd.DataFrame, str, bool]:
    """
    Handle date_diff(col1, col2) → computes (col2 - col1).dt.days.
    Also handles: col2 - col1 when both are date columns.
    Returns (df, error, was_handled).
    """
    # Match date_diff(col1, col2)
    match = re.match(r"date_diff\(\s*(.+?)\s*,\s*(.+?)\s*\)", expression.strip(), re.IGNORECASE)
    if match:
        col1 = match.group(1).strip().strip("`").strip("'").strip('"')
        col2 = match.group(2).strip().strip("`").strip("'").strip('"')
    else:
        # Check for "col2 - col1" where both are date-like
        minus_match = re.match(r"(.+?)\s*-\s*(.+)", expression)
        if not minus_match:
            return df, "", False

        col2_raw = minus_match.group(1).strip().strip("`")
        col1_raw = minus_match.group(2).strip().strip("`")

        # Only handle if both look like date columns
        date_cols = _detect_date_columns(df)
        date_col_names = set(date_cols)

        if col2_raw in date_col_names and col1_raw in date_col_names:
            col1, col2 = col1_raw, col2_raw
        else:
            return df, "", False  # Not a date operation, let normal eval handle it

    # Verify both columns exist
    if col1 not in df.columns:
        return df, f"Column '{col1}' not found", True
    if col2 not in df.columns:
        return df, f"Column '{col2}' not found", True

    try:
        # Parse both to datetime
        d1 = pd.to_datetime(df[col1], errors="coerce")
        d2 = pd.to_datetime(df[col2], errors="coerce")

        # Compute difference in days
        diff = (d2 - d1).dt.days
        df[col_name] = pd.to_numeric(diff, errors="coerce")

        non_null = df[col_name].notna().sum()
        if non_null == 0:
            del df[col_name]
            return df, "Date difference produced no valid values (check date formats)", True

        return df, "", True

    except Exception as e:
        return df, f"Date calculation error: {str(e)}", True


def apply_formula(df: pd.DataFrame, col_name: str, expression: str) -> Tuple[pd.DataFrame, str]:
    """
    Apply a formula to create a new column in the DataFrame.
    Returns (modified_df, error_message).
    Error message is empty string on success.
    """
    # First, try date_diff handling
    df, err, handled = _try_date_diff(df, expression, col_name)
    if handled:
        return df, err

    try:
        # Strip any user-provided backticks first (we'll re-add as needed)
        quoted_expr = expression.replace("`", "")

        # Auto-quote column names that have spaces for pandas eval
        for col in sorted(df.columns, key=len, reverse=True):
            if " " in col and col in quoted_expr:
                quoted_expr = quoted_expr.replace(col, f"`{col}`")

        # Use pandas eval for safe arithmetic
        result = df.eval(quoted_expr)

        # Add as new column
        df[col_name] = result

        # Ensure numeric
        df[col_name] = pd.to_numeric(df[col_name], errors="coerce")

        non_null = df[col_name].notna().sum()
        if non_null == 0:
            del df[col_name]
            return df, "Formula produced no valid numeric values"

        return df, ""

    except Exception as e:
        error_msg = str(e)
        if "undefined variable" in error_msg.lower():
            error_msg = f"Column not found in data. Available columns: {list(df.columns)[:10]}"
        return df, f"Formula error: {error_msg}"


def get_column_suggestions(df: pd.DataFrame) -> List[Dict[str, str]]:
    """
    Generate smart formula suggestions based on the DataFrame schema.
    Returns a list of {name, formula, description} dicts.
    """
    suggestions = []
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    date_cols = _detect_date_columns(df)

    # ─── Date difference suggestions (highest priority) ───
    if len(date_cols) >= 2:
        for i in range(len(date_cols)):
            for j in range(i + 1, min(len(date_cols), i + 3)):
                d1, d2 = date_cols[i], date_cols[j]
                name = f"{d2.replace(' ', '_')}_minus_{d1.replace(' ', '_')}_days"
                # Clean name
                name = re.sub(r'[^A-Za-z0-9_]', '_', name)
                suggestions.append({
                    "name": name,
                    "formula": f"date_diff({d1}, {d2})",
                    "description": f"Days between {d1} and {d2}",
                })
                if len(suggestions) >= 3:
                    break
            if len(suggestions) >= 3:
                break

    # ─── Ratio suggestions ───
    if len(numeric_cols) >= 2:
        n1, n2 = numeric_cols[0], numeric_cols[1]
        suggestions.append({
            "name": f"{re.sub(r'[^A-Za-z0-9_]', '_', n1)}_to_{re.sub(r'[^A-Za-z0-9_]', '_', n2)}_ratio",
            "formula": f"`{n1}` / `{n2}`" if " " in n1 or " " in n2 else f"{n1} / {n2}",
            "description": f"Ratio of {n1} to {n2}",
        })

    # ─── Product suggestion ───
    if len(numeric_cols) >= 2:
        n1, n2 = numeric_cols[0], numeric_cols[1]
        suggestions.append({
            "name": f"{re.sub(r'[^A-Za-z0-9_]', '_', n1)}_x_{re.sub(r'[^A-Za-z0-9_]', '_', n2)}",
            "formula": f"`{n1}` * `{n2}`" if " " in n1 or " " in n2 else f"{n1} * {n2}",
            "description": f"Product of {n1} and {n2}",
        })

    # ─── Sum of numerics ───
    if len(numeric_cols) >= 3:
        parts = [f"`{c}`" if " " in c else c for c in numeric_cols[:4]]
        suggestions.append({
            "name": "total_score",
            "formula": " + ".join(parts),
            "description": f"Sum of {', '.join(numeric_cols[:4])}",
        })

    # ─── Percentage suggestion ───
    if numeric_cols:
        col = numeric_cols[0]
        ref = f"`{col}`" if " " in col else col
        suggestions.append({
            "name": f"{re.sub(r'[^A-Za-z0-9_]', '_', col)}_pct",
            "formula": f"{ref} / {ref}.sum() * 100",
            "description": f"Percentage share of {col}",
        })

    return suggestions[:6]
