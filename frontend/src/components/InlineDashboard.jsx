import React, { useState, useCallback } from 'react'
import { Responsive, WidthProvider } from 'react-grid-layout'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import { chatWithDashboard } from '../api'
import ChartWidget from './ChartWidget'
import KPICard from './KPICard'
import { FiSend, FiCpu, FiUser, FiGrid, FiZap, FiMessageCircle, FiArrowRight } from 'react-icons/fi'

const ResponsiveGridLayout = WidthProvider(Responsive)

function genId() {
  return Math.random().toString(36).substr(2, 9)
}

export default function InlineDashboard({ reportType, reportId, fileName = null, compact = false }) {
  const [sessionId] = useState(() => `inline-${genId()}`)
  const [loading, setLoading] = useState(false)
  const [charts, setCharts] = useState([])
  const [kpis, setKpis] = useState([])
  const [summary, setSummary] = useState('')
  const [messages, setMessages] = useState([])
  const [chartLayouts, setChartLayouts] = useState({})
  const [input, setInput] = useState('')
  const [showChat, setShowChat] = useState(false)
  const [suggestions, setSuggestions] = useState([])

  const generateChartLayout = useCallback((chartList) => {
    const items = []
    const cols = 12
    let curY = 0, curX = 0

    chartList.forEach((chart) => {
      let w, h
      switch (chart.type) {
        case 'pie': case 'gauge': case 'funnel': w = 4; h = 5; break
        case 'heatmap': case 'radar': case 'boxplot': w = 6; h = 6; break
        case 'histogram': w = 6; h = 5; break
        case 'forecast': w = 8; h = 6; break
        default: w = 6; h = 5; break
      }
      if (curX + w > cols) { curX = 0; curY += h }
      items.push({ i: `chart-${chart.id}`, x: curX, y: curY, w, h, minW: 3, minH: 3 })
      curX += w
      if (curX >= cols) { curX = 0; curY += h }
    })

    return { lg: items, md: items, sm: items.map(it => ({ ...it, w: 12, x: 0 })) }
  }, [])

  const handleSend = useCallback(async (text) => {
    if (!text.trim()) return
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const data = await chatWithDashboard(reportType, reportId, text, sessionId, fileName)
      setCharts(data.charts || [])
      setKpis(data.kpis || [])
      setSummary(data.summary || '')
      setChartLayouts(generateChartLayout(data.charts || []))
      setSuggestions(data.suggested_prompts || [])
      setMessages((prev) => [...prev, { role: 'assistant', content: data.summary || 'Dashboard generated.' }])
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${err.message}` }])
    } finally {
      setLoading(false)
    }
  }, [reportType, reportId, sessionId, fileName, generateChartLayout])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    handleSend(input.trim())
    setInput('')
  }

  const hasDashboard = charts.length > 0 || kpis.length > 0

  return (
    <div style={styles.wrapper}>
      {/* ── Toolbar ── */}
      <div style={styles.toolbar}>
        <div style={styles.toolbarLeft}>
          <FiCpu size={15} color="#f59e0b" />
          <span style={styles.toolbarTitle}>AI Dashboard</span>
          {hasDashboard && (
            <span style={styles.statBadge}>{charts.length} charts &bull; {kpis.length} KPIs</span>
          )}
        </div>
        <div style={styles.toolbarRight}>
          {hasDashboard && (
            <span style={styles.dragHint}><FiGrid size={11} /> Drag to rearrange</span>
          )}
          <button
            style={{ ...styles.chatToggle, ...(showChat ? styles.chatToggleActive : {}) }}
            onClick={() => setShowChat(!showChat)}
          >
            <FiMessageCircle size={13} />
            {showChat ? 'Hide' : 'Chat'}
          </button>
        </div>
      </div>

      {/* ── Quick Start ── */}
      {!hasDashboard && !loading && (
        <div style={styles.quickStart}>
          <p style={styles.quickDesc}>Generate an AI dashboard from this data</p>
          <div style={styles.prompts}>
            {['Complete overview', 'Trends & distributions', 'Compare categories'].map((p) => (
              <button key={p} style={styles.promptBtn} onClick={() => handleSend(p)}>
                <FiZap size={11} /> {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div style={styles.loadingBar}>
          <div className="loading-pulse" style={styles.loadingText}>
            <FiCpu size={15} /> Agents analyzing data...
          </div>
        </div>
      )}

      {/* ── KPI Row ── */}
      {kpis.length > 0 && (
        <div style={styles.kpiSection}>
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

      {/* ── Summary ── */}
      {summary && (
        <div style={styles.summaryWrap}>
          <div style={styles.summaryCard}>
            <span style={styles.summaryLabel}><FiMessageCircle size={12} color="#f59e0b" /> Insight</span>
            <div style={styles.summaryText}>
              {summary.split('\n').slice(0, 4).map((l, i) => <p key={i} style={{ margin: '2px 0' }}>{l}</p>)}
            </div>
          </div>
        </div>
      )}

      {/* ── Chart Grid ── */}
      {charts.length > 0 && (
        <div style={styles.dashArea}>
          <ResponsiveGridLayout
            className="layout"
            layouts={chartLayouts}
            breakpoints={{ lg: 1200, md: 900, sm: 600 }}
            cols={{ lg: 12, md: 8, sm: 4 }}
            rowHeight={60}
            onLayoutChange={(_, all) => setChartLayouts(all)}
            draggableHandle=".drag-handle"
            isResizable={true}
            isDraggable={true}
            compactType="vertical"
            margin={[14, 14]}
          >
            {charts.map((chart) => (
              <div key={`chart-${chart.id}`} style={{ height: '100%' }}>
                <ChartWidget chart={chart} />
              </div>
            ))}
          </ResponsiveGridLayout>
        </div>
      )}

      {/* ── Chat Panel ── */}
      {showChat && (
        <div style={styles.chatPanel}>
          <div style={styles.chatMessages}>
            {messages.length === 0 && (
              <div style={styles.chatEmpty}>Ask anything about the data...</div>
            )}
            {messages.map((m, i) => (
              <div key={i} style={styles.msgRow}>
                <div style={{
                  ...styles.avatar,
                  background: m.role === 'user' ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.15)',
                }}>
                  {m.role === 'user'
                    ? <FiUser size={11} color="#d97706" />
                    : <FiCpu size={11} color="#10b981" />}
                </div>
                <div style={{ ...styles.bubble, ...(m.role === 'user' ? styles.userBub : styles.aiBub) }}>
                  {m.content.split('\n').map((l, j) => <p key={j} style={{ margin: '2px 0' }}>{l}</p>)}
                </div>
              </div>
            ))}
            {/* ── Inline suggestions ── */}
            {!loading && suggestions.length > 0 && messages.length > 0 && (
              <div style={styles.inlineSuggest}>
                <div style={styles.suggestLabel}><FiZap size={10} color="#f59e0b" /> Try asking</div>
                <div style={styles.suggestRow}>
                  {suggestions.map((s, i) => (
                    <button key={i} style={styles.suggestChip} onClick={() => { handleSend(s) }}>{s}</button>
                  ))}
                </div>
              </div>
            )}
          </div>
          <form onSubmit={handleSubmit} style={styles.chatInput}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about the data..."
              disabled={loading}
              style={styles.input}
            />
            <button type="submit" disabled={loading || !input.trim()} style={styles.sendBtn}>
              <FiSend size={13} />
            </button>
          </form>
        </div>
      )}
    </div>
  )
}

const styles = {
  wrapper: {
    background: 'var(--bg-card)', borderRadius: 14,
    border: '1px solid var(--border)', overflow: 'hidden', marginTop: 20,
  },
  toolbar: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '10px 18px', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)',
  },
  toolbarLeft: { display: 'flex', alignItems: 'center', gap: 8 },
  toolbarTitle: { fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' },
  statBadge: {
    fontSize: 10, color: '#d97706', fontWeight: 600,
    padding: '2px 7px', borderRadius: 5,
    background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.15)',
  },
  toolbarRight: { display: 'flex', alignItems: 'center', gap: 10 },
  dragHint: { display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: 'var(--text-muted)', fontWeight: 500 },
  chatToggle: {
    display: 'flex', alignItems: 'center', gap: 4,
    padding: '5px 11px', borderRadius: 7,
    border: '1px solid var(--border)', background: 'var(--bg-card)',
    color: 'var(--text-secondary)', fontSize: 11, fontWeight: 500, cursor: 'pointer',
  },
  chatToggleActive: { background: 'var(--accent)', color: '#fff', borderColor: 'var(--accent)' },

  quickStart: { padding: '20px 18px', textAlign: 'center' },
  quickDesc: { fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 },
  prompts: { display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' },
  promptBtn: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '7px 14px', borderRadius: 8,
    border: '1px solid var(--border)', background: 'var(--bg-primary)',
    color: 'var(--accent-light)', fontSize: 12, fontWeight: 500, cursor: 'pointer',
  },

  loadingBar: { padding: '18px', textAlign: 'center' },
  loadingText: { display: 'inline-flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--accent-light)', fontWeight: 500 },

  kpiSection: { padding: '14px 18px 0' },
  kpiGrid: { display: 'grid', gap: 12 },

  summaryWrap: { padding: '12px 18px 0' },
  summaryCard: {
    background: 'var(--bg-primary)', borderRadius: 10, border: '1px solid var(--border)',
    padding: '12px 16px',
  },
  summaryLabel: {
    display: 'flex', alignItems: 'center', gap: 6,
    fontSize: 10, fontWeight: 700, color: 'var(--text-muted)',
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8,
  },
  summaryText: { fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 },

  dashArea: { padding: '8px 8px 16px' },

  chatPanel: {
    borderTop: '1px solid var(--border)', background: 'var(--bg-secondary)',
    maxHeight: 320, display: 'flex', flexDirection: 'column',
  },
  chatMessages: {
    flex: 1, overflowY: 'auto', padding: '10px 14px',
    display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 240,
  },
  chatEmpty: { fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', padding: 14 },
  msgRow: { display: 'flex', gap: 6, alignItems: 'flex-start' },
  avatar: {
    width: 22, height: 22, borderRadius: 6,
    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  },
  bubble: { maxWidth: '88%', padding: '7px 11px', borderRadius: 9, fontSize: 11, lineHeight: 1.5 },
  userBub: {
    background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.15)',
    color: 'var(--text-primary)', borderTopLeftRadius: 2,
  },
  aiBub: {
    background: 'var(--bg-card)', border: '1px solid var(--border)',
    color: 'var(--text-primary)', borderTopLeftRadius: 2,
  },
  chatInput: {
    display: 'flex', gap: 6, padding: '8px 14px',
    borderTop: '1px solid var(--border)', alignItems: 'center',
  },
  input: {
    flex: 1, background: 'var(--bg-input)', color: 'var(--text-primary)',
    fontSize: 12, outline: 'none', padding: '7px 11px', borderRadius: 7,
    border: '1px solid var(--border)', fontFamily: 'Inter, sans-serif',
  },
  sendBtn: {
    width: 30, height: 30, borderRadius: 7,
    background: 'var(--accent)', color: '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    border: 'none', cursor: 'pointer', flexShrink: 0,
  },

  // Inline suggestions
  inlineSuggest: { padding: '4px 0 2px', marginLeft: 28 },
  suggestLabel: {
    display: 'flex', alignItems: 'center', gap: 4,
    fontSize: 9, fontWeight: 600, color: 'var(--text-muted)',
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6,
  },
  suggestRow: { display: 'flex', flexDirection: 'column', gap: 4 },
  suggestChip: {
    display: 'flex', alignItems: 'center', gap: 5,
    padding: '6px 11px', borderRadius: 8,
    background: 'linear-gradient(135deg, rgba(245,158,11,0.06), rgba(251,191,36,0.10))',
    border: '1px solid rgba(245,158,11,0.18)',
    color: '#92400e', fontSize: 11, fontWeight: 500,
    cursor: 'pointer', transition: 'all 0.18s', textAlign: 'left',
    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%',
  },
}
