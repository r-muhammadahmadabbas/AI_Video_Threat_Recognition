import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { Plus, Edit, Trash2, Shield, Loader2 } from 'lucide-react'

const RULE_TYPES = ['restricted_zone_entry', 'loitering', 'person_down', 'fight', 'crowd_anomaly', 'weapon'] as const
const SEVERITIES = ['low', 'medium', 'high', 'critical'] as const

export function RulesPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [formData, setFormData] = useState({ name: '', camera_id: 0, zone_id: undefined, rule_type: 'restricted_zone_entry', severity: 'medium', is_active: true, config_json: {}, cooldown_seconds: 60, model_version: '' })

  const { data: rulesData } = useQuery({ queryKey: ['rules', page], queryFn: () => api.getRules({ page, page_size: 20 }) })
  const { data: camerasData } = useQuery({ queryKey: ['cameras-all'], queryFn: () => api.getCameras({ page_size: 100 }) })
  const { data: zonesData } = useQuery({ queryKey: ['zones-all'], queryFn: () => api.getZones({ page_size: 100 }) })

  const createMutation = useMutation({ mutationFn: api.createRule, onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rules'] }); setShowForm(false); resetForm() } })
  const updateMutation = useMutation({ mutationFn: ({ id, data }: { id: number; data: any }) => api.updateRule(id, data), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rules'] }); setEditing(null); resetForm() } })
  const deleteMutation = useMutation({ mutationFn: api.deleteRule, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules'] }) })

  const resetForm = () => setFormData({ name: '', camera_id: 0, zone_id: undefined, rule_type: 'restricted_zone_entry', severity: 'medium', is_active: true, config_json: {}, cooldown_seconds: 60, model_version: '' })

  const handleSubmit = (e: React.FormEvent) => { e.preventDefault(); if (editing) updateMutation.mutate({ id: editing.id, data: formData }); else createMutation.mutate(formData) }
  const startEdit = (rule: any) => { setEditing(rule); setFormData({...rule, zone_id: rule.zone_id || undefined}); setShowForm(true) }
  const handleDelete = (id: number) => { if (confirm('Delete this rule?')) deleteMutation.mutate(id) }

  const getSeverityBadge = (s: string) => { const colors: Record<string, string> = { low: 'badge-info', medium: 'badge-warning', high: 'badge-danger', critical: 'badge-danger' }; return <span className={`badge ${colors[s] || 'badge-gray'}`}>{s}</span> }

  return (
    <div>
      <div className="page-header"><div><h1 className="page-title">Threat Rules</h1><p className="page-subtitle">Configure detection rules for each camera</p></div><button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(true) }}><Plus style={{ width: 18, height: 18 }} /> Add Rule</button></div>
      {showForm && (
        <div className="modal-overlay" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header"><h2 className="modal-title">{editing ? 'Edit Rule' : 'Add Rule'}</h2><button className="modal-close" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>✕</button></div>
            <form onSubmit={handleSubmit} className="modal-body">
              <div className="form-group"><label className="form-label">Name</label><input className="input" value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} required /></div>
              <div className="form-group"><label className="form-label">Camera</label><select className="input" value={formData.camera_id} onChange={(e) => setFormData({...formData, camera_id: Number(e.target.value)})} required><option value={0}>Select camera</option>{camerasData?.items?.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></div>
              <div className="form-group"><label className="form-label">Zone (optional)</label><select className="input" value={formData.zone_id || 0} onChange={(e) => setFormData({...formData, zone_id: Number(e.target.value) || undefined})}><option value={0}>No zone</option>{zonesData?.items?.map((z: any) => <option key={z.id} value={z.id}>{z.name} ({z.zone_type})</option>)}</select></div>
              <div className="form-group"><label className="form-label">Rule Type</label><select className="input" value={formData.rule_type} onChange={(e) => setFormData({...formData, rule_type: e.target.value as any})}>{RULE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}</select></div>
              <div className="form-group"><label className="form-label">Severity</label><select className="input" value={formData.severity} onChange={(e) => setFormData({...formData, severity: e.target.value as any})}>{SEVERITIES.map(s => <option key={s} value={s}>{s}</option>)}</select></div>
              <div className="form-group"><label className="form-label">Cooldown (seconds)</label><input type="number" className="input" min="0" max="3600" value={formData.cooldown_seconds} onChange={(e) => setFormData({...formData, cooldown_seconds: Number(e.target.value)})} /></div>
              <div className="form-group"><label className="form-label">Config (JSON)</label><textarea className="input" style={{ minHeight: 80, fontFamily: 'monospace', fontSize: 12 }} value={JSON.stringify(formData.config_json, null, 2)} onChange={(e) => { try { setFormData({...formData, config_json: JSON.parse(e.target.value) }) } catch {} }} /></div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}><input type="checkbox" checked={formData.is_active} onChange={(e) => setFormData({...formData, is_active: e.target.checked})} /> Active</label>
              <div className="modal-footer"><button type="button" className="btn btn-secondary" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>Cancel</button><button type="submit" className="btn btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>{createMutation.isPending || updateMutation.isPending ? <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} /> : 'Save'}</button></div>
            </form>
          </div>
        </div>
      )}
      <div className="card"><div className="table-container"><table><thead><tr><th>Name</th><th>Camera</th><th>Zone</th><th>Type</th><th>Severity</th><th>Cooldown</th><th>Active</th><th style={{ width: 100 }}>Actions</th></tr></thead><tbody>{rulesData?.items?.length === 0 ? (<tr><td colSpan={8} style={{ textAlign: 'center', padding: 48 }}><div className="empty-state" style={{ padding: 0 }}><Shield className="empty-state-icon" /><p>No rules configured</p></div></td></tr>) : (rulesData?.items?.map((rule: any) => (<tr key={rule.id}><td style={{ fontWeight: 500 }}>{rule.name}</td><td>Camera #{rule.camera_id}</td><td>{rule.zone_id ? `Zone #${rule.zone_id}` : '—'}</td><td><span className="badge badge-gray">{rule.rule_type}</span></td><td>{getSeverityBadge(rule.severity)}</td><td>{rule.cooldown_seconds}s</td><td>{rule.is_active ? <span className="badge badge-success">Yes</span> : <span className="badge badge-gray">No</span>}</td><td><button className="btn btn-ghost" onClick={() => startEdit(rule)} style={{ padding: '6px' }}><Edit style={{ width: 16, height: 16 }} /></button><button className="btn btn-ghost" onClick={() => handleDelete(rule.id)} style={{ padding: '6px', color: 'var(--color-danger)' }}><Trash2 style={{ width: 16, height: 16 }} /></button></td></tr>)))}</tbody></table></div></div>
    </div>
  )
}