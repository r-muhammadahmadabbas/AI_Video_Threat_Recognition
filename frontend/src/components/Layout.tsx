import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { LogOut, LayoutDashboard, AlertTriangle, Video, MapPin, Shield, Users, FileText } from 'lucide-react'

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navItems = [
    { path: '/', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/incidents', label: 'Incidents', icon: AlertTriangle },
    { path: '/cameras', label: 'Cameras', icon: Video },
    { path: '/zones', label: 'Zones', icon: MapPin },
    { path: '/rules', label: 'Rules', icon: Shield },
    { path: '/users', label: 'Users', icon: Users },
    { path: '/audit', label: 'Audit', icon: FileText },
  ]

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside style={{
        width: 260,
        background: 'var(--color-surface)',
        borderRight: '1px solid var(--color-border)',
        display: 'flex',
        flexDirection: 'column',
        padding: '20px 16px',
        gap: 8,
      }}>
        <div style={{ padding: '0 12px 20px', borderBottom: '1px solid var(--color-border)', marginBottom: 8 }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Video style={{ width: 24, height: 24, color: 'var(--color-primary)' }} />
            Threat Recognition
          </h1>
        </div>
        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '10px 12px',
                borderRadius: 'var(--radius-md)',
                color: isActive ? 'var(--color-primary)' : 'var(--color-text-muted)',
                background: isActive ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                fontWeight: isActive ? 600 : 500,
                textDecoration: 'none',
                transition: 'all var(--transition)',
              })}
            >
              <item.icon style={{ width: 20, height: 20 }} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ paddingTop: 16, borderTop: '1px solid var(--color-border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', marginBottom: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--color-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 600, fontSize: 14 }}>
              {user?.email?.[0].toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 500, fontSize: 14, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {user?.full_name || user?.email}
              </div>
              <div style={{ fontSize: 12, color: 'var(--color-text-muted)', textTransform: 'capitalize' }}>
                {user?.role}
              </div>
            </div>
          </div>
          <button onClick={handleLogout} style={{
            display: 'flex', alignItems: 'center', gap: 10, width: '100%',
            padding: '10px 12px', borderRadius: 'var(--radius-md)',
            background: 'transparent', border: '1px solid var(--color-border)',
            color: 'var(--color-text-muted)', fontSize: 14, cursor: 'pointer',
          }}>
            <LogOut style={{ width: 18, height: 18 }} />
            Logout
          </button>
        </div>
      </aside>
      <main style={{ flex: 1, padding: '24px 32px', overflow: 'auto' }}>
        <Outlet />
      </main>
    </div>
  )
}