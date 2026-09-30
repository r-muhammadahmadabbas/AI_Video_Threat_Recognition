import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { Search, Filter, ChevronLeft, ChevronRight, Loader2, FileText } from 'lucide-react'

const ACTIONS = ['login', 'logout', 'incident_view', 'incident_verify', 'incident_dismiss', 'camera_create', 'camera_update', 'camera_delete', 'zone_create', 'zone_update', 'zone_delete', 'rule_create', 'rule_update', 'rule_delete', 'user_create', 'user_update', 'user_delete', 'settings_change', 'export_data'] as const

export function AuditPage() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [action, setAction] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['audit', page, pageSize, action, dateFrom, dateTo],
    queryFn: () => api.getAuditLogs({ page, page_size: pageSize, action: action || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }),
  })

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit Logs</h1>
          <p className="page-subtitle">System activity and compliance trail</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 24, padding: 20 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center' }}>
          <select className="input" value={action} onChange={(e) => setAction(e.target.value)} style={{ width: 'auto', minWidth: 200, paddingRight: 36 }}>
            <option value="">All Actions</option>
            {ACTIONS.map((a) => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
          </select>
          <input type="date" className="input" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} style={{ width: 'auto' }} />
          <span style={{ color: 'var(--color-text-muted)' }}>to</span>
          <input type="date" className="input" value={dateTo} onChange={(e) => setDateTo(e.target.value)} style={{ width: 'auto' }} />
        </div>
      </div>

      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>User</th>
                <th>Action</th>
                <th>Resource</th>
                <th>IP Address</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 48 }}><Loader2 style={{ width: 24, height: 24, margin: '0 auto', animation: 'spin 1s linear infinite' }} /></td></tr>
              ) : data?.items?.length === 0 ? (
                <tr><td colSpan={5} style={{ textAlign: 'center', padding: 48 }}><div className="empty-state" style={{ padding: 0 }}><FileText className="empty-state-icon" /><p>No audit logs found</p></div></td></tr>
              ) : (
                data?.items?.map((log: any) => (
                  <tr key={log.id}>
                    <td style={{ whiteSpace: 'nowrap' }}>{new Date(log.created_at).toLocaleString()}</td>
                    <td>{log.user_id ? `User #${log.user_id}` : 'System'}</td>
                    <td><span className="badge badge-gray">{log.action.replace(/_/g, ' ')}</span></td>
                    <td>{log.resource_type ? `${log.resource_type} #${log.resource_id}` : '—'}</td>
                    <td style={{ color: 'var(--color-text-muted)', fontSize: 13, fontFamily: 'monospace' }}>{log.ip_address || '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {data && data.total > pageSize && (
          <div className="pagination">
            <button className="pagination-btn" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}><ChevronLeft style={{ width: 16, height: 16 }} /></button>
            <span className="pagination-info">Page {page} of {Math.ceil(data.total / pageSize)}</span>
            <button className="pagination-btn" onClick={() => setPage(p => Math.min(Math.ceil(data.total / pageSize), p + 1))} disabled={page >= Math.ceil(data.total / pageSize)}><ChevronRight style={{ width: 16, height: 16 }} /></button>
          </div>
        )}
      </div>
    </div>
  )
}