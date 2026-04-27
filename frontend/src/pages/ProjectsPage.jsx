import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, FolderOpen, Trash2, ChevronRight, FileText, Tag, Brain } from 'lucide-react'
import toast from 'react-hot-toast'
import { getProjects, createProject, deleteProject, getPrebuiltSchemas } from '../lib/api'

const COLORS = ['#3B82F6','#8B5CF6','#10B981','#F59E0B','#EF4444','#F97316','#06B6D4','#7C3AED']
const MODEL_TYPES = [
  { value: 'template', label: 'Template Model', desc: 'Fixed-layout forms (fast, CPU-only)' },
  { value: 'neural', label: 'Neural Model', desc: 'Variable-layout documents (LayoutLMv3)' },
]

function CreateProjectModal({ onClose, onCreate }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [modelType, setModelType] = useState('template')
  const [schema, setSchema] = useState('')
  const [schemas, setSchemas] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getPrebuiltSchemas().then(setSchemas).catch(() => {})
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return toast.error('Project name is required')
    setLoading(true)
    try {
      const project = await createProject({ name: name.trim(), description, model_type: modelType, prebuilt_schema: schema || null })
      toast.success(`Project "${project.name}" created!`)
      onCreate(project)
      onClose()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create project')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Create New Project</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="form-group">
              <label className="form-label">Project Name *</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g., Invoice Extractor" autoFocus />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea className="input" value={description} onChange={e => setDescription(e.target.value)} placeholder="What type of documents will you process?" rows={2} style={{ resize: 'vertical' }} />
            </div>
            <div className="form-group">
              <label className="form-label">Model Type</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {MODEL_TYPES.map(mt => (
                  <label key={mt.value} style={{
                    display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px',
                    background: modelType === mt.value ? 'var(--accent-glow)' : 'var(--bg-secondary)',
                    border: `1px solid ${modelType === mt.value ? 'var(--accent)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                  }}>
                    <input type="radio" value={mt.value} checked={modelType === mt.value} onChange={() => setModelType(mt.value)} style={{ marginTop: 2 }} />
                    <div>
                      <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>{mt.label}</div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{mt.desc}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Prebuilt Schema (optional)</label>
              <select className="input select" value={schema} onChange={e => setSchema(e.target.value)}>
                <option value="">Custom schema (define your own fields)</option>
                {schemas.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1).replace('_', ' ')}</option>)}
              </select>
              {schema && <p style={{ fontSize: '0.75rem', color: 'var(--green)', marginTop: 4 }}>✓ Fields will be auto-populated from {schema} template</p>}
            </div>
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <span className="spinner" /> : <Plus size={16} />}
              Create Project
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function ProjectCard({ project, onDelete, onNavigate }) {
  const labelPct = project.document_count > 0 ? Math.round((project.labeled_count / project.document_count) * 100) : 0
  const modelColor = project.model_type === 'neural' ? 'badge-purple' : 'badge-blue'

  return (
    <div className="card card-hover" style={{ cursor: 'pointer', position: 'relative' }} onClick={() => onNavigate(project)}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 42, height: 42, borderRadius: '10px', background: 'linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <FolderOpen size={20} color="white" />
          </div>
          <div>
            <h3 style={{ fontWeight: 600, fontSize: '1rem', marginBottom: 2 }}>{project.name}</h3>
            <span className={`badge ${modelColor}`}>{project.model_type}</span>
          </div>
        </div>
        <button
          className="btn btn-ghost btn-icon btn-sm"
          style={{ color: 'var(--text-muted)' }}
          onClick={e => { e.stopPropagation(); onDelete(project) }}
        >
          <Trash2 size={14} />
        </button>
      </div>
      {project.description && (
        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 14, lineHeight: 1.5 }}>{project.description}</p>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
        {[
          { icon: FileText, label: 'Documents', value: project.document_count },
          { icon: Tag, label: 'Labeled', value: project.labeled_count },
          { icon: Brain, label: 'Fields', value: project.fields?.length || 0 },
        ].map(stat => (
          <div key={stat.label} style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', padding: '8px 10px' }}>
            <stat.icon size={14} color="var(--text-secondary)" />
            <div>
              <div style={{ fontWeight: 700, fontSize: '1rem', lineHeight: 1 }}>{stat.value}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{stat.label}</div>
            </div>
          </div>
        ))}
      </div>
      {project.document_count > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
            <span>Labeling progress</span>
            <span>{labelPct}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill progress-blue" style={{ width: `${labelPct}%` }} />
          </div>
        </div>
      )}
      <div style={{ position: 'absolute', bottom: 16, right: 16, color: 'var(--text-muted)' }}>
        <ChevronRight size={16} />
      </div>
    </div>
  )
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    try {
      setLoading(true)
      const data = await getProjects()
      setProjects(data)
    } catch (err) {
      toast.error('Failed to load projects')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (project) => {
    if (!confirm(`Delete project "${project.name}"? This cannot be undone.`)) return
    try {
      await deleteProject(project.id)
      setProjects(prev => prev.filter(p => p.id !== project.id))
      toast.success('Project deleted')
    } catch {
      toast.error('Failed to delete project')
    }
  }

  const handleNavigate = (project) => {
    navigate(`/documents?project=${project.id}`)
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Projects</h1>
          <p>Create and manage your document intelligence projects</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            <Plus size={16} /> New Project
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid-4" style={{ marginBottom: 24 }}>
        {[
          { label: 'Total Projects', value: projects.length, color: 'blue' },
          { label: 'Total Documents', value: projects.reduce((s, p) => s + p.document_count, 0), color: 'purple' },
          { label: 'Labeled Docs', value: projects.reduce((s, p) => s + p.labeled_count, 0), color: 'green' },
          { label: 'Template Models', value: projects.filter(p => p.model_type === 'template').length, color: 'amber' },
        ].map(stat => (
          <div key={stat.label} className={`stat-card`}>
            <div>
              <div className="stat-number">{stat.value}</div>
              <div className="stat-label">{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      {loading ? (
        <div className="empty-state">
          <div className="spinner" style={{ width: 30, height: 30, margin: '0 auto 12px' }} />
          <p>Loading projects...</p>
        </div>
      ) : projects.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><FolderOpen size={28} /></div>
          <h3>No projects yet</h3>
          <p>Create your first document intelligence project to start labeling and training extraction models.</p>
          <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => setShowCreate(true)}>
            <Plus size={16} /> Create First Project
          </button>
        </div>
      ) : (
        <div className="grid-3">
          {projects.map(project => (
            <ProjectCard key={project.id} project={project} onDelete={handleDelete} onNavigate={handleNavigate} />
          ))}
          <div
            className="card"
            style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10, minHeight: 160, border: '2px dashed var(--border)', background: 'transparent' }}
            onClick={() => setShowCreate(true)}
          >
            <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Plus size={22} color="var(--accent)" />
            </div>
            <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>New Project</span>
          </div>
        </div>
      )}

      {showCreate && <CreateProjectModal onClose={() => setShowCreate(false)} onCreate={(p) => setProjects(prev => [p, ...prev])} />}
    </div>
  )
}
