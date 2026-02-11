import pandas as pd
from state import DashboardState


# Vibrant multi-color palette — designed to pop on yellow-themed UI
# Avoids pure yellow (blends into background); leads with vivid jewel tones
COLORS = [
    "#6366f1",  # indigo
    "#f43f5e",  # rose
    "#06b6d4",  # cyan
    "#10b981",  # emerald
    "#f97316",  # orange
    "#8b5cf6",  # violet
    "#ec4899",  # pink
    "#14b8a6",  # teal
    "#e11d48",  # crimson
    "#0ea5e9",  # sky blue
    "#a855f7",  # purple
    "#22c55e",  # green
]


def chart_agent(state: DashboardState) -> DashboardState:
    plan = state["analysis_plan"]
    data_map = state["aggregated_data"]

    charts = []

    for chart in plan.get("charts", []):
        cid = chart["id"]
        ctype = chart.get("type", "bar")
        x = chart.get("x", "")
        hue = chart.get("hue")
        title = chart.get("title", cid)

        raw = data_map.get(cid)
        if raw is None:
            continue

        if isinstance(raw, dict) and "error" in raw:
            continue

        try:
            option = _build_chart_option(ctype, raw, chart, x, hue, title)
            if option:
                charts.append({"id": cid, "option": option, "type": ctype})
        except Exception as e:
            print(f"[ChartAgent] Error building {cid}: {e}")
            continue

    state["charts"] = charts

    # A2A: Share chart context for memory
    a2a_bus = state.get("a2a_bus")
    if a2a_bus:
        for c in charts:
            a2a_bus.publish(
                sender="chart_agent",
                receiver="all",
                msg_type="chart_context",
                payload={
                    "chart_id": c["id"],
                    "chart_type": c.get("type", "unknown"),
                    "title": c["option"].get("title", {}).get("text", ""),
                }
            )

    return state


def _build_chart_option(ctype, raw, chart, x, hue, title):
    builders = {
        "pie": _build_pie,
        "bar": _build_bar_line_area,
        "line": _build_bar_line_area,
        "area": _build_bar_line_area,
        "scatter": _build_scatter,
        "boxplot": _build_boxplot,
        "histogram": _build_histogram,
        "radar": _build_radar,
        "heatmap": _build_heatmap,
        "gauge": _build_gauge,
        "funnel": _build_funnel,
        "treemap": _build_treemap,
    }

    builder = builders.get(ctype, _build_bar_line_area)
    return builder(ctype, raw, chart, x, hue, title)


# ==============================================================
# PIE CHART — vibrant donut with rich colors
# ==============================================================

def _build_pie(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, pd.DataFrame):
        return None

    df = raw.copy().dropna(subset=[x, "value"])
    if df.empty:
        return None

    if hue and hue in df.columns:
        df = df.groupby(x, dropna=False)["value"].sum().reset_index()

    df = df.nlargest(10, "value")

    pie_data = [
        {"name": str(r[x]), "value": round(float(r["value"]), 2)}
        for _, r in df.iterrows()
        if r["value"] is not None
    ]

    if not pie_data:
        return None

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {"orient": "vertical", "left": "left", "top": "middle", "type": "scroll"},
        "color": COLORS,
        "series": [{
            "type": "pie",
            "radius": ["42%", "72%"],
            "center": ["55%", "55%"],
            "avoidLabelOverlap": True,
            "itemStyle": {"borderRadius": 8, "borderColor": "#fff", "borderWidth": 3},
            "label": {"show": True, "formatter": "{b}: {d}%", "fontSize": 11},
            "emphasis": {
                "label": {"show": True, "fontSize": 15, "fontWeight": "bold"},
                "itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(0,0,0,0.25)"}
            },
            "data": pie_data
        }]
    }


# ==============================================================
# BAR / LINE / AREA — grouped hue support, vibrant per-bar colors
# ==============================================================

def _build_bar_line_area(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, pd.DataFrame):
        return None

    df = raw.copy().dropna(subset=[x, "value"])
    if df.empty:
        return None

    series_type = "line" if ctype in ("line", "area") else "bar"
    is_area = ctype == "area"

    if hue and hue in df.columns:
        # ---- GROUPED: multi-series with hue ----
        categories = list(df[x].unique())
        cat_str = [str(c) for c in categories]
        hue_values = list(df[hue].unique())

        lookup = {}
        for _, r in df.iterrows():
            lookup[(r[x], r[hue])] = round(float(r["value"]), 2)

        series = []
        for idx, hv in enumerate(hue_values):
            aligned_data = [lookup.get((c, hv), None) for c in categories]
            if all(v is None for v in aligned_data):
                continue

            s = {
                "name": str(hv),
                "type": series_type,
                "data": aligned_data,
                "smooth": series_type == "line",
                "itemStyle": {
                    "borderRadius": [4, 4, 0, 0],
                    "color": COLORS[idx % len(COLORS)],
                } if series_type == "bar" else {
                    "color": COLORS[idx % len(COLORS)],
                },
            }
            if is_area:
                s["areaStyle"] = {"opacity": 0.25, "color": COLORS[idx % len(COLORS)]}
            if series_type == "bar":
                s["barMaxWidth"] = 36
                s["barGap"] = "15%"
            series.append(s)

        if not series:
            return None

        legend = {"data": [str(v) for v in hue_values], "top": 28, "type": "scroll"}
    else:
        # ---- SINGLE series: color each bar differently ----
        cat_str = [str(r[x]) for _, r in df.iterrows()]
        data_values = []
        for idx, (_, r) in enumerate(df.iterrows()):
            val = round(float(r["value"]), 2)
            if series_type == "bar":
                data_values.append({
                    "value": val,
                    "itemStyle": {
                        "color": COLORS[idx % len(COLORS)],
                        "borderRadius": [6, 6, 0, 0],
                    }
                })
            else:
                data_values.append(val)

        s = {
            "type": series_type,
            "data": data_values,
            "smooth": series_type == "line",
        }

        if series_type == "line":
            s["lineStyle"] = {"width": 3, "color": COLORS[0]}
            s["itemStyle"] = {"color": COLORS[0]}
            s["symbol"] = "circle"
            s["symbolSize"] = 6

        if is_area:
            s["areaStyle"] = {"opacity": 0.2, "color": COLORS[0]}
            s["lineStyle"] = {"width": 2, "color": COLORS[0]}

        if series_type == "bar":
            s["barMaxWidth"] = 40

        series = [s]
        legend = {}

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow" if series_type == "bar" else "cross"}},
        "legend": legend,
        "color": COLORS,
        "grid": {"left": "8%", "right": "5%", "bottom": "12%", "top": "20%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": cat_str,
            "axisLabel": {"rotate": 30 if len(cat_str) > 6 else 0, "fontSize": 11},
        },
        "yAxis": {"type": "value", "splitLine": {"lineStyle": {"type": "dashed", "color": "#e5e7eb"}}},
        "series": series,
    }


# ==============================================================
# SCATTER CHART
# ==============================================================

def _build_scatter(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, pd.DataFrame):
        return None

    df = raw.copy()
    if df.empty:
        return None

    x_col = df.columns[0]
    y_col = "value" if "value" in df.columns else df.columns[1]

    scatter_data = [
        [round(float(r[x_col]), 2), round(float(r[y_col]), 2)]
        for _, r in df.iterrows()
        if pd.notna(r[x_col]) and pd.notna(r[y_col])
    ]

    if not scatter_data:
        return None

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "item"},
        "color": COLORS,
        "grid": {"left": "8%", "right": "5%", "bottom": "12%", "top": "15%", "containLabel": True},
        "xAxis": {
            "type": "value", "name": x_col.replace("_", " ").title(),
            "splitLine": {"lineStyle": {"type": "dashed", "color": "#e5e7eb"}},
        },
        "yAxis": {
            "type": "value", "name": y_col.replace("_", " ").title(),
            "splitLine": {"lineStyle": {"type": "dashed", "color": "#e5e7eb"}},
        },
        "series": [{
            "type": "scatter",
            "data": scatter_data,
            "symbolSize": 10,
            "itemStyle": {
                "color": {
                    "type": "radial", "x": 0.5, "y": 0.5, "r": 0.5,
                    "colorStops": [
                        {"offset": 0, "color": COLORS[0]},
                        {"offset": 1, "color": COLORS[2]},
                    ]
                },
                "opacity": 0.75,
            },
            "emphasis": {"itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(0,0,0,0.3)"}}
        }]
    }


# ==============================================================
# BOXPLOT CHART
# ==============================================================

def _build_boxplot(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, dict) or "boxplot_data" not in raw:
        return None

    box_data = raw.get("boxplot_data", [])
    categories = raw.get("boxplot_categories", [])
    outliers = raw.get("boxplot_outliers", [])

    if not box_data or not categories:
        return None

    series = [
        {
            "name": "boxplot",
            "type": "boxplot",
            "data": box_data,
            "itemStyle": {
                "color": "#ede9fe",
                "borderColor": COLORS[0],
                "borderWidth": 2,
            },
            "emphasis": {
                "itemStyle": {"borderColor": COLORS[5], "borderWidth": 2.5}
            },
        }
    ]

    # Add outliers as scatter
    if outliers:
        series.append({
            "name": "outliers",
            "type": "scatter",
            "data": outliers,
            "symbolSize": 6,
            "itemStyle": {"color": COLORS[1], "opacity": 0.8},
        })

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "item", "axisPointer": {"type": "shadow"}},
        "color": COLORS,
        "grid": {"left": "8%", "right": "5%", "bottom": "12%", "top": "16%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {"rotate": 25 if len(categories) > 5 else 0, "fontSize": 11},
        },
        "yAxis": {
            "type": "value",
            "splitLine": {"lineStyle": {"type": "dashed", "color": "#e5e7eb"}},
        },
        "series": series,
    }


# ==============================================================
# HISTOGRAM CHART
# ==============================================================

def _build_histogram(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, dict) or "histogram_bins" not in raw:
        return None

    bins = raw.get("histogram_bins", [])
    counts = raw.get("histogram_counts", [])
    hue_series = raw.get("histogram_hue")

    if not bins or not counts:
        return None

    if hue_series:
        # Multi-series histogram (grouped by hue)
        series = []
        for idx, (hv, hv_counts) in enumerate(hue_series.items()):
            series.append({
                "name": str(hv),
                "type": "bar",
                "data": hv_counts,
                "barMaxWidth": 30,
                "itemStyle": {
                    "color": COLORS[idx % len(COLORS)],
                    "borderRadius": [3, 3, 0, 0],
                    "opacity": 0.85,
                },
            })
        legend = {"data": list(hue_series.keys()), "top": 28, "type": "scroll"}
    else:
        # Single histogram — gradient fill
        data_with_color = []
        for idx, c in enumerate(counts):
            data_with_color.append({
                "value": c,
                "itemStyle": {
                    "color": COLORS[idx % len(COLORS)],
                    "borderRadius": [4, 4, 0, 0],
                },
            })
        series = [{
            "type": "bar",
            "data": data_with_color,
            "barMaxWidth": 36,
            "barCategoryGap": "10%",
        }]
        legend = {}

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": legend,
        "color": COLORS,
        "grid": {"left": "8%", "right": "5%", "bottom": "16%", "top": "18%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": bins,
            "axisLabel": {"rotate": 35, "fontSize": 10},
            "name": "Range",
        },
        "yAxis": {
            "type": "value",
            "name": "Frequency",
            "splitLine": {"lineStyle": {"type": "dashed", "color": "#e5e7eb"}},
        },
        "series": series,
    }


# ==============================================================
# RADAR CHART
# ==============================================================

def _build_radar(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, dict) or "radar_data" not in raw:
        return None

    metrics = raw.get("radar_metrics", [])
    radar_data = raw.get("radar_data", [])

    if not metrics or not radar_data:
        return None

    max_vals = {}
    for item in radar_data:
        for m in metrics:
            val = item["values"].get(m, 0) or 0
            max_vals[m] = max(max_vals.get(m, 0), val)

    indicator = [
        {"name": m.replace("_", " ").title(), "max": round(max_vals.get(m, 100) * 1.2, 2)}
        for m in metrics
    ]

    series_data = []
    for i, item in enumerate(radar_data):
        series_data.append({
            "name": str(item["category"]),
            "value": [item["values"].get(m, 0) or 0 for m in metrics],
            "areaStyle": {"opacity": 0.12, "color": COLORS[i % len(COLORS)]},
            "lineStyle": {"width": 2, "color": COLORS[i % len(COLORS)]},
            "itemStyle": {"color": COLORS[i % len(COLORS)]},
        })

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "item"},
        "legend": {
            "data": [str(d["category"]) for d in radar_data],
            "bottom": 0, "type": "scroll"
        },
        "color": COLORS,
        "radar": {"indicator": indicator, "shape": "polygon", "radius": "60%"},
        "series": [{
            "type": "radar",
            "data": series_data,
            "emphasis": {"areaStyle": {"opacity": 0.3}}
        }]
    }


# ==============================================================
# HEATMAP CHART — warm color ramp
# ==============================================================

def _build_heatmap(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, dict) or "heatmap_data" not in raw:
        return None

    x_labels = raw.get("heatmap_x", [])
    y_labels = raw.get("heatmap_y", [])
    data = raw.get("heatmap_data", [])

    if not x_labels or not y_labels or not data:
        return None

    values = [d[2] for d in data if d[2] is not None]
    min_val = min(values) if values else 0
    max_val = max(values) if values else 1

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"position": "top"},
        "grid": {"left": "12%", "right": "8%", "bottom": "18%", "top": "15%"},
        "xAxis": {
            "type": "category", "data": x_labels,
            "splitArea": {"show": True},
            "axisLabel": {"rotate": 30, "fontSize": 10},
        },
        "yAxis": {
            "type": "category", "data": y_labels,
            "splitArea": {"show": True},
        },
        "visualMap": {
            "min": min_val, "max": max_val,
            "calculable": True, "orient": "horizontal", "left": "center", "bottom": 0,
            "inRange": {"color": ["#ede9fe", "#a78bfa", "#7c3aed", "#4c1d95"]},
        },
        "series": [{
            "type": "heatmap", "data": data,
            "label": {"show": True, "fontSize": 10, "color": "#1f2937"},
            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,0,0,0.5)"}}
        }]
    }


# ==============================================================
# GAUGE CHART — vibrant gradient
# ==============================================================

def _build_gauge(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, dict) or "gauge_value" not in raw:
        return None

    value = raw["gauge_value"]
    max_val = raw.get("gauge_max", 100)

    if value is None:
        return None

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"formatter": "{a}: {c}"},
        "series": [{
            "type": "gauge",
            "min": 0, "max": max_val,
            "progress": {"show": True, "width": 16, "itemStyle": {"color": COLORS[0]}},
            "axisLine": {"lineStyle": {"width": 16, "color": [[0.3, COLORS[3]], [0.7, COLORS[4]], [1, COLORS[0]]]}},
            "axisTick": {"show": False},
            "splitLine": {"length": 10, "lineStyle": {"width": 2, "color": "#999"}},
            "axisLabel": {"distance": 22, "fontSize": 10},
            "anchor": {"show": True, "showAbove": True, "size": 20, "itemStyle": {"borderWidth": 3}},
            "detail": {
                "valueAnimation": True, "fontSize": 24, "fontWeight": "bold",
                "offsetCenter": [0, "70%"], "formatter": "{value}",
                "color": COLORS[0],
            },
            "data": [{"value": value, "name": title}]
        }]
    }


# ==============================================================
# FUNNEL CHART
# ==============================================================

def _build_funnel(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, pd.DataFrame):
        return None

    df = raw.copy().dropna(subset=[x, "value"])
    if df.empty:
        return None

    funnel_data = [
        {"name": str(r[x]), "value": round(float(r["value"]), 2)}
        for _, r in df.iterrows()
    ]

    if not funnel_data:
        return None

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c}"},
        "legend": {"bottom": 0, "type": "scroll"},
        "color": COLORS,
        "series": [{
            "type": "funnel",
            "left": "10%", "top": 50, "bottom": 40, "width": "80%",
            "min": 0, "minSize": "0%", "maxSize": "100%",
            "sort": "descending", "gap": 4,
            "label": {"show": True, "position": "inside", "fontSize": 12, "color": "#fff"},
            "itemStyle": {"borderColor": "#fff", "borderWidth": 2},
            "emphasis": {"label": {"fontSize": 14}},
            "data": funnel_data
        }]
    }


# ==============================================================
# TREEMAP CHART
# ==============================================================

def _build_treemap(ctype, raw, chart, x, hue, title):
    if not isinstance(raw, pd.DataFrame):
        return None

    df = raw.copy().dropna(subset=[x, "value"])
    if df.empty:
        return None

    if hue and hue in df.columns:
        tree_data = []
        for parent_val in df[hue].unique():
            children = []
            subset = df[df[hue] == parent_val]
            for _, r in subset.iterrows():
                children.append({"name": str(r[x]), "value": round(float(r["value"]), 2)})
            tree_data.append({"name": str(parent_val), "children": children})
    else:
        tree_data = [
            {"name": str(r[x]), "value": round(float(r["value"]), 2)}
            for _, r in df.iterrows()
        ]

    if not tree_data:
        return None

    return {
        "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14, "fontWeight": "bold"}},
        "tooltip": {"formatter": "{b}: {c}"},
        "color": COLORS,
        "series": [{
            "type": "treemap", "data": tree_data,
            "top": 40, "left": 10, "right": 10, "bottom": 10,
            "roam": False, "nodeClick": False,
            "breadcrumb": {"show": False},
            "label": {"show": True, "formatter": "{b}\n{c}", "fontSize": 11, "color": "#fff"},
            "itemStyle": {"borderColor": "#fff", "borderWidth": 2, "gapWidth": 2},
            "levels": [
                {"itemStyle": {"borderColor": "#555", "borderWidth": 3, "gapWidth": 3}},
                {"itemStyle": {"borderColor": "#ddd", "borderWidth": 1, "gapWidth": 1}},
            ]
        }]
    }
