import pandas as pd
import numpy as np
import math
from typing import Dict, Any
from state import DashboardState


AGG_MAP = {
    "sum": "sum",
    "mean": "mean",
    "avg": "mean",
    "count": "count",
    "min": "min",
    "max": "max",
    "median": "median",
    "raw": None,
}


def safe_value(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def apply_metric(series: pd.Series, agg: str):
    agg = AGG_MAP.get(agg, agg)
    if agg is None:
        return series.tolist()
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return None
    return getattr(series, agg)()


def aggregator_agent(state: DashboardState) -> DashboardState:
    df: pd.DataFrame = state["dataframe"]
    plan: Dict[str, Any] = state["analysis_plan"]

    # ================= KPIs =================
    kpis = []
    for kpi in plan.get("kpis", []):
        try:
            col = kpi["metric"]["column"]
            agg = kpi["metric"]["aggregation"]

            if col not in df.columns:
                kpis.append({"name": kpi["name"], "value": None, "error": f"Column '{col}' not found"})
                continue

            if agg == "count":
                value = len(df[df[col].notna()])
            else:
                value = apply_metric(df[col], agg)

            if isinstance(value, list):
                value = len(value)

            kpis.append({
                "name": kpi["name"],
                "value": safe_value(round(float(value), 2)) if value is not None else None
            })

        except Exception as e:
            kpis.append({
                "name": kpi.get("name", "KPI"),
                "value": None,
                "error": str(e)
            })

    state["kpis"] = kpis

    # ================= CHART DATA =================
    aggregated = {}

    for chart in plan.get("charts", []):
        cid = chart["id"]
        try:
            ctype = chart.get("type", "bar")
            x = chart["x"]
            y_spec = chart["y"]
            y_col = y_spec["column"]
            agg = y_spec["aggregation"]
            hue = chart.get("hue")

            # Validate columns exist
            required_cols = [x]
            if y_col != x:
                required_cols.append(y_col)
            if hue:
                required_cols.append(hue)

            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                aggregated[cid] = {"error": f"Missing columns: {missing}"}
                continue

            # ---------- SCATTER (raw values) ----------
            if ctype == "scatter" or agg == "raw":
                scatter_df = df[[x, y_col]].dropna().copy()
                scatter_df = scatter_df.head(500)
                scatter_df.columns = [x, "value"]
                scatter_df[x] = pd.to_numeric(scatter_df[x], errors="coerce")
                scatter_df["value"] = pd.to_numeric(scatter_df["value"], errors="coerce")
                scatter_df = scatter_df.dropna()
                aggregated[cid] = scatter_df
                continue

            # ---------- BOXPLOT ----------
            if ctype == "boxplot":
                y_series = pd.to_numeric(df[y_col], errors="coerce")

                if x in df.columns:
                    categories = df[x].dropna().unique()[:15]
                    box_data = []
                    outliers = []
                    cat_labels = []

                    for idx, cat in enumerate(categories):
                        subset = y_series[df[x] == cat].dropna()
                        if len(subset) < 2:
                            continue
                        q1 = float(subset.quantile(0.25))
                        q3 = float(subset.quantile(0.75))
                        iqr = q3 - q1
                        median = float(subset.median())
                        lower = float(max(subset.min(), q1 - 1.5 * iqr))
                        upper = float(min(subset.max(), q3 + 1.5 * iqr))
                        box_data.append([
                            safe_value(round(lower, 2)),
                            safe_value(round(q1, 2)),
                            safe_value(round(median, 2)),
                            safe_value(round(q3, 2)),
                            safe_value(round(upper, 2)),
                        ])
                        cat_labels.append(str(cat))

                        # Outliers
                        out = subset[(subset < q1 - 1.5 * iqr) | (subset > q3 + 1.5 * iqr)]
                        for v in out.head(20):
                            outliers.append([idx, safe_value(round(float(v), 2))])

                    aggregated[cid] = {
                        "boxplot_data": box_data,
                        "boxplot_categories": cat_labels,
                        "boxplot_outliers": outliers,
                    }
                else:
                    aggregated[cid] = {"error": f"Column '{x}' not found for boxplot"}
                continue

            # ---------- HISTOGRAM ----------
            if ctype == "histogram":
                series = pd.to_numeric(df[y_col], errors="coerce").dropna()
                if series.empty:
                    aggregated[cid] = {"error": "No numeric data for histogram"}
                    continue

                n_bins = chart.get("bins", min(20, max(5, int(len(series) ** 0.5))))
                counts, bin_edges = np.histogram(series, bins=n_bins)

                bin_labels = []
                for i in range(len(bin_edges) - 1):
                    lo = round(float(bin_edges[i]), 1)
                    hi = round(float(bin_edges[i + 1]), 1)
                    bin_labels.append(f"{lo}-{hi}")

                # If hue is provided, create separate histograms per group
                if hue and hue in df.columns:
                    hue_values = df[hue].dropna().unique()[:8]
                    hue_series = {}
                    for hv in hue_values:
                        subset = pd.to_numeric(df[df[hue] == hv][y_col], errors="coerce").dropna()
                        hue_counts, _ = np.histogram(subset, bins=bin_edges)
                        hue_series[str(hv)] = [int(c) for c in hue_counts]

                    aggregated[cid] = {
                        "histogram_bins": bin_labels,
                        "histogram_counts": [int(c) for c in counts],
                        "histogram_hue": hue_series,
                    }
                else:
                    aggregated[cid] = {
                        "histogram_bins": bin_labels,
                        "histogram_counts": [int(c) for c in counts],
                    }
                continue

            # ---------- RADAR ----------
            if ctype == "radar":
                radar_metrics = chart.get("radar_metrics", [])
                if not radar_metrics:
                    radar_metrics = [c for c in state.get("schema", {}).get("numeric", []) if c in df.columns][:6]

                if not radar_metrics:
                    aggregated[cid] = {"error": "No numeric columns for radar"}
                    continue

                if x in df.columns:
                    categories = df[x].dropna().unique()[:8]
                    radar_data = []
                    for cat in categories:
                        subset = df[df[x] == cat]
                        values = {}
                        for metric in radar_metrics:
                            if metric in subset.columns:
                                val = pd.to_numeric(subset[metric], errors="coerce").mean()
                                values[metric] = safe_value(round(float(val), 2)) if not pd.isna(val) else 0
                            else:
                                values[metric] = 0
                        radar_data.append({"category": str(cat), "values": values})

                    aggregated[cid] = {"radar_metrics": radar_metrics, "radar_data": radar_data}
                else:
                    aggregated[cid] = {"error": f"Column '{x}' not found for radar"}
                continue

            # ---------- GAUGE ----------
            if ctype == "gauge":
                series = pd.to_numeric(df[y_col], errors="coerce").dropna()
                if series.empty:
                    aggregated[cid] = {"error": "No numeric data for gauge"}
                    continue

                if agg == "count":
                    value = len(series)
                else:
                    agg_fn = AGG_MAP.get(agg, "mean")
                    value = getattr(series, agg_fn)() if agg_fn else series.mean()

                max_val = chart.get("max_value", float(series.max()) * 1.2)
                aggregated[cid] = {
                    "gauge_value": safe_value(round(float(value), 2)),
                    "gauge_max": safe_value(round(float(max_val), 2)),
                }
                continue

            # ---------- HEATMAP ----------
            if ctype == "heatmap":
                if hue and hue in df.columns:
                    x_cats = df[x].dropna().unique()[:15]
                    y_cats = df[hue].dropna().unique()[:15]

                    heatmap_data = []
                    for xi, xc in enumerate(x_cats):
                        for yi, yc in enumerate(y_cats):
                            subset = df[(df[x] == xc) & (df[hue] == yc)]
                            if agg == "count":
                                val = len(subset)
                            else:
                                s = pd.to_numeric(subset[y_col], errors="coerce").dropna()
                                agg_fn = AGG_MAP.get(agg, "mean")
                                val = getattr(s, agg_fn)() if not s.empty and agg_fn else 0
                            heatmap_data.append([xi, yi, safe_value(round(float(val), 2)) if val else 0])

                    aggregated[cid] = {
                        "heatmap_x": [str(c) for c in x_cats],
                        "heatmap_y": [str(c) for c in y_cats],
                        "heatmap_data": heatmap_data,
                    }
                else:
                    aggregated[cid] = {"error": "Heatmap requires hue column"}
                continue

            # ---------- TREEMAP ----------
            if ctype == "treemap":
                group_cols = [x]
                if hue and hue in df.columns:
                    group_cols.append(hue)

                if agg == "count":
                    grouped = df.groupby(group_cols, dropna=False).size().reset_index(name="value")
                else:
                    agg_fn = AGG_MAP.get(agg, "sum")
                    grouped = df.groupby(group_cols, dropna=False)[y_col].apply(
                        lambda s: apply_metric(s, agg)
                    ).reset_index(name="value")

                grouped["value"] = grouped["value"].apply(safe_value)
                grouped = grouped.dropna(subset=["value"])
                aggregated[cid] = grouped
                continue

            # ---------- FUNNEL ----------
            if ctype == "funnel":
                if agg == "count":
                    grouped = df.groupby(x, dropna=False).size().reset_index(name="value")
                else:
                    agg_fn = AGG_MAP.get(agg, "sum")
                    grouped = df.groupby(x, dropna=False)[y_col].apply(
                        lambda s: apply_metric(s, agg)
                    ).reset_index(name="value")

                grouped["value"] = grouped["value"].apply(safe_value)
                grouped = grouped.dropna(subset=["value"])
                grouped = grouped.sort_values("value", ascending=False).head(10)
                aggregated[cid] = grouped
                continue

            # ---------- STANDARD: BAR / LINE / PIE / AREA ----------
            group_cols = [x]
            if hue and hue in df.columns:
                group_cols.append(hue)

            if agg == "count":
                grouped = df.groupby(group_cols, dropna=False).size().reset_index(name="value")
            else:
                grouped = (
                    df.groupby(group_cols, dropna=False)[y_col]
                      .apply(lambda s: apply_metric(s, agg))
                      .reset_index(name="value")
                )

            grouped["value"] = grouped["value"].apply(safe_value)
            grouped = grouped.dropna(subset=["value"])
            aggregated[cid] = grouped

        except Exception as e:
            aggregated[cid] = {"error": str(e)}

    state["aggregated_data"] = aggregated
    return state
