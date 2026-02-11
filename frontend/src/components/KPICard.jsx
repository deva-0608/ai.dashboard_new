import React from 'react'
import { FiTrendingUp, FiHash, FiDollarSign, FiPercent, FiActivity } from 'react-icons/fi'

const KPI_ICONS = [FiTrendingUp, FiDollarSign, FiHash, FiPercent, FiActivity]

const KPI_COLORS = [
  { bg: '#fef3c7', text: '#d97706', accent: '#f59e0b' },
  { bg: '#d1fae5', text: '#059669', accent: '#10b981' },
  { bg: '#dbeafe', text: '#2563eb', accent: '#3b82f6' },
  { bg: '#fce7f3', text: '#db2777', accent: '#ec4899' },
  { bg: '#ede9fe', text: '#7c3aed', accent: '#8b5cf6' },
]

function formatValue(val) {
  if (val === null || val === undefined) return 'N/A'
  if (typeof val === 'number') {
    if (Math.abs(val) >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`
    if (Math.abs(val) >= 1_000) return `${(val / 1_000).toFixed(1)}K`
    return val.toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  return String(val)
}

export default function KPICard({ kpi, index = 0 }) {
  const theme = KPI_COLORS[index % KPI_COLORS.length]
  const Icon = KPI_ICONS[index % KPI_ICONS.length]

  return (
    <div style={styles.card}>
      <div style={styles.row}>
        <div style={{ ...styles.iconBox, background: theme.bg }}>
          <Icon size={16} color={theme.text} />
        </div>
        <div style={styles.info}>
          <div style={styles.label}>{kpi.name}</div>
          <div style={{ ...styles.value, color: theme.text }}>
            {formatValue(kpi.value)}
          </div>
        </div>
      </div>
      <div style={{ ...styles.bar, background: theme.bg }}>
        <div style={{ ...styles.barFill, background: theme.accent, width: '65%' }} />
      </div>
    </div>
  )
}

const styles = {
  card: {
    background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb',
    padding: '16px 18px 12px', display: 'flex', flexDirection: 'column',
    gap: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    transition: 'all 0.15s',
  },
  row: { display: 'flex', alignItems: 'center', gap: 12 },
  iconBox: {
    width: 38, height: 38, borderRadius: 10,
    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  },
  info: { flex: 1, minWidth: 0 },
  label: {
    fontSize: 11, fontWeight: 600, color: '#6b7280',
    textTransform: 'uppercase', letterSpacing: '0.04em',
    lineHeight: 1.2, marginBottom: 2,
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  value: { fontSize: 24, fontWeight: 800, letterSpacing: '-0.02em', lineHeight: 1.1 },
  bar: { height: 4, borderRadius: 2, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 2, transition: 'width 0.5s ease' },
}
