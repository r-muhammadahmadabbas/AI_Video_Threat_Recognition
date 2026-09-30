import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { AlertTriangle, CheckCircle, XCircle, Clock, Video, MapPin, Shield, Download, Eye } from 'lucide-react'

export function IncidentDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: incident, isLoading } = useQuery({
    queryKey: ['incident', id],
    queryFn: () => api.getIncident(Number(id)),
    enabled: !!id,
  })

  const { data: evidence } = useQuery({
    queryKey: ['evidence', id],
    queryFn: () => api.getEvidence(Number(id)),
    enabled: !!id,
  })

  const getSeverityBadge = (s: string) => {
    const colors: Record<string, string> = {
      low: 'badge-info', medium: 'badge-warning', high: 'badge-danger', critical: 'badge-danger',
    }
    return <span className={`badge ${colors[s] || 'badge-gray'}`}>{s}</span>
  }

  const getStatusBadge = (s: string) => {
    const colors: Record<string, string> = {
      detected: 'badge-info', pending_review: 'badge-warning', verified: 'badge-success', dismissed: 'badge-gray', merged: 'badge-gray',
    }
    const icons: Record<string, any> = { detected: AlertTriangle, pending_review: Clock, verified: CheckCircle, dismissed: XCircle }
    const Icon = icons[s]
    return <span className={`badge ${colors[s] || 'badge-gray'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>{Icon && <Icon style={{ width: 12, height: 12 }} />}{s.replace('_', ' ')}</span>
  }

  if (isLoading) {
    return <div className="empty-state" style={{ flex: 1 }}><svg className="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></svg><p>Loading...</p></div>
  }

  if (!incident) {
    return <div className="empty-state" style={{ flex: 1 }}><AlertTriangle className="empty-state-icon" /><p>Incident not found</p></div>
  }

  return (
    <div>
      <div className="page-header" style={{ flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 className="page-title">Incident #{incident.id}</h1>
          <p className="page-subtitle">{incident.event_type} • {new Date(incident.first_seen_at).toLocaleString()}</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          {getStatusBadge(incident.status)}
          {getSeverityBadge(incident.severity)}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 24 }}>
        <div className="card">
          <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--color-border)' }}>
            <h2 style={{ fontSize: 16, fontWeight: 600 }}>Evidence</h2>
          </div>
          <div style={{ padding: 24 }}>
            {evidence?.items?.length ? (
              evidence.items.map((e: any) => (
                <div key={e.id} style={{ marginBottom: 16, padding: 16, border: '1px solid var(--color-border)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                    <span className="badge badge-gray">{e.evidence_type}</span>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <a href={api.getEvidenceFile(e.id)} target="_blank" rel="noopener noreferrer" className="btn btn-ghost" style={{ padding: '6px 10px' }}>
                        <Eye style={{ width: 16, height: 16 }} />
                        View
                      </a>
                      <a href={api.getEvidenceFile(e.id)} download className="btn btn-ghost" style={{ padding: '6px 10px' }}>
                        <Download style={{ width: 16, height: 16 }} />
                        Download
                      </a>
                    </div>
                  </div>
                  {e.thumbnail_uri && (
                    <img src={api.getEvidenceThumbnail(e.id)} alt="Evidence thumbnail" style={{ maxWidth: '100%', borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }} />
                  )}
                  <div style={{ marginTop: 8, fontSize: 12, color: 'var(--color-text-muted)', display: 'flex', gap: 16 }}>
                    <span>Duration: {e.duration_seconds?.toFixed(1)}s</span>
                    <span>Size: {(e.size_bytes! / 1024 / 1024).toFixed(1)} MB</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-state" style={{ padding: 32 }}>
                <Video className="empty-state-icon" />
                <p>No evidence available</p>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--color-border)' }}>
            <h2 style={{ fontSize: 16, fontWeight: 600 }}>Details</h2>
          </div>
          <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
              <div><p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Event Type</p><p style={{ fontWeight: 500 }}>{incident.event_type}</p></div>
              <div><p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Severity</p><p>{getSeverityBadge(incident.severity)}</p></div>
              <div><p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Status</p><p>{getStatusBadge(incident.status)}</p></div>
              <div><p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Confidence</p><p style={{ fontFamily: 'monospace' }}>{(incident.confidence * 100).toFixed(1)}%</p></div>
              <div><p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Camera</p><p>Camera #{incident.camera_id}</p></div>
              <div><p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Zone</p><p>{incident.zone_id ? `Zone #${incident.zone_id}` : 'N/A'}</p></div>
              <div><p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Rule</p><p>{incident.rule_id ? `Rule #${incident.rule_id}` : 'N/A'}</p></div>
              <div><p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Model Version</p><p style={{ fontFamily: 'monospace', fontSize: 13 }}>{incident.model_version}</p></div>
            </div>

            <div style={{ paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Track IDs</p>
              <p style={{ fontFamily: 'monospace', fontSize: 13 }}>{incident.track_ids.join(', ')}</p>
            </div>

            <div style={{ paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>First Seen</p>
              <p>{new Date(incident.first_seen_at).toLocaleString()}</p>
            </div>

            <div style={{ paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
              <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Last Seen</p>
              <p>{new Date(incident.last_seen_at).toLocaleString()}</p>
            </div>

            {incident.verified_at && (
              <div style={{ paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>{incident.status === 'verified' ? 'Verified' : 'Dismissed'} By</p>
                <p>User #{incident.verified_by_id} at {new Date(incident.verified_at).toLocaleString()}</p>
              </div>
            )}

            {incident.metadata_json && Object.keys(incident.metadata_json).length > 0 && (
              <div style={{ paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 4 }}>Metadata</p>
                <pre style={{ fontSize: 12, background: 'var(--color-bg)', padding: 12, borderRadius: 'var(--radius-md)', overflow: 'auto', maxHeight: 200 }}>
                  {JSON.stringify(incident.metadata_json, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}