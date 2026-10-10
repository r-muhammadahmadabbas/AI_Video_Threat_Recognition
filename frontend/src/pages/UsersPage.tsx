import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { Plus, Edit, Trash2, Users, Loader2, Shield, User, Eye } from 'lucide-react'

const ROLES = ['admin', 'operator', 'viewer'] as const

export function UsersPage() {
  const queryClient = useQueryClient()
  const [page] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [formData, setFormData] = useState({ email: '', password: '', full_name: '', role: 'viewer', is_active: true })

  const { data } = useQuery({ queryKey: ['users', page], queryFn: () => api.getUsers({ page, page_size: 20 }) })

  const createMutation = useMutation({ mutationFn: api.createUser, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); setShowForm(false); resetForm() } })
  const updateMutation = useMutation({ mutationFn: ({ id, data }: { id: number; data: any }) => api.updateUser(id, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); setEditing(null); resetForm() } })
  const deleteMutation = useMutation({ mutationFn: api.deleteUser, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }) })

  const resetForm = () => setFormData({ email: '', password: '', full_name: '', role: 'viewer', is_active: true })

  const handleSubmit = (e: React.FormEvent) => { e.preventDefault(); if (editing) { const { password, ...rest } = formData; updateMutation.mutate({ id: editing.id, data: rest }) } else createMutation.mutate(formData) }
  const startEdit = (user: any) => { setEditing(user); setFormData({ email: user.email, password: '', full_name: user.full_name || '', role: user.role, is_active: user.is_active }); setShowForm(true) }
  const handleDelete = (id: number) => { if (confirm('Delete this user?')) deleteMutation.mutate(id) }

  const getRoleBadge = (r: string) => { const colors: Record<string, string> = { admin: 'badge-danger', operator: 'badge-warning', viewer: 'badge-info' }; const icons: Record<string, any> = { admin: Shield, operator: User, viewer: Eye }; const Icon = icons[r]; return <span className={`badge ${colors[r] || 'badge-gray'}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>{Icon && <Icon style={{ width: 12, height: 12 }} />}{r}</span> }

  return (
    <div>
      <div className="page-header"><div><h1 className="page-title">Users</h1><p className="page-subtitle">Manage user accounts and roles</p></div><button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(true) }}><Plus style={{ width: 18, height: 18 }} /> Add User</button></div>
      {showForm && (
        <div className="modal-overlay" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header"><h2 className="modal-title">{editing ? 'Edit User' : 'Add User'}</h2><button className="modal-close" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>✕</button></div>
            <form onSubmit={handleSubmit} className="modal-body">
              <div className="form-group"><label className="form-label">Email</label><input className="input" type="email" value={formData.email} onChange={(e) => setFormData({...formData, email: e.target.value})} required disabled={editing} /></div>
              <div className="form-group"><label className="form-label">{editing ? 'New Password (leave blank to keep)' : 'Password'}</label><input type="password" className="input" value={formData.password} onChange={(e) => setFormData({...formData, password: e.target.value})} required={!editing} /></div>
              <div className="form-group"><label className="form-label">Full Name</label><input className="input" value={formData.full_name} onChange={(e) => setFormData({...formData, full_name: e.target.value})} /></div>
              <div className="form-group"><label className="form-label">Role</label><select className="input" value={formData.role} onChange={(e) => setFormData({...formData, role: e.target.value as any})}>{ROLES.map(r => <option key={r} value={r}>{r}</option>)}</select></div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}><input type="checkbox" checked={formData.is_active} onChange={(e) => setFormData({...formData, is_active: e.target.checked})} /> Active</label>
              <div className="modal-footer"><button type="button" className="btn btn-secondary" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>Cancel</button><button type="submit" className="btn btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>{createMutation.isPending || updateMutation.isPending ? <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} /> : 'Save'}</button></div>
            </form>
          </div>
        </div>
      )}
      <div className="card"><div className="table-container"><table><thead><tr><th>Email</th><th>Name</th><th>Role</th><th>Status</th><th>Last Login</th><th style={{ width: 100 }}>Actions</th></tr></thead><tbody>{data?.items?.length === 0 ? (<tr><td colSpan={6} style={{ textAlign: 'center', padding: 48 }}><div className="empty-state" style={{ padding: 0 }}><Users className="empty-state-icon" /><p>No users found</p></div></td></tr>) : (data?.items?.map((user: any) => (<tr key={user.id}><td style={{ fontWeight: 500 }}>{user.email}</td><td>{user.full_name || '—'}</td><td>{getRoleBadge(user.role)}</td><td>{user.is_active ? <span className="badge badge-success">Active</span> : <span className="badge badge-gray">Inactive</span>}</td><td style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'Never'}</td><td><button className="btn btn-ghost" onClick={() => startEdit(user)} style={{ padding: '6px' }}><Edit style={{ width: 16, height: 16 }} /></button><button className="btn btn-ghost" onClick={() => handleDelete(user.id)} style={{ padding: '6px', color: 'var(--color-danger)' }}><Trash2 style={{ width: 16, height: 16 }} /></button></td></tr>)))}</tbody></table></div></div>
    </div>
  )
}