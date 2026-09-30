import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Search, Filter, ChevronLeft, ChevronRight, AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react'

const SEVERITY_OPTIONS = ['low', 'medium', 'high', 'critical'] as const
const STATUS_OPTIONS = ['detected', 'pending_review', 'verified', 'dismissed', 'merged'] as const

export function IncidentsPage() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [search, setSearch] = useState('')
  const [severity, setSeverity] = useState<string>('')
  const [status, setStatus] = useState<string>('')

  const { data, isLoading } = useQuery({
    queryKey: ['incidents', page, pageSize, search, severity, status],
    queryFn: () => api.getIncidents({
      page,
      page_size: pageSize,
      event_type: search || undefined,
      severity: severity || undefined,
      status: status || undefined,
    }),
  })

  const getSeverityBadge = (s: string) => {
    const colors: Record<string, string> = {
      low: 'badge-info',
      medium: 'badge-warning',
      high: 'badge-danger',
      critical: 'badge-danger',
    }
    return <span className={`badge ${colors[s] || 'badge-gray'}`}>{s}</span>
  }

  const getStatusBadge = (s: string) => {
    const colors: Record<string, string> = {
      detected: 'badge-info',
      pending_review: 'badge-warning',
      verified: 'badge-success',
      dismissed: 'badge-gray',
      merged: 'badge-gray',
    }
    const icons: Record<string, any> = {
      detected: AlertTriangle,
      pending_review: Clock,
      verified: CheckCircle,
      dismissed: XCircle,
    }
    const Icon = icons[s]
    return (
      <span className={`badge ${colors[s] || 'badge-gray'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        {Icon && <Icon style={{ width: 12, height: 12 }} />}
        {s.replace('_', ' ')}
      </span>
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Incidents</h1>
          <p className="page-subtitle">Review and manage security incidents</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 24, padding: 20 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <input
              type="text"
              className="input"
              placeholder="Search event type..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px center', paddingRight: 40 }}
            />
          </div>
          <select className="input" value={severity} onChange={(e) => setSeverity(e.target.value)} style={{ width: 'auto', minWidth: 160, paddingRight: 36 }}>
            <option value="">All Severities</option>
            {SEVERITY_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 'auto', minWidth: 180, paddingRight: 36 }}>
            <option value="">All Statuses</option>
            {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
          </select>
        </div>
      </div>

      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Event Type</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Confidence</th>
                <th>Camera</th>
                <th style={{ width: 100 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: 48 }}>
                    <div className="empty-state" style={{ padding: 0 }}>
                      <svg className="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M12 6v6l4 2" />
                      </svg>
                      <p>Loading...</p>
                    </div>
                  </td>
                </tr>
              ) : data?.items?.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: 'center', padding: 48 }}>
                    <div className="empty-state" style={{ padding: 0 }}>
                      <AlertTriangle className="empty-state-icon" />
                      <p>No incidents found</p>
                    </div>
                  </td>
                </tr>
              ) : (
                data?.items?.map((incident: any) => (
                  <tr key={incident.id}>
                    <td style={{ whiteSpace: 'nowrap' }}>{new Date(incident.first_seen_at).toLocaleString()}</td>
                    <td style={{ fontWeight: 500 }}>{incident.event_type}</td>
                    <td>{getSeverityBadge(incident.severity)}</td>
                    <td>{getStatusBadge(incident.status)}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{(incident.confidence * 100).toFixed(1)}%</td>
                    <td style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>{incident.camera_id}</td>
                    <td>
                      <a href={`/incidents/${incident.id}`} className="btn btn-ghost" style={{ padding: '6px 10px', fontSize: 12 }}>View</a>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {data && data.total > pageSize && (
          <div className="pagination">
            <button className="pagination-btn" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
              <ChevronLeft style={{ width: 16, height: 16 }} />
            </button>
            <span className="pagination-info">
              Page {page} of {Math.ceil(data.total / pageSize)}
            </span>
            <button className="pagination-btn" onClick={() => setPage(p => Math.min(Math.ceil(data.total / pageSize), p + 1))} disabled={page >= Math.ceil(data.total / pageSize)}>
              <ChevronRight style={{ width: 16, height: 16 }} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}