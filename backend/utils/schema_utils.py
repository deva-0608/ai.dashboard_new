import pandas as pd

def infer_schema(df: pd.DataFrame) -> dict:
    schema = {}

    for col in df.columns:
        dtype = str(df[col].dtype)

        schema[col] = {
            "dtype": dtype,
            "non_null_pct": round(df[col].notna().mean(), 2),
            "unique_values": int(df[col].nunique())
        }

        if pd.api.types.is_numeric_dtype(df[col]):
            schema[col].update({
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "mean": float(df[col].mean())
            })

    return schema
