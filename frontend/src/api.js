const API_BASE = 'http://localhost:8001'

export async function fetchReportList(reportType) {
  const res = await fetch(`${API_BASE}/reports/design/${reportType}-list`)
  if (!res.ok) throw new Error('Failed to fetch report list')
  return res.json()
}

export async function fetchReportData(reportType, reportId, fileName = null) {
  const url = fileName
    ? `${API_BASE}/reports/design/${reportType}/detail/${reportId}/data?file_name=${encodeURIComponent(fileName)}`
    : `${API_BASE}/reports/design/${reportType}/detail/${reportId}/data`
  const res = await fetch(url)
  if (!res.ok) throw new Error('Failed to fetch report data')
  return res.json()
}

export async function fetchReportFiles(reportType, reportId) {
  const res = await fetch(`${API_BASE}/reports/design/${reportType}/detail/${reportId}/files`)
  if (!res.ok) throw new Error('Failed to fetch report files')
  return res.json()
}

export async function fetchAllExcelFiles(reportType) {
  const res = await fetch(`${API_BASE}/reports/design/${reportType}/all-files`)
  if (!res.ok) throw new Error('Failed to fetch all Excel files')
  return res.json()
}

export async function chatWithDashboard(reportType, reportId, prompt, sessionId = null, fileName = null) {
  const res = await fetch(`${API_BASE}/reports/design/${reportType}/detail/${reportId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      session_id: sessionId,
      file_name: fileName,
    }),
  })
  if (!res.ok) throw new Error('Chat API failed')
  return res.json()
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error('Backend health check failed')
  return res.json()
}
