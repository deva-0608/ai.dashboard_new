import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Responsive, WidthProvider } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import { chatWithDashboard, fetchReportFiles } from '../api'
import ChartWidget from '../components/ChartWidget'
import KPICard from '../components/KPICard'
import ChatPanel from '../components/ChatPanel'
import { FiArrowLeft, FiCpu, FiGrid, FiZap, FiBarChart2, FiMessageCircle } from 'react-icons/fi'
import FormulaBuilder from '../components/FormulaBuilder'

const ResponsiveGridLayout = WidthProvider(Responsive)

function generateId() {
  return Math.random().toString(36).substr(2, 9)
}

export default function AIDashboard() {
  const { reportType, reportId } = useParams()
  const navigate = useNavigate()

  const [sessionId] = useState(() => `session-${generateId()}`)
  const [files, setFiles] = useState([])
  const [activeFile, setActiveFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [charts, setCharts] = useState([])
  const [kpis, setKpis] = useState([])
  const [summary, setSummary] = useState('')
  const [messages, setMessages] = useState([])
  const [chartLayouts, setChartLayouts] = useState({})
  const [projectName, setProjectName] = useState('')
  const [stats, setStats] = useState({ charts: 0, kpis: 0 })
  const [suggestions, setSuggestions] = useState([])

  useEffect(() => {
    fetchReportFiles(reportType, reportId)
      .then(setFiles)
      .catch(() => {})
  }, [reportType, reportId])

  const generateChartLayout = useCallback((chartList) => {
    const items = []
    const cols = 12
    let curY = 0, curX = 0

    chartList.forEach((chart) => {
      // Smart sizing by chart type
      let w, h
      switch (chart.type) {
        case 'pie':
        case 'gauge':
        case 'funnel':
          w = 4; h = 5; break
        case 'heatmap':
        case 'radar':
          w = 6; h = 6; break
        case 'boxplot':
          w = 6; h = 6; break
        case 'histogram':
          w = 6; h = 5; break
        case 'forecast':
          w = 8; h = 6; break
        case 'treemap':
          w = 6; h = 5; break
        case 'scatter':
          w = 6; h = 5; break
        default: // bar, line, area
          w = 6; h = 5; break
      }

      // If it won't fit on this row, go to next
      if (curX + w > cols) {
        curX = 0
        curY += h
      }

      items.push({
        i: `chart-${chart.id}`,
        x: curX, y: curY, w, h,
        minW: 3, minH: 3,
      })

      curX += w
      if (curX >= cols) {
        curX = 0
        curY += h
      }
    })

    return { lg: items, md: items, sm: items.map(it => ({ ...it, w: 12, x: 0 })) }
  }, [])

  const handleSend = useCallback(async (text) => {
    if (!text.trim()) return

    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)

    try {
      const data = await chatWithDashboard(reportType, reportId, text, sessionId, activeFile)

      setProjectName(data.project_name || '')
      setCharts(data.charts || [])
      setKpis(data.kpis || [])
      setSummary(data.summary || '')
      setStats({ charts: data.chart_count || 0, kpis: data.kpi_count || 0 })
      setChartLayouts(generateChartLayout(data.charts || []))
      setSuggestions(data.suggested_prompts || [])

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: data.summary || 'Dashboard generated.' },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Error: ${err.message}` },
      ])
    } finally {
      setLoading(false)
    }
  }, [reportType, reportId, sessionId, activeFile, generateChartLayout])

  const hasDashboard = charts.length > 0 || kpis.length > 0

  return (
    <div style={styles.wrapper}>
      {/* ── HEADER ── */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <button onClick={() => navigate(`/reports/${reportType}`)} style={styles.backBtn}>
            <FiArrowLeft size={16} />
          </button>
          <div style={styles.titleBlock}>
            <div style={styles.headerTitle}>
              <FiCpu size={18} color="#f59e0b" />
              <span>{projectName || 'AI Dashboard'}</span>
            </div>
            <div style={styles.headerMeta}>
              {reportType} / #{reportId}
              {stats.charts > 0 && (
                <span style={styles.statPill}>
                  <FiBarChart2 size={11} /> {stats.charts} charts &bull; {stats.kpis} KPIs
                </span>
              )}
            </div>
          </div>
        </div>

        {/* File selector */}
        {files.length > 1 && (
          <div style={styles.fileTabs}>
            {files.map((f) => (
              <button
                key={f.file_name}
                style={{
                  ...styles.fileTab,
                  ...(activeFile === f.file_name ? styles.fileTabActive : {}),
                }}
                onClick={() => setActiveFile(f.file_name)}
              >
                {f.project_name}
              </button>
            ))}
          </div>
        )}

        <div style={styles.headerRight}>
          <FormulaBuilder
            reportType={reportType}
            reportId={reportId}
            sessionId={sessionId}
            fileName={activeFile}
            onColumnAdded={(result) => {
              setMessages((prev) => [...prev, {
                role: 'assistant',
                content: `Custom column "${result.column_name}" created with ${result.total_rows} values. It will be available in your next analysis.`,
              }])
            }}
          />
          <div style={styles.badge}>
            <FiGrid size={12} />
            <span>Drag to rearrange</span>
          </div>
        </div>
      </header>

      {/* ── MAIN AREA ── */}
      <div style={styles.main}>
        <div style={styles.dashboardArea}>

          {/* EMPTY STATE */}
          {!hasDashboard && !loading && (
            <div style={styles.emptyState}>
              <div style={styles.emptyIcon}>
                <FiZap size={36} color="#f59e0b" />
              </div>
              <h3 style={styles.emptyTitle}>Ask anything about your data</h3>
              <p style={styles.emptyDesc}>
                Type a question in the chat or click a quick start prompt below.
                The AI will generate a complete dashboard.
              </p>
              <div style={styles.promptRow}>
                {[
                  'Give me a complete overview of this data',
                  'Show trends and distributions',
                  'Compare categories with grouped analysis',
                ].map((p) => (
                  <button key={p} style={styles.promptBtn} onClick={() => handleSend(p)}>
                    <FiZap size={12} /> {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* LOADING */}
          {loading && (
            <div style={styles.loadingWrap}>
              <div className="loading-pulse" style={styles.loadingInner}>
                <FiCpu size={22} color="#f59e0b" />
                <span>AI agents are analyzing your data...</span>
              </div>
            </div>
          )}

          {/* ── KPI ROW (separate, not in grid) ── */}
          {kpis.length > 0 && (
            <div style={styles.section}>
              <div style={styles.sectionLabel}>Key Metrics</div>
              <div style={{
                ...styles.kpiGrid,
                gridTemplateColumns: `repeat(${Math.min(kpis.length, 4)}, 1fr)`,
              }}>
                {kpis.map((kpi, i) => (
                  <KPICard key={i} kpi={kpi} index={i} />
                ))}
              </div>
            </div>
          )}

          {/* ── SUMMARY ── */}
          {summary && (
            <div style={styles.summaryCard}>
              <div style={styles.summaryHeader}>
                <FiMessageCircle size={14} color="#f59e0b" />
                <span style={styles.summaryLabel}>AI Insight</span>
              </div>
              <div style={styles.summaryText}>
                {summary.split('\n').map((line, i) => (
                  <p key={i} style={{ margin: '3px 0' }}>{line}</p>
                ))}
              </div>
            </div>
          )}

          {/* ── CHART GRID (draggable) ── */}
          {charts.length > 0 && (
            <div style={styles.section}>
              <div style={styles.sectionLabel}>Charts</div>
              <ResponsiveGridLayout
                className="layout"
                layouts={chartLayouts}
                breakpoints={{ lg: 1200, md: 900, sm: 600 }}
                cols={{ lg: 12, md: 8, sm: 4 }}
                rowHeight={65}
                onLayoutChange={(_, all) => setChartLayouts(all)}
                draggableHandle=".drag-handle"
                isResizable={true}
                isDraggable={true}
                compactType="vertical"
                margin={[16, 16]}
              >
                {charts.map((chart) => (
                  <div key={`chart-${chart.id}`} style={{ height: '100%' }}>
                    <ChartWidget chart={chart} />
                  </div>
                ))}
              </ResponsiveGridLayout>
            </div>
          )}
        </div>

        {/* ── CHAT PANEL ── */}
        <ChatPanel
          messages={messages}
          onSend={handleSend}
          loading={loading}
          summary={summary}
          suggestions={suggestions}
        />
      </div>
    </div>
  )
}

const styles = {
  wrapper: { height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg-primary)' },

  // Header
  header: {
    display: 'flex', alignItems: 'center', padding: '12px 24px',
    background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)',
    gap: 16, flexShrink: 0,
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 14 },
  backBtn: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    width: 38, height: 38, borderRadius: 10,
    background: 'var(--bg-primary)', border: '1px solid var(--border)',
    color: 'var(--text-primary)', cursor: 'pointer', transition: 'all 0.15s',
  },
  titleBlock: { display: 'flex', flexDirection: 'column', gap: 2 },
  headerTitle: {
    display: 'flex', alignItems: 'center', gap: 8,
    fontSize: 17, fontWeight: 700, color: 'var(--text-primary)',
  },
  headerMeta: {
    display: 'flex', alignItems: 'center', gap: 10,
    fontSize: 12, color: 'var(--text-muted)',
  },
  statPill: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '2px 8px', borderRadius: 5, fontSize: 11, fontWeight: 600,
    background: 'rgba(245,158,11,0.12)', color: '#d97706',
  },
  fileTabs: { display: 'flex', gap: 6, marginLeft: 8 },
  fileTab: {
    padding: '6px 14px', borderRadius: 8,
    border: '1px solid var(--border)', background: 'var(--bg-primary)',
    color: 'var(--text-secondary)', fontSize: 12, fontWeight: 500,
    cursor: 'pointer', transition: 'all 0.15s',
  },
  fileTabActive: { background: 'var(--accent)', color: '#fff', borderColor: 'var(--accent)' },
  headerRight: { marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 },
  badge: {
    display: 'flex', alignItems: 'center', gap: 5,
    padding: '6px 12px', borderRadius: 8,
    background: 'var(--bg-primary)', border: '1px solid var(--border)',
    color: 'var(--text-muted)', fontSize: 11, fontWeight: 500,
  },

  // Main
  main: { flex: 1, display: 'flex', overflow: 'hidden' },
  dashboardArea: { flex: 1, overflowY: 'auto', padding: '20px 24px 60px' },

  // Empty state
  emptyState: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '70vh', gap: 16, textAlign: 'center',
  },
  emptyIcon: {
    width: 72, height: 72, borderRadius: 20,
    background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  emptyTitle: { fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', marginTop: 4 },
  emptyDesc: { fontSize: 14, color: 'var(--text-secondary)', maxWidth: 440, lineHeight: 1.7 },
  promptRow: { display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12, width: '100%', maxWidth: 420 },
  promptBtn: {
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '11px 18px', borderRadius: 10,
    background: 'var(--bg-card)', border: '1px solid var(--border)',
    color: 'var(--accent-light)', fontSize: 13, fontWeight: 500,
    cursor: 'pointer', transition: 'all 0.15s', textAlign: 'left',
  },

  // Loading
  loadingWrap: { display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 60 },
  loadingInner: {
    display: 'flex', alignItems: 'center', gap: 12,
    fontSize: 15, color: 'var(--text-secondary)', fontWeight: 500,
  },

  // Section headers
  section: { marginBottom: 24 },
  sectionLabel: {
    fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
    letterSpacing: '0.08em', color: 'var(--text-muted)', marginBottom: 12,
    paddingLeft: 2,
  },

  // KPI grid — separate from react-grid-layout
  kpiGrid: {
    display: 'grid', gap: 16,
  },

  // Summary card
  summaryCard: {
    background: 'var(--bg-card)', borderRadius: 12, border: '1px solid var(--border)',
    padding: '16px 20px', marginBottom: 24, boxShadow: 'var(--shadow-sm)',
  },
  summaryHeader: {
    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10,
  },
  summaryLabel: { fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' },
  summaryText: { fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 },
}
