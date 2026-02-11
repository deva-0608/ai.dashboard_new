import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Home from './pages/Home'
import ReportList from './pages/ReportList'
import ReportDetail from './pages/ReportDetail'
import AIDashboard from './pages/AIDashboard'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/reports/:reportType" element={<ReportList />} />
      <Route path="/reports/:reportType/:reportId" element={<ReportDetail />} />
      <Route path="/dashboard/:reportType/:reportId" element={<AIDashboard />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
