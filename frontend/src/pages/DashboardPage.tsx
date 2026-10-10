import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { AlertTriangle, CheckCircle, Clock, Video, ShieldAlert } from 'lucide-react'

interface DashboardStats {
  total_cameras: number
  online_cameras: number
  total_incidents: number
  pending_incidents: number
  verified_incidents: number
  dismissed_incidents: number
  very_high_risk_incidents: number
  incidents_last_24h: number
}

function StatCard({ title, value, icon: Icon, color, trend }: { title: string; value: number; icon: any; color: string; trend?: string }) {
  return (
    <div className="card" style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 4 }}>{title}</p>
          <p style={{ fontSize: 28, fontWeight: 700 }}>{value}</p>
          {trend && <p style={{ fontSize: 12, color: 'var(--color-success)', marginTop: 4 }}>{trend}</p>}
        </div>
        <div style={{ width: 48, height: 48, borderRadius: 'var(--radius-md)', background: `${color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon style={{ width: 24, height: 24, color }} />
        </div>
      </div>
    </div>
  )
}

function CameraStatusCard({ camera }: { camera: any }) {
  const isOnline = camera.status === 'online'
  return (
    <div className="card" style={{ padding: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ width: 10, height: 10, borderRadius: '50%', background: isOnline ? 'var(--color-success)' : 'var(--color-danger)' }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{camera.name}</p>
        <p style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{camera.source_type?.toUpperCase()} • {isOnline ? 'Online' : 'Offline'}</p>
      </div>
      <span className={`badge ${isOnline ? 'badge-success' : 'badge-danger'}`}>{isOnline ? 'Live' : 'Down'}</span>
    </div>
  )
}

export function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard-stats'],
    queryFn: () => api.getDashboardStats(),
    refetchInterval: 30000,
  })

  const { data: camerasData } = useQuery({
    queryKey: ['cameras-recent'],
    queryFn: () => api.getCameras({ page_size: 5, is_active: true }),
  })

  const { data: incidentsData } = useQuery({
    queryKey: ['incidents-recent'],
    queryFn: () => api.getIncidents({ page_size: 5 }),
  })

  if (statsLoading) {
    return (
      <div className="empty-state" style={{ flex: 1 }}>
        <svg className="empty-state-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" />
        </svg>
        <p>Loading dashboard...</p>
      </div>
    )
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">System overview and key metrics</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16, marginBottom: 24 }}>
        <StatCard title="Total Cameras" value={stats?.total_cameras || 0} icon={Video} color="var(--color-primary)" />
        <StatCard title="Online Cameras" value={stats?.online_cameras || 0} icon={CheckCircle} color="var(--color-success)" />
        <StatCard title="Total Incidents" value={stats?.total_incidents || 0} icon={AlertTriangle} color="var(--color-warning)" />
        <StatCard title="Pending Review" value={stats?.pending_incidents || 0} icon={Clock} color="var(--color-info)" />
        <StatCard title="Very High Risk" value={stats?.very_high_risk_incidents || 0} icon={ShieldAlert} color="var(--color-danger)" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: 24 }}>
        <div className="card">
          <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: 16, fontWeight: 600 }}>Recent Cameras</h2>
            <a href="/cameras" className="btn btn-ghost" style={{ fontSize: 12 }}>View All</a>
          </div>
          <div style={{ padding: 8 }}>
            {camerasData?.items?.length ? (
              camerasData.items.map((camera: any) => <CameraStatusCard key={camera.id} camera={camera} />)
            ) : (
              <div className="empty-state" style={{ padding: 32 }}>
                <Video className="empty-state-icon" />
                <p>No cameras configured</p>
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: 16, fontWeight: 600 }}>Recent Incidents</h2>
            <a href="/incidents" className="btn btn-ghost" style={{ fontSize: 12 }}>View All</a>
          </div>
          <div style={{ padding: 8 }}>
            {incidentsData?.items?.length ? (
              incidentsData.items.map((incident: any) => (
                <div key={incident.id} className="card" style={{ margin: 8, padding: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
                    <span className={`badge ${incident.severity === 'critical' || incident.severity === 'high' ? 'badge-danger' : incident.severity === 'medium' ? 'badge-warning' : 'badge-info'}`}>
                      {incident.severity}
                    </span>
                    <div>
                      <p style={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{incident.event_type}</p>
                      <p style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>{new Date(incident.first_seen_at).toLocaleString()}</p>
                    </div>
                  </div>
                  <span className={`badge ${incident.status === 'verified' ? 'badge-success' : incident.status === 'dismissed' ? 'badge-gray' : 'badge-warning'}`}>
                    {incident.status}
                  </span>
                </div>
              ))
            ) : (
              <div className="empty-state" style={{ padding: 32 }}>
                <AlertTriangle className="empty-state-icon" />
                <p>No incidents yet</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}