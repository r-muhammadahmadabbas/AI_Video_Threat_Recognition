import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { Plus, Edit, Trash2, MapPin, Loader2, X, Undo2, RotateCcw } from 'lucide-react'

const ZONE_TYPES = ['restricted', 'loitering', 'privacy', 'crowd'] as const

interface Point {
  x: number
  y: number
}

interface PolygonEditorProps {
  cameraId: number | null
  initialPolygon: Point[][]
  onPolygonChange: (polygon: Point[][]) => void
  frameWidth: number
  frameHeight: number
}

function PolygonEditor({ cameraId, initialPolygon, onPolygonChange, frameWidth, frameHeight }: PolygonEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [points, setPoints] = useState<Point[]>(initialPolygon[0] || [])
  const [history, setHistory] = useState<Point[][]>([initialPolygon[0] || []])
  const [historyIndex, setHistoryIndex] = useState(0)
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageError, setImageError] = useState(false)

  const snapshotUrl = cameraId ? api.getCameraSnapshot(cameraId) : null

  useEffect(() => {
    if (snapshotUrl) {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => {
        imgRef.current = img
        setImageLoaded(true)
        setImageError(false)
      }
      img.onerror = () => setImageError(true)
      img.src = snapshotUrl
    } else {
      imgRef.current = null
      setImageLoaded(false)
      setImageError(false)
    }
  }, [snapshotUrl])

  useEffect(() => {
    setPoints(initialPolygon[0] || [])
    setHistory([initialPolygon[0] || []])
    setHistoryIndex(0)
  }, [initialPolygon])

  const draw = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    const scaleX = frameWidth / rect.width
    const scaleY = frameHeight / rect.height

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (imageLoaded && imgRef.current) {
      ctx.drawImage(imgRef.current, 0, 0, canvas.width, canvas.height)
    } else if (imageError) {
      ctx.fillStyle = 'var(--color-bg)'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.fillStyle = 'var(--color-text-muted)'
      ctx.font = '14px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('Could not load camera snapshot', canvas.width / 2, canvas.height / 2)
    }

    if (points.length > 0) {
      ctx.strokeStyle = '#22c55e'
      ctx.lineWidth = 2
      ctx.beginPath()
      points.forEach((p, i) => {
        const x = p.x / scaleX
        const y = p.y / scaleY
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      if (points.length > 2) ctx.closePath()
      ctx.stroke()

      ctx.fillStyle = 'rgba(34, 197, 94, 0.15)'
      if (points.length > 2) ctx.fill()

      points.forEach((p, i) => {
        const x = p.x / scaleX
        const y = p.y / scaleY
        ctx.fillStyle = i === 0 ? '#16a34a' : '#22c55e'
        ctx.beginPath()
        ctx.arc(x, y, 6, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = 'white'
        ctx.lineWidth = 2
        ctx.stroke()

        ctx.fillStyle = 'white'
        ctx.font = '10px monospace'
        ctx.textAlign = 'center'
        ctx.fillText(`${i + 1}`, x, y + 3)
      })
    }
  }

  useEffect(() => {
    draw()
  }, [points, imageLoaded, imageError, frameWidth, frameHeight])

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const scaleX = frameWidth / rect.width
    const scaleY = frameHeight / rect.height
    const x = Math.round((e.nativeEvent.offsetX) * scaleX)
    const y = Math.round((e.nativeEvent.offsetY) * scaleY)

    const clampedX = Math.max(0, Math.min(frameWidth - 1, x))
    const clampedY = Math.max(0, Math.min(frameHeight - 1, y))

    const newPoints = [...points, { x: clampedX, y: clampedY }]
    setPoints(newPoints)
    pushHistory(newPoints)
  }

  const pushHistory = (newPoints: Point[]) => {
    const newHistory = history.slice(0, historyIndex + 1)
    newHistory.push(newPoints)
    setHistory(newHistory)
    setHistoryIndex(newHistory.length - 1)
  }

  const undo = () => {
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1
      setHistoryIndex(newIndex)
      setPoints(history[newIndex])
    }
  }

  const clear = () => {
    const newPoints: Point[] = []
    setPoints(newPoints)
    pushHistory(newPoints)
  }

  const closePolygon = () => {
    if (points.length < 3) return
    const newPoints = [...points]
    if (newPoints[0].x !== newPoints[newPoints.length - 1].x || newPoints[0].y !== newPoints[newPoints.length - 1].y) {
      newPoints.push({ ...newPoints[0] })
      setPoints(newPoints)
      pushHistory(newPoints)
    }
  }

  const removeLastPoint = () => {
    if (points.length === 0) return
    const newPoints = points.slice(0, -1)
    setPoints(newPoints)
    pushHistory(newPoints)
  }

  useEffect(() => {
    onPolygonChange([points])
  }, [points, onPolygonChange])

  return (
    <div style={{ position: 'relative' }}>
      <canvas
        ref={canvasRef}
        width={frameWidth}
        height={frameHeight}
        style={{
          width: '100%',
          maxWidth: frameWidth,
          height: 'auto',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
          background: 'var(--color-bg)',
          cursor: 'crosshair',
        }}
        onClick={handleClick}
      />
      <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <button type="button" className="btn btn-secondary" onClick={undo} disabled={historyIndex <= 0}>
          <Undo2 style={{ width: 16, height: 16 }} /> Undo
        </button>
        <button type="button" className="btn btn-secondary" onClick={removeLastPoint} disabled={points.length === 0}>
          <X style={{ width: 16, height: 16 }} /> Remove Last
        </button>
        <button type="button" className="btn btn-secondary" onClick={closePolygon} disabled={points.length < 3}>
          <RotateCcw style={{ width: 16, height: 16 }} /> Close Polygon
        </button>
        <button type="button" className="btn btn-ghost" onClick={clear}>
          Clear All
        </button>
        <span style={{ fontSize: 12, color: 'var(--color-text-muted)', marginLeft: 'auto' }}>
          {points.length} point{points.length !== 1 ? 's' : ''}
        </span>
      </div>
    </div>
  )
}

export function ZonesPage() {
  const queryClient = useQueryClient()
  const [page] = useState(1)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [formData, setFormData] = useState({
    name: '',
    camera_id: 0,
    zone_type: 'restricted',
    polygon: [[]] as Point[][],
    is_active: true
  })
  const [editorFrameSize, setEditorFrameSize] = useState({ width: 640, height: 480 })

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

  const handleCameraChange = (cameraId: number) => {
    setFormData(prev => ({ ...prev, camera_id: cameraId }))
    const camera = camerasData?.items?.find((c: any) => c.id === cameraId)
    if (camera?.width && camera?.height) {
      setEditorFrameSize({ width: camera.width, height: camera.height })
    }
  }

  const startEdit = (zone: any) => {
    setEditing(zone)
    setFormData({
      name: zone.name,
      camera_id: zone.camera_id,
      zone_type: zone.zone_type,
      polygon: zone.polygon,
      is_active: zone.is_active
    })
    if (zone.camera_id) {
      const camera = camerasData?.items?.find((c: any) => c.id === zone.camera_id)
      if (camera?.width && camera?.height) {
        setEditorFrameSize({ width: camera.width, height: camera.height })
      }
    }
    setShowForm(true)
  }

  const handleDelete = (id: number) => { if (confirm('Delete this zone?')) deleteMutation.mutate(id) }

  const typeColors: Record<string, string> = {
    restricted: 'badge-danger',
    loitering: 'badge-warning',
    privacy: 'badge-info',
    crowd: 'badge-primary'
  }

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
            <div className="modal-header">
              <h2 className="modal-title">{editing ? 'Edit Zone' : 'Add Zone'}</h2>
              <button className="modal-close" onClick={() => { setShowForm(false); setEditing(null); resetForm() }}>✕</button>
            </div>
            <form onSubmit={handleSubmit} className="modal-body">
              <div className="form-group">
                <label className="form-label">Name</label>
                <input className="input" value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} required />
              </div>
              <div className="form-group">
                <label className="form-label">Camera</label>
                <select className="input" value={formData.camera_id} onChange={(e) => handleCameraChange(Number(e.target.value))} required>
                  <option value={0}>Select camera</option>
                  {camerasData?.items?.map((c: any) => <option key={c.id} value={c.id}>{c.name} ({c.width}x{c.height})</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Zone Type</label>
                <select className="input" value={formData.zone_type} onChange={(e) => setFormData({...formData, zone_type: e.target.value as any})}>
                  {ZONE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Polygon Editor</label>
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 8 }}>
                  Click on the image to add points. Click the first point again or use "Close Polygon" to close the shape.
                </p>
                {formData.camera_id ? (
                  <PolygonEditor
                    cameraId={formData.camera_id}
                    initialPolygon={formData.polygon}
                    onPolygonChange={(polygon) => setFormData(prev => ({ ...prev, polygon }))}
                    frameWidth={editorFrameSize.width}
                    frameHeight={editorFrameSize.height}
                  />
                ) : (
                  <div style={{ padding: 24, textAlign: 'center', color: 'var(--color-text-muted)', border: '1px dashed var(--color-border)', borderRadius: 'var(--radius-md)' }}>
                    Select a camera to load its snapshot and draw the polygon
                  </div>
                )}
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={formData.is_active} onChange={(e) => setFormData({...formData, is_active: e.target.checked})} />
                Active
              </label>
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
                    <td>
                      <button className="btn btn-ghost" onClick={() => startEdit(zone)} style={{ padding: '6px' }}><Edit style={{ width: 16, height: 16 }} /></button>
                      <button className="btn btn-ghost" onClick={() => handleDelete(zone.id)} style={{ padding: '6px', color: 'var(--color-danger)' }}><Trash2 style={{ width: 16, height: 16 }} /></button>
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