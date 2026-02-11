import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { fetchHealth } from '../api'
import { FiBarChart2, FiFileText, FiFolder, FiCpu, FiActivity } from 'react-icons/fi'

const REPORT_TYPES = [
  {
    id: 'project-report',
    name: 'Project Report',
    desc: 'Analyze project data with AI-powered insights and visualizations',
    icon: <FiBarChart2 size={28} />,
    color: '#f59e0b',
  },
  {
    id: 'document-report',
    name: 'Document Report',
    desc: 'Generate intelligent reports from document-based Excel data',
    icon: <FiFileText size={28} />,
    color: '#10b981',
  },
  {
    id: 'custom-report',
    name: 'Custom Report',
    desc: 'Create custom dashboards from any Excel dataset',
    icon: <FiFolder size={28} />,
    color: '#3b82f6',
  },
]

export default function Home() {
  const [health, setHealth] = useState(null)

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth({ status: 'error' }))
  }, [])

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerContent}>
          <div style={styles.logo}>
            <FiCpu size={32} color="#f59e0b" />
            <h1 style={styles.title}>AI Dashboard</h1>
          </div>
          <div style={styles.status}>
            <FiActivity size={14} color={health?.status === 'ok' ? '#10b981' : '#ef4444'} />
            <span style={{
              fontSize: 12,
              color: health?.status === 'ok' ? '#10b981' : '#ef4444',
              fontWeight: 500,
            }}>
              {health?.status === 'ok'
                ? `Connected — ${health?.llm?.provider || 'unknown'} / ${health?.llm?.model || 'loading'}`
                : 'Backend offline'}
            </span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <div style={styles.hero}>
        <h2 style={styles.heroTitle}>Intelligent Data Analytics</h2>
        <p style={styles.heroSub}>
          Upload Excel data, ask questions in natural language, and get instant
          AI-generated dashboards with draggable charts and smart insights.
        </p>
      </div>

      {/* Cards */}
      <div style={styles.grid}>
        {REPORT_TYPES.map((rt) => (
          <Link key={rt.id} to={`/reports/${rt.id}`} style={{ textDecoration: 'none' }}>
            <div
              style={{ ...styles.card, borderTop: `3px solid ${rt.color}` }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-4px)'
                e.currentTarget.style.boxShadow = `0 8px 28px rgba(0,0,0,0.10), 0 0 16px ${rt.color}22`
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.06)'
              }}
            >
              <div style={{ ...styles.cardIcon, background: `${rt.color}15`, color: rt.color }}>
                {rt.icon}
              </div>
              <h3 style={styles.cardTitle}>{rt.name}</h3>
              <p style={styles.cardDesc}>{rt.desc}</p>
              <div style={{ ...styles.cardArrow, color: rt.color }}>Open Reports &rarr;</div>
            </div>
          </Link>
        ))}
      </div>

      {/* Footer */}
      <div style={styles.footer}>
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
          Powered by LangGraph + ECharts + React
        </span>
      </div>
    </div>
  )
}

const styles = {
  container: { minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center' },
  header: { width: '100%', borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)' },
  headerContent: {
    maxWidth: 1200, margin: '0 auto', padding: '16px 24px',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  logo: { display: 'flex', alignItems: 'center', gap: 12 },
  title: {
    fontSize: 22, fontWeight: 800,
    background: 'linear-gradient(135deg, #f59e0b, #d97706)',
    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
  },
  status: {
    display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
    background: 'var(--bg-primary)', borderRadius: 20, border: '1px solid var(--border)',
  },
  hero: { textAlign: 'center', padding: '60px 24px 40px', maxWidth: 700 },
  heroTitle: {
    fontSize: 36, fontWeight: 800, marginBottom: 16, color: 'var(--text-primary)',
  },
  heroSub: { fontSize: 16, color: 'var(--text-secondary)', lineHeight: 1.7 },
  grid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: 24, maxWidth: 1100, width: '100%', padding: '0 24px',
  },
  card: {
    background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', padding: 28,
    boxShadow: '0 4px 12px rgba(0,0,0,0.06)', transition: 'all 0.2s', cursor: 'pointer',
  },
  cardIcon: {
    width: 52, height: 52, borderRadius: 12,
    display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 16,
  },
  cardTitle: { fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 },
  cardDesc: { fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 },
  cardArrow: { fontSize: 13, fontWeight: 600 },
  footer: { marginTop: 'auto', padding: 24, textAlign: 'center' },
}
