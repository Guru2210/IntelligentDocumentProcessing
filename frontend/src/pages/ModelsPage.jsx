import { useState, useEffect } from 'react'
import { GitBranch, Star, Trash2, CheckCircle2, BarChart2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { getProjects, getModels, activateModel, deleteModel } from '../lib/api'

export default function ModelsPage() {
  const [projects, setProjects] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [models, setModels] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => { getProjects().then(setProjects).catch(() => {}) }, [])

  useEffect(() => {
    if (!selectedProjectId) { setModels([]); return }
    setLoading(true)
    getModels(selectedProjectId).then(m => { setModels(m); setLoading(false) }).catch(() => setLoading(false))
  }, [selectedProjectId])

  const handleActivate = async (model) => {
    try {
      await activateModel(selectedProjectId, model.id)
      setModels(prev => prev.map(m => ({ ...m, is_active: m.id === model.id })))
      toast.success(`v${model.version} activated`)
    } catch { toast.error('Failed to activate model') }
  }

  const handleDelete = async (model) => {
    if (model.is_active) return toast.error('Cannot delete the active model')
    if (!confirm(`Delete model v${model.version}?`)) return
    try {
      await deleteModel(selectedProjectId, model.id)
      setModels(prev => prev.filter(m => m.id !== model.id))
      toast.success('Model deleted')
    } catch { toast.error('Failed to delete model') }
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Models</h1>
          <p>View and manage trained model versions</p>
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <select className="input select" value={selectedProjectId} onChange={e => setSelectedProjectId(e.target.value)} style={{ maxWidth: 320 }}>
          <option value="">Select project...</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      {!selectedProjectId ? (
        <div className="empty-state">
          <div className="empty-state-icon"><GitBranch size={28} /></div>
          <h3>Select a project</h3>
          <p>Choose a project to view its trained model versions.</p>
        </div>
      ) : loading ? (
        <div className="empty-state"><span className="spinner" style={{ width: 28, height: 28 }} /></div>
      ) : models.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><GitBranch size={28} /></div>
          <h3>No models trained yet</h3>
          <p>Go to Training and train your first model to see it here.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {models.map(model => {
            const accPct = Math.round(model.overall_accuracy * 100)
            const accColor = accPct >= 90 ? 'var(--green)' : accPct >= 70 ? 'var(--amber)' : 'var(--red)'
            return (
              <div key={model.id} className="card" style={{ border: model.is_active ? '1px solid var(--accent)' : undefined }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                  <div style={{ width: 48, height: 48, borderRadius: 10, background: model.is_active ? 'var(--accent-glow)' : 'var(--bg-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', border: model.is_active ? '1px solid var(--accent)' : undefined }}>
                    <GitBranch size={22} color={model.is_active ? 'var(--accent-bright)' : 'var(--text-muted)'} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontWeight: 700, fontSize: '1rem' }}>Version {model.version}</span>
                      {model.is_active && <span className="badge badge-blue"><CheckCircle2 size={10} style={{ marginRight: 3 }} />Active</span>}
                      <span className={`badge ${model.model_type === 'neural' ? 'badge-purple' : 'badge-cyan'}`}>{model.model_type}</span>
                      <span style={{ marginLeft: 'auto', fontWeight: 700, fontSize: '1.1rem', color: accColor }}>{accPct}%</span>
                    </div>
                    <div style={{ display: 'flex', gap: 14, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      <span><FileText size={12} style={{ display: 'inline', marginRight: 4 }} />{model.training_doc_count} training docs</span>
                      <span>Created: {new Date(model.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {!model.is_active && (
                      <button className="btn btn-secondary btn-sm" onClick={() => handleActivate(model)}>
                        <Star size={13} /> Activate
                      </button>
                    )}
                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(model)} disabled={model.is_active}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                {/* Per-field metrics */}
                {Object.keys(model.field_metrics || {}).length > 0 && (
                  <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>Field Accuracy</div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 8 }}>
                      {Object.entries(model.field_metrics).map(([fieldName, f1]) => {
                        const pct = Math.round(f1 * 100)
                        return (
                          <div key={fieldName} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: '0.78rem', flex: 1 }} className="truncate">{fieldName}</span>
                            <div style={{ width: 60, height: 4, background: 'var(--border)', borderRadius: 99 }}>
                              <div style={{ width: `${pct}%`, height: '100%', background: pct >= 90 ? 'var(--green)' : pct >= 70 ? 'var(--amber)' : 'var(--red)', borderRadius: 99 }} />
                            </div>
                            <span style={{ fontSize: '0.75rem', fontWeight: 600, width: 32, textAlign: 'right', color: pct >= 90 ? 'var(--green)' : pct >= 70 ? 'var(--amber)' : 'var(--red)' }}>{pct}%</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function FileText({ size, style }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={style}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
}
