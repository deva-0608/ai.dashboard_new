import React, { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { fetchReportData, fetchReportFiles } from '../api'
import { FiArrowLeft, FiBarChart2, FiFile, FiTable, FiCpu } from 'react-icons/fi'
import InlineDashboard from '../components/InlineDashboard'

export default function ReportDetail() {
  const { reportType, reportId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [files, setFiles] = useState([])
  const [activeFile, setActiveFile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('data') // 'data' | 'dashboard'

  useEffect(() => {
    fetchReportFiles(reportType, reportId).then(setFiles).catch(() => {})
  }, [reportType, reportId])

  useEffect(() => {
    setLoading(true)
    fetchReportData(reportType, reportId, activeFile)
      .then((d) => {
        setData(d)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [reportType, reportId, activeFile])

  return (
    <div style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <div style={styles.headerInner}>
          <button onClick={() => navigate(`/reports/${reportType}`)} style={styles.backBtn}>
            <FiArrowLeft size={18} />
            <span>Back</span>
          </button>
          <div>
            <h1 style={styles.title}>{data?.project_name || 'Report Detail'}</h1>
            <span style={styles.meta}>{reportType} / ID: {reportId}</span>
          </div>
          <Link to={`/dashboard/${reportType}/${reportId}`} style={styles.fullDashBtn}>
            <FiBarChart2 size={16} />
            Full Dashboard
          </Link>
        </div>
      </header>

      <div style={styles.content}>
        {/* File selector (when multiple Excel files) */}
        {files.length > 1 && (
          <div style={styles.fileTabs}>
            <span style={styles.fileLabel}>Files:</span>
            {files.map((f, i) => (
              <button
                key={f.file_name}
                style={{
                  ...styles.fileTab,
                  ...(activeFile === f.file_name || (!activeFile && i === 0)
                    ? styles.fileTabActive
                    : {}),
                }}
                onClick={() => setActiveFile(f.file_name)}
              >
                <FiFile size={12} />
                {f.project_name}
              </button>
            ))}
          </div>
        )}

        {/* Tab bar: Data | Dashboard */}
        <div style={styles.tabs}>
          <button
            style={{ ...styles.tabBtn, ...(tab === 'data' ? styles.tabActive : {}) }}
            onClick={() => setTab('data')}
          >
            <FiTable size={14} />
            Data Preview
          </button>
          <button
            style={{ ...styles.tabBtn, ...(tab === 'dashboard' ? styles.tabActive : {}) }}
            onClick={() => setTab('dashboard')}
          >
            <FiCpu size={14} />
            AI Dashboard
          </button>
        </div>

        {/* DATA TAB */}
        {tab === 'data' && (
          <>
            {loading ? (
              <div className="skeleton" style={{ height: 400, borderRadius: 12 }} />
            ) : data ? (
              <div style={styles.tableWrap}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      {data.columns.map((col) => (
                        <th key={col} style={styles.th}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.rows.map((row, i) => (
                      <tr key={i} style={styles.tr}>
                        {data.columns.map((col) => (
                          <td key={col} style={styles.td} title={String(row[col] ?? '')}>
                            {String(row[col] ?? '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                No data available
              </div>
            )}

            {data && (
              <div style={styles.info}>
                Showing first 10 of {data.row_count} rows &bull; {data.columns.length} columns
              </div>
            )}

            {/* Inline AI Dashboard right below the data table */}
            <InlineDashboard
              reportType={reportType}
              reportId={reportId}
              fileName={activeFile}
            />
          </>
        )}

        {/* DASHBOARD TAB */}
        {tab === 'dashboard' && (
          <InlineDashboard
            reportType={reportType}
            reportId={reportId}
            fileName={activeFile}
          />
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
    maxWidth: 1400,
    margin: '0 auto',
    padding: '16px 24px',
    display: 'flex',
    alignItems: 'center',
    gap: 20,
  },
  backBtn: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 14px', background: 'var(--bg-card)',
    border: '1px solid var(--border)', borderRadius: 8,
    color: 'var(--text-primary)', fontSize: 13, fontWeight: 500, cursor: 'pointer',
  },
  title: { fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' },
  meta: { fontSize: 12, color: 'var(--text-muted)' },
  fullDashBtn: {
    marginLeft: 'auto',
    display: 'flex', alignItems: 'center', gap: 8,
    padding: '10px 20px', borderRadius: 10,
    background: 'var(--accent-gradient)', color: '#fff',
    fontWeight: 600, fontSize: 14, textDecoration: 'none',
  },
  content: { maxWidth: 1400, margin: '0 auto', padding: 24 },
  fileTabs: {
    display: 'flex', alignItems: 'center', gap: 8,
    marginBottom: 16, overflowX: 'auto', paddingBottom: 4,
  },
  fileLabel: { fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, flexShrink: 0 },
  fileTab: {
    display: 'flex', alignItems: 'center', gap: 5,
    padding: '7px 14px', borderRadius: 8,
    border: '1px solid var(--border)', background: 'var(--bg-card)',
    color: 'var(--text-secondary)', fontSize: 12, fontWeight: 500,
    cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.2s',
  },
  fileTabActive: { background: 'var(--accent)', color: '#fff', borderColor: 'var(--accent)' },
  tabs: {
    display: 'flex', gap: 4, marginBottom: 20,
    background: 'var(--bg-secondary)', borderRadius: 10, padding: 4,
    border: '1px solid var(--border)', width: 'fit-content',
  },
  tabBtn: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 18px', borderRadius: 8, border: 'none',
    background: 'transparent', color: 'var(--text-muted)',
    fontSize: 13, fontWeight: 500, cursor: 'pointer', transition: 'all 0.2s',
  },
  tabActive: {
    background: 'var(--bg-card)', color: 'var(--text-primary)',
    boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
  },
  tableWrap: {
    overflowX: 'auto', borderRadius: 12,
    border: '1px solid var(--border)', background: 'var(--bg-card)',
  },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 13 },
  th: {
    padding: '12px 14px', textAlign: 'left',
    background: 'var(--bg-secondary)', color: 'var(--text-secondary)',
    fontWeight: 600, fontSize: 11, textTransform: 'uppercase',
    letterSpacing: '0.05em', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap',
  },
  tr: { borderBottom: '1px solid var(--border)' },
  td: {
    padding: '10px 14px', color: 'var(--text-primary)',
    maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  info: { marginTop: 12, fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' },
}
