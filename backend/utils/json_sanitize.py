import math
import pandas as pd
import numpy as np
from datetime import datetime, date


def sanitize_for_json(obj):
    """
    Recursively sanitize objects so they are 100% JSON serializable.
    Converts:
    - NaN / inf → None
    - numpy scalars → python scalars
    - pandas objects → dict / list
    - datetime → ISO string
    """

    # -----------------------------
    # Primitives
    # -----------------------------
    if obj is None:
        return None

    if isinstance(obj, (str, int, bool)):
        return obj

    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # -----------------------------
    # NumPy
    # -----------------------------
    if isinstance(obj, np.generic):
        return sanitize_for_json(obj.item())

    # -----------------------------
    # Datetime
    # -----------------------------
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()

    # -----------------------------
    # Pandas
    # -----------------------------
    if isinstance(obj, pd.DataFrame):
        return sanitize_for_json(obj.to_dict(orient="records"))

    if isinstance(obj, pd.Series):
        return sanitize_for_json(obj.tolist())

    # -----------------------------
    # Containers
    # -----------------------------
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(v) for v in obj]

    # -----------------------------
    # Fallback (last resort)
    # -----------------------------
    return obj
