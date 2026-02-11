import pandas as pd
import numpy as np
import warnings

INVALID_VALUES = ["--", "-", "", "none", "null"]


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Production-safe dataframe cleaning:
    - No row loss
    - Conservative dtype inference
    - No pandas warnings
    - Safe for AI analytics pipelines
    """
    df = df.copy()

    for col in df.columns:
        # ---------------------------------
        # Normalize string values safely
        # ---------------------------------
        if df[col].dtype == object:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.lower()
                .replace(INVALID_VALUES, np.nan)
            )

        df[col] = df[col].infer_objects(copy=False)

        # ---------------------------------
        # VERY SAFE datetime conversion
        # ---------------------------------
        if df[col].dtype == object:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)

                parsed = pd.to_datetime(df[col], errors="coerce")

            if parsed.notna().mean() > 0.7:
                df[col] = parsed
                continue

        # ---------------------------------
        # SAFE numeric conversion
        # ---------------------------------
        if df[col].dtype == object:
            numeric = pd.to_numeric(df[col], errors="coerce")

            if numeric.notna().mean() > 0.7:
                df[col] = numeric

    return df
