import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { Plus, Edit, Trash2, Search, Video, Wifi, WifiOff, Loader2 } from 'lucide-react'

export function CamerasPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [formData, setFormData] = useState({ name: '', source_type: 'rtsp', source_url: '', username: '', password: '', inference_enabled: true, inference_fps: 5 })

  const { data, isLoading } = useQuery({
    queryKey: ['cameras', page, search],
    queryFn: () => api.getCameras({ page, page_size: 20, is_active: true }),
  })

  const createMutation = useMutation({
    mutationFn: api.createCamera,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['cameras'] }); setShowForm(false); resetForm() },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => api.updateCamera(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['cameras'] }); setEditing(null); resetForm() },
  })

  const deleteMutation = useMutation({
    mutationFn: api.deleteCamera,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cameras'] }),
  })

  const resetForm = () => {
    setFormData({ name: '', source_type: 'rtsp', source_url: '', username: '', password: '', inference_enabled: true, inference_fps: 5 })
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editing) {
      updateMutation.mutate({ id: editing.id, data: formData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const startEdit = (camera: any) => {
    setEditing(camera)
    setFormData({ name: camera.name, source_type: camera.source_type, source_url: camera.source_url, username: camera.username || '', password: '', inference_enabled: camera.inference_enabled, inference_fps: camera.inference_fps })
    setShowForm(true)
  }

  const handleDelete = (id: number) => {
    if (confirm('Delete this camera?')) deleteMutation.mutate(id)
  }

  const getStatusIcon = (status: string) => status === 'online' ? <Wifi style={{ width: 16, height: 16, color: 'var(--color-success)' }} /> : <WifiOff style={{ width: 16, height: 16, color: 'var(--color-danger)' }} />

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Cameras</h1>
          <p className="page-subtitle">Manage video sources and inference settings</p>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
          <Plus style={{ width: 18, height: 18 }} /> Add Camera
        </button>
      </div>

      {showForm && (
        <div className="modal-overlay" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{editing ? 'Edit Camera' : 'Add Camera'}</h2>
              <button className="modal-close" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-body">
              <div className="form-group">
                <label className="form-label">Name</label>
                <input className="input" value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} required />
              </div>
              <div className="form-group">
                <label className="form-label">Source Type</label>
                <select className="input" value={formData.source_type} onChange={(e) => setFormData({...formData, source_type: e.target.value})}>
                  <option value="rtsp">RTSP</option>
                  <option value="file">File</option>
                  <option value="webcam">Webcam</option>
                  <option value="onvif">ONVIF</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Source URL</label>
                <input className="input" value={formData.source_url} onChange={(e) => setFormData({...formData, source_url: e.target.value})} placeholder="rtsp://..." required />
              </div>
              <div className="form-group">
                <label className="form-label">Username (optional)</label>
                <input className="input" value={formData.username} onChange={(e) => setFormData({...formData, username: e.target.value})} />
              </div>
              <div className="form-group">
                <label className="form-label">Password (optional)</label>
                <input type="password" className="input" value={formData.password} onChange={(e) => setFormData({...formData, password: e.target.value})} />
              </div>
              <div style={{ display: 'flex', gap: 16 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input type="checkbox" checked={formData.inference_enabled} onChange={(e) => setFormData({...formData, inference_enabled: e.target.checked})} />
                  Inference Enabled
                </label>
                <div style={{ flex: 1 }}>
                  <label className="form-label">Inference FPS</label>
                  <input type="number" className="input" min="1" max="30" value={formData.inference_fps} onChange={(e) => setFormData({...formData, inference_fps: Number(e.target.value)})} />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>
                  {createMutation.isPending || updateMutation.isPending ? <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} /> : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="card">
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--color-border)', display: 'flex', gap: 16 }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <input type="text" className="input" placeholder="Search cameras..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cline x1='21' y1='21' x2='16.65' y2='16.65'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px center', paddingRight: 40 }} />
          </div>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Source</th>
                <th>Status</th>
                <th>Inference</th>
                <th>FPS</th>
                <th style={{ width: 120 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 48 }}><Loader2 style={{ width: 24, height: 24, margin: '0 auto', animation: 'spin 1s linear infinite' }} /></td></tr>
              ) : data?.items?.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: 'center', padding: 48 }}><div className="empty-state" style={{ padding: 0 }}><Video className="empty-state-icon" /><p>No cameras configured</p></div></td></tr>
              ) : (
                data?.items?.map((camera: any) => (
                  <tr key={camera.id}>
                    <td style={{ fontWeight: 500 }}>{camera.name}</td>
                    <td><span className="badge badge-gray">{camera.source_type.toUpperCase()}</span></td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--color-text-muted)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{camera.source_url}</td>
                    <td>{getStatusIcon(camera.status)} <span className={`badge ${camera.status === 'online' ? 'badge-success' : 'badge-danger'}`}>{camera.status}</span></td>
                    <td>{camera.inference_enabled ? <span className="badge badge-success">On</span> : <span className="badge badge-gray">Off</span>}</td>
                    <td>{camera.inference_fps}</td>
                    <td>
                      <button className="btn btn-ghost" onClick={() => startEdit(camera)} style={{ padding: '6px' }} title="Edit"><Edit style={{ width: 16, height: 16 }} /></button>
                      <button className="btn btn-ghost" onClick={() => handleDelete(camera.id)} style={{ padding: '6px', color: 'var(--color-danger)' }} title="Delete"><Trash2 style={{ width: 16, height: 16 }} /></button>
                    </td>
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