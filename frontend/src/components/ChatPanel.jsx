import React, { useState, useRef, useEffect } from 'react'
import { FiSend, FiCpu, FiUser, FiMessageCircle, FiZap } from 'react-icons/fi'

export default function ChatPanel({ messages, onSend, loading, summary, suggestions = [] }) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, suggestions])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    onSend(input.trim())
    setInput('')
  }

  const handleSuggestionClick = (text) => {
    if (loading) return
    onSend(text)
  }

  return (
    <aside style={styles.panel}>
      <div style={styles.header}>
        <FiMessageCircle size={16} color="#f59e0b" />
        <span style={styles.headerTitle}>AI Analyst</span>
        {loading && <span className="loading-pulse" style={styles.typing}>thinking...</span>}
      </div>

      <div style={styles.messages}>
        {messages.length === 0 && (
          <div style={styles.welcome}>
            <FiCpu size={28} color="var(--text-muted)" />
            <p style={styles.welcomeText}>
              Ask me anything about your data. I'll generate a complete dashboard
              with charts, KPIs, and insights.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} style={styles.msgRow}>
            <div style={{
              ...styles.avatar,
              background: msg.role === 'user' ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.15)',
            }}>
              {msg.role === 'user'
                ? <FiUser size={13} color="#d97706" />
                : <FiCpu size={13} color="#10b981" />}
            </div>
            <div style={{
              ...styles.bubble,
              ...(msg.role === 'user' ? styles.userBubble : styles.aiBubble),
            }}>
              <div style={styles.msgContent}>
                {msg.content.split('\n').map((line, j) => (
                  <p key={j} style={{ margin: '2px 0' }}>{line}</p>
                ))}
              </div>
            </div>
          </div>
        ))}

        {/* ── Suggested follow-up prompts ── */}
        {!loading && suggestions.length > 0 && messages.length > 0 && (
          <div style={styles.suggestionsWrap}>
            <div style={styles.suggestionsLabel}>
              <FiZap size={11} color="#f59e0b" />
              <span>Try asking</span>
            </div>
            <div style={styles.suggestionsRow}>
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  style={styles.suggestionChip}
                  onClick={() => handleSuggestionClick(s)}
                  title={s}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div style={styles.msgRow}>
            <div style={{ ...styles.avatar, background: 'rgba(16,185,129,0.15)' }}>
              <FiCpu size={13} color="#10b981" />
            </div>
            <div style={{ ...styles.bubble, ...styles.aiBubble }}>
              <div className="loading-pulse" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Analyzing data and generating dashboard...
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} style={styles.inputArea}>
        <div style={styles.inputWrap}>
          <input
            type="text"
            placeholder="Ask about the data..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            style={styles.input}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            style={{ ...styles.sendBtn, opacity: loading || !input.trim() ? 0.4 : 1 }}
          >
            <FiSend size={16} />
          </button>
        </div>
      </form>
    </aside>
  )
}

const styles = {
  panel: {
    width: 380, flexShrink: 0, display: 'flex', flexDirection: 'column',
    background: 'var(--bg-secondary)', borderLeft: '1px solid var(--border)', height: '100%',
  },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '14px 18px',
    borderBottom: '1px solid var(--border)', background: 'linear-gradient(90deg, #fef3c7, #fff)',
    flexShrink: 0,
  },
  headerTitle: { fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' },
  typing: { marginLeft: 'auto', fontSize: 11, color: '#d97706', fontWeight: 500 },
  messages: {
    flex: 1, overflowY: 'auto', padding: '16px 14px',
    display: 'flex', flexDirection: 'column', gap: 14,
  },
  welcome: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100%', gap: 12, padding: 20, textAlign: 'center',
  },
  welcomeText: { fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, maxWidth: 280 },
  msgRow: { display: 'flex', gap: 8, alignItems: 'flex-start' },
  avatar: {
    width: 28, height: 28, borderRadius: 8,
    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2,
  },
  bubble: {
    maxWidth: '85%', padding: '10px 14px', borderRadius: 12, fontSize: 13, lineHeight: 1.6,
  },
  userBubble: {
    background: 'rgba(245,158,11,0.10)', border: '1px solid rgba(245,158,11,0.2)',
    color: 'var(--text-primary)', borderTopLeftRadius: 4,
  },
  aiBubble: {
    background: 'var(--bg-primary)', border: '1px solid var(--border)',
    color: 'var(--text-primary)', borderTopLeftRadius: 4,
  },
  msgContent: { wordBreak: 'break-word' },

  // ── Suggestion chips ──
  suggestionsWrap: {
    padding: '6px 0 2px', marginLeft: 36,
  },
  suggestionsLabel: {
    display: 'flex', alignItems: 'center', gap: 5,
    fontSize: 10, fontWeight: 600, color: 'var(--text-muted)',
    textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8,
  },
  suggestionsRow: {
    display: 'flex', flexDirection: 'column', gap: 6,
  },
  suggestionChip: {
    display: 'flex', alignItems: 'center', gap: 6,
    padding: '8px 14px', borderRadius: 10,
    background: 'linear-gradient(135deg, rgba(245,158,11,0.06), rgba(251,191,36,0.10))',
    border: '1px solid rgba(245,158,11,0.18)',
    color: '#92400e', fontSize: 12, fontWeight: 500,
    cursor: 'pointer', transition: 'all 0.18s ease',
    textAlign: 'left', lineHeight: 1.4,
    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
    maxWidth: '100%',
  },

  inputArea: { padding: '12px 14px', borderTop: '1px solid var(--border)', flexShrink: 0 },
  inputWrap: {
    display: 'flex', gap: 8, alignItems: 'center',
    background: 'var(--bg-input)', borderRadius: 10,
    border: '1px solid var(--border)', padding: '4px 6px 4px 14px',
  },
  input: {
    flex: 1, border: 'none', background: 'transparent',
    color: 'var(--text-primary)', fontSize: 14, outline: 'none',
    padding: '8px 0', fontFamily: 'Inter, sans-serif',
  },
  sendBtn: {
    width: 36, height: 36, borderRadius: 8,
    background: 'linear-gradient(135deg, #f59e0b, #fbbf24)', color: '#fff',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    border: 'none', cursor: 'pointer', transition: 'all 0.2s', flexShrink: 0,
  },
}
