import React, { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { fetchReportList } from '../api'
import { FiArrowLeft, FiFileText, FiFile, FiBarChart2, FiCpu, FiChevronDown, FiChevronUp } from 'react-icons/fi'
import InlineDashboard from '../components/InlineDashboard'

export default function ReportList() {
  const { reportType } = useParams()
  const navigate = useNavigate()
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedId, setExpandedId] = useState(null)     // which report has dashboard open
  const [expandedFile, setExpandedFile] = useState(null)  // which file within that report

  useEffect(() => {
    setLoading(true)
    fetchReportList(reportType)
      .then((data) => { setReports(data); setLoading(false) })
      .catch((err) => { setError(err.message); setLoading(false) })
  }, [reportType])

  const formatType = (type) =>
    type.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

  const toggleDashboard = (reportId, fileName = null) => {
    if (expandedId === reportId && expandedFile === fileName) {
      setExpandedId(null)
      setExpandedFile(null)
    } else {
      setExpandedId(reportId)
      setExpandedFile(fileName)
    }
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerInner}>
          <button onClick={() => navigate('/')} style={styles.backBtn}>
            <FiArrowLeft size={18} />
            <span>Back</span>
          </button>
          <h1 style={styles.title}>
            <FiFileText size={22} color="#f59e0b" />
            {formatType(reportType)}
          </h1>
          <span style={styles.countBadge}>{reports.length} reports</span>
        </div>
      </header>

      <div style={styles.content}>
        {loading && (
          <div style={styles.loadingGrid}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton" style={{ height: 100, borderRadius: 12 }} />
            ))}
          </div>
        )}

        {error && <div style={styles.error}>Error: {error}</div>}

        {!loading && !error && reports.length === 0 && (
          <div style={styles.empty}>No reports found for {formatType(reportType)}</div>
        )}

        {!loading && !error && reports.length > 0 && (
          <div style={styles.list}>
            {reports.map((report) => {
              const isExpanded = expandedId === report.report_id
              const hasMultipleFiles = report.excel_files && report.excel_files.length > 1

              return (
                <div key={report.report_id} style={styles.card}>
                  {/* Card header */}
                  <div style={styles.cardHeader}>
                    <div style={styles.cardIcon}>
                      <FiFile size={20} />
                    </div>
                    <div style={styles.cardInfo}>
                      <div style={styles.cardName}>{report.project_name}</div>
                      <div style={styles.cardMeta}>
                        ID: {report.report_id} &bull; {report.file_count || 1} file(s)
                      </div>
                    </div>

                    <div style={styles.cardActions}>
                      <Link to={`/reports/${reportType}/${report.report_id}`} style={styles.viewBtn}>
                        View Data
                      </Link>
                      <Link to={`/dashboard/${reportType}/${report.report_id}`} style={styles.dashBtn}>
                        <FiBarChart2 size={13} />
                        Full Dashboard
                      </Link>
                      <button
                        style={{
                          ...styles.expandBtn,
                          ...(isExpanded ? styles.expandBtnActive : {}),
                        }}
                        onClick={() => toggleDashboard(report.report_id)}
                      >
                        <FiCpu size={13} />
                        {isExpanded ? 'Close' : 'Quick AI'}
                        {isExpanded ? <FiChevronUp size={13} /> : <FiChevronDown size={13} />}
                      </button>
                    </div>
                  </div>

                  {/* File list (when multiple files) */}
                  {hasMultipleFiles && (
                    <div style={styles.fileRow}>
                      {report.excel_files.map((f) => (
                        <button
                          key={f}
                          style={{
                            ...styles.fileTag,
                            ...(isExpanded && expandedFile === f ? styles.fileTagActive : {}),
                          }}
                          onClick={() => toggleDashboard(report.report_id, f)}
                          title={`Quick AI Dashboard for ${f}`}
                        >
                          <FiCpu size={10} /> {f}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Inline Dashboard (expanded) */}
                  {isExpanded && (
                    <div style={styles.dashboardArea} className="fade-in">
                      <InlineDashboard
                        reportType={reportType}
                        reportId={report.report_id}
                        fileName={expandedFile}
                        compact={true}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

const styles = {
  container: { minHeight: '100vh' },
  header: {
    borderBottom: '1px solid var(--border)',
    background: 'var(--bg-secondary)',
  },
  headerInner: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '16px 24px',
    display: 'flex',
    alignItems: 'center',
    gap: 16,
  },
  backBtn: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 14px', background: 'var(--bg-card)',
    border: '1px solid var(--border)', borderRadius: 8,
    color: 'var(--text-primary)', fontSize: 13, fontWeight: 500, cursor: 'pointer',
  },
  title: {
    fontSize: 20, fontWeight: 700,
    display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-primary)',
  },
  countBadge: {
    marginLeft: 'auto',
    fontSize: 12, color: 'var(--text-muted)', fontWeight: 500,
    padding: '4px 10px', borderRadius: 6,
    background: 'var(--bg-card)', border: '1px solid var(--border)',
  },
  content: { maxWidth: 1200, margin: '0 auto', padding: 24 },
  loadingGrid: { display: 'flex', flexDirection: 'column', gap: 16 },
  error: {
    padding: 20, background: 'rgba(255,118,117,0.1)',
    border: '1px solid rgba(255,118,117,0.3)', borderRadius: 12,
    color: '#ff7675', textAlign: 'center',
  },
  empty: { padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 15 },
  list: { display: 'flex', flexDirection: 'column', gap: 16 },
  card: {
    background: 'var(--bg-card)',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--border)',
    overflow: 'hidden',
    transition: 'all 0.2s',
  },
  cardHeader: {
    display: 'flex', alignItems: 'center', gap: 14, padding: '16px 20px',
  },
  cardIcon: {
    width: 44, height: 44, borderRadius: 10,
    background: 'rgba(245,158,11,0.15)', color: '#f59e0b',
    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
  },
  cardInfo: { flex: 1, minWidth: 0 },
  cardName: { fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' },
  cardMeta: { fontSize: 12, color: 'var(--text-muted)', marginTop: 2 },
  cardActions: { display: 'flex', gap: 8, flexShrink: 0 },
  viewBtn: {
    padding: '7px 14px', borderRadius: 8,
    background: 'var(--bg-primary)', border: '1px solid var(--border)',
    color: 'var(--text-primary)', fontSize: 12, fontWeight: 500,
    textDecoration: 'none', transition: 'all 0.2s',
  },
  dashBtn: {
    display: 'flex', alignItems: 'center', gap: 5,
    padding: '7px 14px', borderRadius: 8,
    background: 'var(--accent-gradient)', color: '#fff',
    fontSize: 12, fontWeight: 600, textDecoration: 'none',
  },
  expandBtn: {
    display: 'flex', alignItems: 'center', gap: 4,
    padding: '7px 12px', borderRadius: 8,
    border: '1px solid var(--border)', background: 'var(--bg-primary)',
    color: 'var(--text-secondary)', fontSize: 12, fontWeight: 500, cursor: 'pointer',
    transition: 'all 0.2s',
  },
  expandBtnActive: {
    background: 'rgba(245,158,11,0.15)', color: 'var(--accent-light)',
    borderColor: 'rgba(245,158,11,0.3)',
  },
  fileRow: {
    display: 'flex', flexWrap: 'wrap', gap: 6,
    padding: '0 20px 12px',
  },
  fileTag: {
    display: 'flex', alignItems: 'center', gap: 4,
    fontSize: 11, padding: '4px 10px', borderRadius: 6,
    background: 'var(--bg-primary)', color: 'var(--text-secondary)',
    border: '1px solid var(--border)', cursor: 'pointer', transition: 'all 0.2s',
  },
  fileTagActive: {
    background: 'rgba(245,158,11,0.15)', color: 'var(--accent-light)',
    borderColor: 'rgba(245,158,11,0.3)',
  },
  dashboardArea: { padding: '0 12px 16px' },
}
