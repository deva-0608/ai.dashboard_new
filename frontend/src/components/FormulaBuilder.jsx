import React, { useState, useEffect, useMemo } from 'react'
import { FiPlus, FiX, FiCheck, FiAlertCircle, FiCode, FiChevronDown, FiChevronUp, FiCalendar } from 'react-icons/fi'
import { addCustomColumn, fetchFormulaSuggestions } from '../api'

export default function FormulaBuilder({ reportType, reportId, sessionId, fileName, onColumnAdded }) {
  const [isOpen, setIsOpen] = useState(false)
  const [formula, setFormula] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [columns, setColumns] = useState({})
  const [showColumns, setShowColumns] = useState(false)
  const [pendingDateCol, setPendingDateCol] = useState(null) // for 2-click date_diff

  useEffect(() => {
    if (isOpen && suggestions.length === 0) {
      fetchFormulaSuggestions(reportType, reportId, fileName)
        .then((data) => {
          setSuggestions(data.suggestions || [])
          setColumns(data.columns || {})
        })
        .catch(() => {})
    }
  }, [isOpen, reportType, reportId, fileName])

  // Dynamic placeholder based on actual columns
  const dynamicPlaceholder = useMemo(() => {
    const dates = columns.datetime || []
    const nums = columns.numeric || []
    if (dates.length >= 2) {
      return `Duration = date_diff(${dates[0]}, ${dates[1]})`
    }
    if (nums.length >= 2) {
      return `Result = ${nums[0]} * ${nums[1]}`
    }
    if (nums.length >= 1) {
      return `Doubled = ${nums[0]} * 2`
    }
    return 'new_column = column1 * column2'
  }, [columns])

  // Dynamic hint examples based on actual columns
  const hintExamples = useMemo(() => {
    const dates = columns.datetime || []
    const nums = columns.numeric || []
    const parts = []
    if (nums.length >= 2) {
      parts.push({ label: 'Arithmetic', example: `${nums[0]} * ${nums[1]}` })
    }
    if (dates.length >= 2) {
      parts.push({ label: 'Duration', example: `date_diff(${dates[0]}, ${dates[1]})` })
    } else if (dates.length === 1 && nums.length >= 1) {
      parts.push({ label: 'Example', example: `${nums[0]} / ${nums[0]}.sum() * 100` })
    }
    return parts
  }, [columns])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!formula.trim() || loading) return

    setLoading(true)
    setError('')
    setSuccess(null)
    setPendingDateCol(null)

    try {
      const result = await addCustomColumn(reportType, reportId, formula.trim(), sessionId, fileName)
      setSuccess(result)
      setFormula('')
      if (onColumnAdded) onColumnAdded(result)
      setTimeout(() => setSuccess(null), 5000)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const applySuggestion = (sug) => {
    setFormula(`${sug.name} = ${sug.formula}`)
    setError('')
    setSuccess(null)
    setPendingDateCol(null)
  }

  const insertColumn = (colName) => {
    const ref = colName.includes(' ') ? colName : colName
    setFormula((prev) => prev ? `${prev} ${ref}` : ref)
  }

  // Smart date column click — builds date_diff() with two clicks
  const handleDateClick = (colName) => {
    setError('')
    if (!pendingDateCol) {
      // First date click — remember it and show hint
      setPendingDateCol(colName)
      setFormula((prev) => {
        // If formula already has "= " prefix, append date_diff start
        if (prev && prev.includes('=')) {
          return `${prev.split('=')[0].trim()} = date_diff(${colName}, `
        }
        return `Duration = date_diff(${colName}, `
      })
    } else {
      // Second date click — complete the date_diff()
      const first = pendingDateCol
      setPendingDateCol(null)
      setFormula((prev) => {
        // Check if there's already a partial date_diff
        const match = prev.match(/^(.+?)\s*=\s*date_diff\((.+?),\s*$/)
        if (match) {
          return `${match[1]} = date_diff(${match[2]}, ${colName})`
        }
        // Fallback: build fresh
        const name = prev.split('=')[0].trim() || 'Duration'
        return `${name} = date_diff(${first}, ${colName})`
      })
    }
  }

  if (!isOpen) {
    return (
      <button style={styles.toggleBtn} onClick={() => setIsOpen(true)}>
        <FiCode size={13} />
        <span>Custom Column</span>
        <FiPlus size={12} />
      </button>
    )
  }

  const dateCols = columns.datetime || []
  const numCols = columns.numeric || []
  const catCols = columns.categorical || []

  return (
    <div style={styles.panel}>
      <div style={styles.panelHeader}>
        <div style={styles.panelTitle}>
          <FiCode size={14} color="#f59e0b" />
          <span>Custom Column Builder</span>
        </div>
        <button style={styles.closeBtn} onClick={() => setIsOpen(false)}>
          <FiX size={14} />
        </button>
      </div>

      <form onSubmit={handleSubmit} style={styles.form}>
        <div style={styles.inputRow}>
          <input
            type="text"
            value={formula}
            onChange={(e) => { setFormula(e.target.value); setError(''); setPendingDateCol(null) }}
            placeholder={dynamicPlaceholder}
            disabled={loading}
            style={styles.input}
          />
          <button
            type="submit"
            disabled={loading || !formula.trim()}
            style={{ ...styles.submitBtn, opacity: loading || !formula.trim() ? 0.4 : 1 }}
          >
            {loading ? '...' : <FiPlus size={14} />}
          </button>
        </div>
        {hintExamples.length > 0 ? (
          <div style={styles.hint}>
            {hintExamples.map((h, i) => (
              <span key={i}>
                {i > 0 && <> &nbsp;|&nbsp; </>}
                {h.label}: <code style={styles.code}>{h.example}</code>
              </span>
            ))}
          </div>
        ) : (
          <div style={styles.hint}>
            Format: <code style={styles.code}>new_name = expression</code>
          </div>
        )}
      </form>

      {/* Pending date hint */}
      {pendingDateCol && (
        <div style={styles.dateHint}>
          <FiCalendar size={11} />
          <span>Selected <strong>{pendingDateCol}</strong> — now click a second date column to complete</span>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={styles.errorBox}>
          <FiAlertCircle size={12} />
          <span>{error}</span>
        </div>
      )}

      {/* Success */}
      {success && (
        <div style={styles.successBox}>
          <FiCheck size={12} />
          <span>
            Created <strong>{success.column_name}</strong> ({success.total_rows} values)
            — Sample: [{success.sample_values.slice(0, 3).join(', ')}...]
          </span>
        </div>
      )}

      {/* Suggestions — dynamic from backend */}
      {suggestions.length > 0 && (
        <div style={styles.suggestSection}>
          <div style={styles.suggestLabel}>Suggested formulas</div>
          <div style={styles.suggestGrid}>
            {suggestions.map((sug, i) => (
              <button
                key={i}
                style={{
                  ...styles.suggestChip,
                  ...(sug.formula.includes('date_diff') ? styles.suggestDateChip : {}),
                }}
                onClick={() => applySuggestion(sug)}
                title={`${sug.name} = ${sug.formula}`}
              >
                {sug.formula.includes('date_diff') && (
                  <FiCalendar size={10} style={{ flexShrink: 0, marginTop: 1 }} />
                )}
                <div>
                  <span style={styles.suggestName}>{sug.name}</span>
                  <span style={styles.suggestDesc}>{sug.description}</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Column reference — always visible, dates first */}
      <div style={styles.colSection}>
        <button style={styles.colToggle} onClick={() => setShowColumns(!showColumns)}>
          {showColumns ? <FiChevronUp size={11} /> : <FiChevronDown size={11} />}
          <span>Available columns ({dateCols.length + numCols.length + catCols.length})</span>
        </button>
        {showColumns && (
          <div style={styles.colGrid}>
            {dateCols.length > 0 && (
              <div>
                <div style={styles.colGroupLabel}>
                  <span style={styles.dateTag}>DATE</span> Click two dates to build date_diff()
                </div>
                {dateCols.map((c) => (
                  <button
                    key={c}
                    style={{
                      ...styles.colChip, ...styles.dateChip,
                      ...(pendingDateCol === c ? styles.dateChipActive : {}),
                    }}
                    onClick={() => handleDateClick(c)}
                  >
                    <FiCalendar size={9} style={{ marginRight: 3, verticalAlign: 'middle' }} />
                    {c}
                  </button>
                ))}
              </div>
            )}
            {numCols.length > 0 && (
              <div>
                <div style={styles.colGroupLabel}>Numeric</div>
                {numCols.map((c) => (
                  <button key={c} style={styles.colChip} onClick={() => insertColumn(c)}>
                    {c}
                  </button>
                ))}
              </div>
            )}
            {catCols.length > 0 && (
              <div>
                <div style={styles.colGroupLabel}>Categorical</div>
                {catCols.slice(0, 10).map((c) => (
                  <button key={c} style={styles.colChip} onClick={() => insertColumn(c)}>
                    {c}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

const styles = {
  toggleBtn: {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '7px 14px', borderRadius: 8,
    background: 'var(--bg-card)', border: '1px solid var(--border)',
    color: 'var(--accent-light)', fontSize: 12, fontWeight: 600,
    cursor: 'pointer', transition: 'all 0.15s',
  },
  panel: {
    background: 'var(--bg-card)', borderRadius: 12,
    border: '1px solid var(--border)', padding: 16,
    marginBottom: 16, boxShadow: 'var(--shadow-sm)',
  },
  panelHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 12,
  },
  panelTitle: {
    display: 'flex', alignItems: 'center', gap: 8,
    fontSize: 13, fontWeight: 700, color: 'var(--text-primary)',
  },
  closeBtn: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    width: 28, height: 28, borderRadius: 7,
    background: 'var(--bg-primary)', border: '1px solid var(--border)',
    color: 'var(--text-muted)', cursor: 'pointer',
  },
  form: { marginBottom: 10 },
  inputRow: { display: 'flex', gap: 8 },
  input: {
    flex: 1, padding: '9px 14px', borderRadius: 8,
    border: '1px solid var(--border)', background: 'var(--bg-primary)',
    color: 'var(--text-primary)', fontSize: 13, fontFamily: "'Fira Code', monospace",
    outline: 'none',
  },
  submitBtn: {
    width: 38, height: 38, borderRadius: 8,
    background: 'linear-gradient(135deg, #f59e0b, #fbbf24)', color: '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    border: 'none', cursor: 'pointer', flexShrink: 0,
  },
  hint: {
    fontSize: 10, color: 'var(--text-muted)', marginTop: 6, paddingLeft: 2, lineHeight: 1.8,
  },
  code: {
    background: 'rgba(245,158,11,0.08)', padding: '1px 5px', borderRadius: 4,
    fontFamily: "'Fira Code', monospace", fontSize: 10, color: '#92400e',
  },
  dateHint: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 12px', borderRadius: 8,
    background: 'rgba(99, 102, 241, 0.06)', border: '1px solid rgba(99, 102, 241, 0.15)',
    color: '#4f46e5', fontSize: 11, marginBottom: 10,
  },
  errorBox: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 12px', borderRadius: 8,
    background: 'rgba(239, 68, 68, 0.08)', border: '1px solid rgba(239, 68, 68, 0.2)',
    color: '#dc2626', fontSize: 11, marginBottom: 10,
  },
  successBox: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 12px', borderRadius: 8,
    background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.2)',
    color: '#059669', fontSize: 11, marginBottom: 10,
  },
  suggestSection: { marginBottom: 10 },
  suggestLabel: {
    fontSize: 10, fontWeight: 600, color: 'var(--text-muted)',
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6,
  },
  suggestGrid: { display: 'flex', flexWrap: 'wrap', gap: 6 },
  suggestChip: {
    display: 'flex', alignItems: 'flex-start', gap: 5,
    padding: '7px 11px', borderRadius: 8,
    background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)',
    color: '#92400e', fontSize: 11, cursor: 'pointer', textAlign: 'left',
    transition: 'all 0.15s', maxWidth: '100%',
  },
  suggestDateChip: {
    background: 'rgba(99, 102, 241, 0.06)', border: '1px solid rgba(99, 102, 241, 0.18)',
    color: '#4f46e5',
  },
  suggestName: { display: 'block', fontWeight: 600, fontSize: 11 },
  suggestDesc: { display: 'block', fontSize: 9, color: 'var(--text-muted)', marginTop: 1 },
  colSection: { borderTop: '1px solid var(--border)', paddingTop: 8 },
  colToggle: {
    display: 'flex', alignItems: 'center', gap: 5,
    background: 'none', border: 'none',
    color: 'var(--text-muted)', fontSize: 10, fontWeight: 600,
    cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.04em',
  },
  colGrid: {
    display: 'flex', flexDirection: 'column', gap: 8,
    marginTop: 8, maxHeight: 200, overflowY: 'auto',
  },
  colGroupLabel: {
    fontSize: 9, fontWeight: 700, color: 'var(--text-muted)',
    textTransform: 'uppercase', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4,
  },
  colChip: {
    display: 'inline-flex', alignItems: 'center',
    padding: '4px 9px', borderRadius: 5, margin: '0 4px 4px 0',
    background: 'var(--bg-primary)', border: '1px solid var(--border)',
    color: 'var(--text-secondary)', fontSize: 10, fontFamily: "'Fira Code', monospace",
    cursor: 'pointer', transition: 'all 0.12s',
  },
  dateChip: {
    background: 'rgba(99, 102, 241, 0.06)', border: '1px solid rgba(99, 102, 241, 0.2)',
    color: '#4f46e5',
  },
  dateChipActive: {
    background: 'rgba(99, 102, 241, 0.18)', border: '1px solid rgba(99, 102, 241, 0.5)',
    fontWeight: 700, boxShadow: '0 0 0 2px rgba(99, 102, 241, 0.2)',
  },
  dateTag: {
    display: 'inline-block',
    padding: '1px 4px', borderRadius: 3, fontSize: 8, fontWeight: 700,
    background: 'rgba(99, 102, 241, 0.12)', color: '#4f46e5',
    marginRight: 2,
  },
}
