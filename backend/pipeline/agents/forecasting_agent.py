"""
Forecasting Agent — generates time-series forecasts for date-indexed numeric data.

Uses statsmodels ExponentialSmoothing (Holt-Winters) for seasonal data,
or simple linear trend extrapolation as fallback.

Runs after the Chart Agent and appends forecast charts to the state.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from state import DashboardState

# Vibrant forecast-specific colors
ACTUAL_COLOR = "#6366f1"     # indigo
FORECAST_COLOR = "#f43f5e"   # rose
CONF_BAND_COLOR = "rgba(244, 63, 94, 0.12)"

# Min data points needed to attempt forecasting
MIN_POINTS_FOR_FORECAST = 6
FORECAST_HORIZON = 6  # number of future periods to predict


def forecasting_agent(state: DashboardState) -> DashboardState:
    """
    Detects time-series patterns in the data and produces forecast charts.
    Appends forecast charts to state["charts"].
    """
    df = state.get("dataframe")
    schema = state.get("schema", {})
    intent = state.get("intent", {})

    if df is None or df.empty:
        return state

    datetime_cols = schema.get("datetime", [])
    numeric_cols = schema.get("numeric", [])
    identifiers = set(schema.get("identifiers", []))

    # Filter to usable columns
    numeric_cols = [c for c in numeric_cols if c not in identifiers and c in df.columns]
    datetime_cols = [c for c in datetime_cols if c in df.columns]

    if not datetime_cols or not numeric_cols:
        print("[Forecast] No datetime + numeric column pairs found. Skipping.")
        return state

    # Also check enrichment for month/year columns
    a2a_bus = state.get("a2a_bus")
    enriched_time_cols = []
    if a2a_bus:
        enrichment_msgs = a2a_bus.get_all_of_type("enrichment_info")
        if enrichment_msgs:
            derived = enrichment_msgs[-1].get("payload", {}).get("derived_columns", [])
            # derived_columns is a List[Dict] with {"column": "...", "formula": "..."}
            derived_names = []
            for d in derived:
                if isinstance(d, dict):
                    derived_names.append(d.get("column", ""))
                elif isinstance(d, str):
                    derived_names.append(d)
            enriched_time_cols = [c for c in derived_names if c.endswith("_month") or c.endswith("_year")]

    # Determine if user is asking for forecast/trend
    user_prompt = state.get("prompt", "").lower()
    forecast_keywords = ["forecast", "predict", "future", "projection", "trend", "next",
                         "coming", "expected", "estimate", "will be", "gonna"]
    is_forecast_intent = any(kw in user_prompt for kw in forecast_keywords)

    # Also check intent agent classification
    intent_type = intent.get("type", "")
    if intent_type in ("trend", "forecast", "prediction"):
        is_forecast_intent = True

    # Always try to produce at least 1 forecast if we have time data
    # Produce up to 2 forecast charts
    forecast_charts = []
    attempted = 0
    max_forecasts = 3 if is_forecast_intent else 1

    for date_col in datetime_cols[:2]:
        for num_col in numeric_cols[:3]:
            if attempted >= max_forecasts:
                break
            if len(forecast_charts) >= max_forecasts:
                break

            chart = _try_forecast(df, date_col, num_col, attempted)
            if chart:
                forecast_charts.append(chart)
                attempted += 1

        if len(forecast_charts) >= max_forecasts:
            break

    if forecast_charts:
        existing_charts = state.get("charts", [])
        state["charts"] = existing_charts + forecast_charts
        print(f"[Forecast] Added {len(forecast_charts)} forecast chart(s)")

        # Publish to A2A bus
        if a2a_bus:
            a2a_bus.publish(
                sender="forecasting_agent",
                receiver="all",
                msg_type="forecast_info",
                payload={
                    "forecast_count": len(forecast_charts),
                    "forecasted_columns": [c["id"] for c in forecast_charts],
                }
            )
    else:
        print("[Forecast] No viable time-series found for forecasting.")

    return state


def _try_forecast(df: pd.DataFrame, date_col: str, num_col: str,
                  index: int) -> Optional[Dict[str, Any]]:
    """
    Attempt to build a forecast for a single date_col + num_col pair.
    Returns a chart spec dict or None if data is insufficient.
    """
    try:
        work = df[[date_col, num_col]].dropna().copy()

        # Ensure date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(work[date_col]):
            work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
            work = work.dropna(subset=[date_col])

        # Ensure numeric
        work[num_col] = pd.to_numeric(work[num_col], errors="coerce")
        work = work.dropna()

        if len(work) < MIN_POINTS_FOR_FORECAST:
            return None

        # Determine time granularity
        work = work.sort_values(date_col)
        time_range = (work[date_col].max() - work[date_col].min()).days

        if time_range < 7:
            return None  # too short

        # Choose aggregation period
        if time_range > 365 * 2:
            freq = "QS"
            freq_label = "Quarter"
        elif time_range > 180:
            freq = "MS"
            freq_label = "Month"
        elif time_range > 30:
            freq = "W-MON"
            freq_label = "Week"
        else:
            freq = "D"
            freq_label = "Day"

        # Aggregate by period
        work.set_index(date_col, inplace=True)
        ts = work[num_col].resample(freq).mean().dropna()

        if len(ts) < MIN_POINTS_FOR_FORECAST:
            return None

        # ── Forecast with ExponentialSmoothing ──
        forecast_values, conf_lower, conf_upper = _exponential_smoothing_forecast(ts, FORECAST_HORIZON)

        if forecast_values is None:
            # Fallback to linear trend
            forecast_values, conf_lower, conf_upper = _linear_trend_forecast(ts, FORECAST_HORIZON)

        if forecast_values is None:
            return None

        # ── Build ECharts option ──
        return _build_forecast_chart(
            ts, forecast_values, conf_lower, conf_upper,
            date_col, num_col, freq_label, index
        )

    except Exception as e:
        print(f"[Forecast] Error for {date_col} vs {num_col}: {e}")
        return None


def _exponential_smoothing_forecast(ts: pd.Series, horizon: int):
    """Try Holt-Winters ExponentialSmoothing."""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        # Determine if seasonal (need at least 2 full cycles)
        n = len(ts)
        seasonal = None
        seasonal_periods = None

        if n >= 24:
            seasonal = "add"
            seasonal_periods = 12
        elif n >= 8:
            seasonal = "add"
            seasonal_periods = 4

        model = ExponentialSmoothing(
            ts,
            trend="add",
            seasonal=seasonal,
            seasonal_periods=seasonal_periods,
            initialization_method="estimated",
        )
        fitted = model.fit(optimized=True)
        forecast = fitted.forecast(horizon)

        # Simple confidence band: ±1.5 * residual std
        residuals = fitted.resid.dropna()
        std = residuals.std() if len(residuals) > 0 else 0
        margin = 1.5 * std

        conf_lower = forecast - margin
        conf_upper = forecast + margin

        return (
            forecast.values.tolist(),
            conf_lower.values.tolist(),
            conf_upper.values.tolist(),
        )

    except Exception as e:
        print(f"[Forecast] ExponentialSmoothing failed: {e}")
        return None, None, None


def _linear_trend_forecast(ts: pd.Series, horizon: int):
    """Simple linear regression fallback."""
    try:
        n = len(ts)
        x = np.arange(n)
        y = ts.values.astype(float)

        # Remove NaN/inf
        mask = np.isfinite(y)
        x, y = x[mask], y[mask]
        if len(x) < 3:
            return None, None, None

        # Fit linear regression
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs[0], coeffs[1]

        # Forecast future points
        future_x = np.arange(n, n + horizon)
        forecast = slope * future_x + intercept

        # Confidence band from residual std
        predicted = slope * x + intercept
        residuals = y - predicted
        std = np.std(residuals)
        margin = 1.5 * std

        conf_lower = (forecast - margin).tolist()
        conf_upper = (forecast + margin).tolist()

        return forecast.tolist(), conf_lower, conf_upper

    except Exception as e:
        print(f"[Forecast] Linear trend failed: {e}")
        return None, None, None


def _safe_float(v):
    """Safely convert to float for JSON."""
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), 2)


def _build_forecast_chart(ts, forecast_values, conf_lower, conf_upper,
                          date_col, num_col, freq_label, index):
    """Build an ECharts option for a forecast line chart."""

    # Format date labels
    actual_labels = [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
                     for d in ts.index]
    actual_values = [_safe_float(v) for v in ts.values]

    # Generate future date labels
    last_date = ts.index[-1]
    future_labels = []
    for i in range(1, len(forecast_values) + 1):
        if freq_label == "Quarter":
            future_date = last_date + pd.DateOffset(months=3 * i)
        elif freq_label == "Month":
            future_date = last_date + pd.DateOffset(months=i)
        elif freq_label == "Week":
            future_date = last_date + pd.Timedelta(weeks=i)
        else:
            future_date = last_date + pd.Timedelta(days=i)
        future_labels.append(future_date.strftime("%Y-%m-%d"))

    forecast_values_safe = [_safe_float(v) for v in forecast_values]
    conf_lower_safe = [_safe_float(v) for v in conf_lower]
    conf_upper_safe = [_safe_float(v) for v in conf_upper]

    # Combined x-axis labels
    all_labels = actual_labels + future_labels
    n_actual = len(actual_labels)

    # Actual series (null-padded for forecast zone)
    actual_data = actual_values + [None] * len(forecast_values)

    # Forecast series (null-padded for actual zone, with overlap at junction)
    forecast_data = [None] * (n_actual - 1) + [actual_values[-1]] + forecast_values_safe

    # Confidence band lower / upper
    band_lower = [None] * (n_actual - 1) + [actual_values[-1]] + conf_lower_safe
    band_upper = [None] * (n_actual - 1) + [actual_values[-1]] + conf_upper_safe

    pretty_num = num_col.replace("_", " ").title()
    pretty_date = date_col.replace("_", " ").title()
    title = f"{pretty_num} Forecast ({freq_label}ly Trend)"

    option = {
        "title": {
            "text": title,
            "left": "center",
            "textStyle": {"fontSize": 14, "fontWeight": "bold"},
        },
        "tooltip": {
            "trigger": "axis",
            "backgroundColor": "rgba(255,255,255,0.95)",
            "borderColor": "#e5e7eb",
            "textStyle": {"color": "#1f2937", "fontSize": 12},
        },
        "legend": {
            "data": ["Actual", "Forecast", "Confidence Band"],
            "top": 30,
            "textStyle": {"fontSize": 11},
        },
        "color": [ACTUAL_COLOR, FORECAST_COLOR],
        "grid": {"left": "8%", "right": "5%", "bottom": "15%", "top": "22%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": all_labels,
            "axisLabel": {"rotate": 30, "fontSize": 10},
            "boundaryGap": False,
        },
        "yAxis": {
            "type": "value",
            "name": pretty_num,
            "splitLine": {"lineStyle": {"type": "dashed", "color": "#e5e7eb"}},
        },
        "series": [
            {
                "name": "Actual",
                "type": "line",
                "data": actual_data,
                "smooth": True,
                "symbol": "circle",
                "symbolSize": 5,
                "lineStyle": {"width": 2.5, "color": ACTUAL_COLOR},
                "itemStyle": {"color": ACTUAL_COLOR},
                "areaStyle": {
                    "color": {
                        "type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "rgba(99, 102, 241, 0.15)"},
                            {"offset": 1, "color": "rgba(99, 102, 241, 0.01)"},
                        ]
                    }
                },
            },
            {
                "name": "Forecast",
                "type": "line",
                "data": forecast_data,
                "smooth": True,
                "symbol": "diamond",
                "symbolSize": 7,
                "lineStyle": {"width": 2.5, "color": FORECAST_COLOR, "type": "dashed"},
                "itemStyle": {"color": FORECAST_COLOR},
            },
            {
                "name": "Confidence Band",
                "type": "line",
                "data": band_upper,
                "smooth": True,
                "lineStyle": {"opacity": 0},
                "symbol": "none",
                "areaStyle": {"color": CONF_BAND_COLOR},
                "stack": "confidence",
            },
            {
                "name": "",
                "type": "line",
                "data": band_lower,
                "smooth": True,
                "lineStyle": {"opacity": 0},
                "symbol": "none",
                "areaStyle": {"color": "transparent"},
                "stack": "confidence",
            },
        ],
        # Visual separator: markLine at forecast start
        "markLine_data": n_actual - 1,
    }

    # Add a visual mark to show where forecast begins
    option["series"][0]["markLine"] = {
        "silent": True,
        "symbol": "none",
        "lineStyle": {"type": "dashed", "color": "#d97706", "width": 1.5},
        "data": [{"xAxis": n_actual - 1}],
        "label": {
            "formatter": "Forecast →",
            "position": "end",
            "fontSize": 10,
            "color": "#d97706",
        },
    }

    return {
        "id": f"forecast_{num_col}_{index}",
        "option": option,
        "type": "forecast",
    }
