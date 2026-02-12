from state import DashboardState
from pipeline.a2a_protocol import A2ABus

from pipeline.agents.memory_agent import memory_agent
from pipeline.agents.schema_profiler_agent import schema_profiler_agent
from pipeline.agents.data_enrichment_agent import data_enrichment_agent
from pipeline.agents.intent_agent import intent_agent
from pipeline.agents.planner_agent import planner_agent
from pipeline.agents.aggregator_agent import aggregator_agent
from pipeline.agents.chart_agent import chart_agent
from pipeline.agents.forecasting_agent import forecasting_agent
from pipeline.agents.insight_agent import insight_agent


def run_dashboard_pipeline(state: DashboardState) -> DashboardState:
    """
    Runs the full AI dashboard pipeline with A2A protocol.

    Pipeline:
     1. Memory Agent       — loads session context, publishes memory to A2A bus
     2. Schema Profiler    — analyzes data structure, shares schema via A2A
     3. Data Enrichment    — creates derived columns (duration, rates, bins)
     4. Intent Agent       — classifies user intent, shares with planner via A2A
     5. Planner Agent      — generates analytics plan (5-7 charts, 2-4 KPIs)
     6. Aggregator Agent   — executes data aggregations
     7. Chart Agent        — converts to ECharts specs, publishes chart context
     8. Forecasting Agent  — time-series forecasting (appends forecast charts)
     9. Insight Agent      — generates summary, persists insights to session
    """

    # Initialize A2A bus for inter-agent communication
    state["a2a_bus"] = A2ABus()

    # 1. Conversation memory (loads session + publishes context)
    print("[Pipeline] 1/9 Memory Agent...")
    state = memory_agent(state)

    # 2. Dataset understanding (shares schema via A2A)
    print("[Pipeline] 2/9 Schema Profiler...")
    state = schema_profiler_agent(state)

    # 3. Data enrichment (derived columns, hue candidates)
    print("[Pipeline] 3/9 Data Enrichment...")
    state = data_enrichment_agent(state)

    # 4. User intent reasoning (shares intent via A2A)
    print("[Pipeline] 4/9 Intent Agent...")
    state = intent_agent(state)

    # 5. Analytics planning (reads A2A context, plans 5-7 charts + 2-4 KPIs)
    print("[Pipeline] 5/9 Planner Agent...")
    state = planner_agent(state)

    # 6. Generic data aggregation
    print("[Pipeline] 6/9 Aggregator Agent...")
    state = aggregator_agent(state)

    # 7. Convert to ECharts-ready format (publishes chart context to A2A)
    print("[Pipeline] 7/9 Chart Agent...")
    state = chart_agent(state)

    # 8. Time-series forecasting (appends forecast charts if date+numeric data exists)
    print("[Pipeline] 8/9 Forecasting Agent...")
    state = forecasting_agent(state)

    # Track previous charts
    state["previous_charts"] = [
        c["id"] for c in state.get("charts", []) if "id" in c
    ]

    # 9. Generate insights / summary (persists to session memory)
    print("[Pipeline] 9/9 Insight Agent...")
    state = insight_agent(state)

    print(f"[Pipeline] Complete: {len(state.get('charts', []))} charts, {len(state.get('kpis', []))} KPIs")

    return state
