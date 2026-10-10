import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { Plus, Edit, Trash2, MapPin, Loader2 } from 'lucide-react'

const ZONE_TYPES = ['restricted', 'loitering', 'privacy', 'crowd'] as const

export function ZonesPage() {
  const queryClient = useQueryClient()
  const [page] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [formData, setFormData] = useState({ name: '', camera_id: 0, zone_type: 'restricted', polygon: [[]], is_active: true })

  const { data: zonesData } = useQuery({
    queryKey: ['zones', page],
    queryFn: () => api.getZones({ page, page_size: 20 }),
  })

  const { data: camerasData } = useQuery({
    queryKey: ['cameras-all'],
    queryFn: () => api.getCameras({ page_size: 100 }),
  })

  const createMutation = useMutation({
    mutationFn: api.createZone,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['zones'] }); setShowForm(false); resetForm() },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => api.updateZone(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['zones'] }); setEditing(null); resetForm() },
  })

  const deleteMutation = useMutation({
    mutationFn: api.deleteZone,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['zones'] }),
  })

  const resetForm = () => setFormData({ name: '', camera_id: 0, zone_type: 'restricted', polygon: [[]], is_active: true })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editing) updateMutation.mutate({ id: editing.id, data: formData })
    else createMutation.mutate(formData)
  }

  const startEdit = (zone: any) => {
    setEditing(zone)
    setFormData({ name: zone.name, camera_id: zone.camera_id, zone_type: zone.zone_type, polygon: zone.polygon, is_active: zone.is_active })
    setShowForm(true)
  }

  const handleDelete = (id: number) => { if (confirm('Delete this zone?')) deleteMutation.mutate(id) }

  const typeColors: Record<string, string> = { restricted: 'badge-danger', loitering: 'badge-warning', privacy: 'badge-info', crowd: 'badge-primary' }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Zones</h1>
          <p className="page-subtitle">Define detection zones on camera feeds</p>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
          <Plus style={{ width: 18, height: 18 }} /> Add Zone
        </button>
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header"><h2 className="modal-title">{editing ? 'Edit Zone' : 'Add Zone'}</h2><button className="modal-close" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>✕</button></div>
            <form onSubmit={handleSubmit} className="modal-body">
              <div className="form-group"><label className="form-label">Name</label><input className="input" value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} required /></div>
              <div className="form-group"><label className="form-label">Camera</label><select className="input" value={formData.camera_id} onChange={(e) => setFormData({...formData, camera_id: Number(e.target.value)})} required><option value={0}>Select camera</option>{camerasData?.items?.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
              <div className="form-group"><label className="form-label">Zone Type</label><select className="input" value={formData.zone_type} onChange={(e) => setFormData({...formData, zone_type: e.target.value as any})}>{ZONE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}</select></div>
              <div className="form-group"><label className="form-label">Polygon (JSON array of [x,y] points)</label><textarea className="input" style={{ minHeight: 100, fontFamily: 'monospace', fontSize: 12 }} value={JSON.stringify(formData.polygon, null, 2)} onChange={(e) => { try { setFormData({...formData, polygon: JSON.parse(e.target.value) }) } catch {} }} placeholder="[[100,100],[200,100],[200,200],[100,200]]" /></div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}><input type="checkbox" checked={formData.is_active} onChange={(e) => setFormData({...formData, is_active: e.target.checked})} /> Active</label>
              <div className="modal-footer"><button type="button" className="btn btn-secondary" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>Cancel</button><button type="submit" className="btn btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>{createMutation.isPending || updateMutation.isPending ? <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} /> : 'Save'}</button></div>
            </form>
          </div>
        </div>
      )}

      <div className="card">
        <div className="table-container">
          <table>
            <thead><tr><th>Name</th><th>Camera</th><th>Type</th><th>Active</th><th>Polygon Points</th><th style={{ width: 100 }}>Actions</th></tr></thead>
            <tbody>
              {zonesData?.items?.length === 0 ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 48 }}><div className="empty-state" style={{ padding: 0 }}><MapPin className="empty-state-icon" /><p>No zones defined</p></div></td></tr>
              ) : (
                zonesData?.items?.map((zone: any) => (
                  <tr key={zone.id}>
                    <td style={{ fontWeight: 500 }}>{zone.name}</td>
                    <td>Camera #{zone.camera_id}</td>
                    <td><span className={`badge ${typeColors[zone.zone_type] || 'badge-gray'}`}>{zone.zone_type}</span></td>
                    <td>{zone.is_active ? <span className="badge badge-success">Yes</span> : <span className="badge badge-gray">No</span>}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--color-text-muted)' }}>{zone.polygon?.[0]?.length || 0} points</td>
                    <td><button className="btn btn-ghost" onClick={() => startEdit(zone)} style={{ padding: '6px' }}><Edit style={{ width: 16, height: 16 }} /></button><button className="btn btn-ghost" onClick={() => handleDelete(zone.id)} style={{ padding: '6px', color: 'var(--color-danger)' }}><Trash2 style={{ width: 16, height: 16 }} /></button></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}