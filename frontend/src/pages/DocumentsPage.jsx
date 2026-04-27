import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Upload, FileText, Tag, Trash2, RefreshCw, ChevronRight, CheckCircle, Clock, AlertCircle, Eye } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { getProjects, getDocuments, uploadDocument, deleteDocument, setLabelStatus } from '../lib/api'

const STATUS_CONFIG = {
  unlabeled: { label: 'Unlabeled', badge: 'badge-gray', icon: Clock },
  in_progress: { label: 'In Progress', badge: 'badge-amber', icon: AlertCircle },
  complete: { label: 'Complete', badge: 'badge-green', icon: CheckCircle },
}

const OCR_STATUS = {
  pending: { label: 'Queued', badge: 'badge-gray' },
  processing: { label: 'OCR Running', badge: 'badge-amber' },
  complete: { label: 'Ready', badge: 'badge-green' },
  failed: { label: 'OCR Failed', badge: 'badge-red' },
}

function UploadZone({ projectId, onUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [uploadingFiles, setUploadingFiles] = useState([])

  const onDrop = useCallback(async (acceptedFiles) => {
    if (!projectId) return toast.error('Select a project first')
    setUploading(true)
    setUploadingFiles(acceptedFiles.map(f => ({ name: f.name, status: 'uploading' })))

    for (let i = 0; i < acceptedFiles.length; i++) {
      const file = acceptedFiles[i]
      try {
        const doc = await uploadDocument(projectId, file)
        setUploadingFiles(prev => prev.map((f, idx) => idx === i ? { ...f, status: 'done' } : f))
        onUploaded(doc)
      } catch (err) {
        setUploadingFiles(prev => prev.map((f, idx) => idx === i ? { ...f, status: 'error' } : f))
        toast.error(`Failed to upload ${file.name}`)
      }
    }
    setUploading(false)
    setTimeout(() => setUploadingFiles([]), 2000)
  }, [projectId, onUploaded])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'], 'image/*': ['.jpg', '.jpeg', '.png', '.tiff', '.bmp'] },
    multiple: true,
  })

  return (
    <div>
      <div {...getRootProps()} className={`upload-zone ${isDragActive ? 'drag-active' : ''}`}>
        <input {...getInputProps()} />
        <div className="upload-icon">
          <Upload size={24} />
        </div>
        <p style={{ fontWeight: 600, marginBottom: 4 }}>
          {isDragActive ? 'Drop files here...' : 'Drag & drop documents here'}
        </p>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Supports PDF, JPG, PNG, TIFF — max 100MB per file
        </p>
      </div>
      {uploadingFiles.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {uploadingFiles.map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
              {f.status === 'uploading' && <span className="spinner" />}
              {f.status === 'done' && <CheckCircle size={14} color="var(--green)" />}
              {f.status === 'error' && <AlertCircle size={14} color="var(--red)" />}
              <span style={{ fontSize: '0.8rem' }}>{f.name}</span>
              <span className={`badge ml-auto ${f.status === 'done' ? 'badge-green' : f.status === 'error' ? 'badge-red' : 'badge-amber'}`}>
                {f.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function DocumentsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const [projects, setProjects] = useState([])
  const [selectedProject, setSelectedProject] = useState(searchParams.get('project') || '')
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(false)
  const [polling, setPolling] = useState(false)

  useEffect(() => {
    getProjects().then(setProjects).catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedProject) {
      loadDocuments()
      const interval = setInterval(loadDocuments, 5000) // Poll for OCR status
      return () => clearInterval(interval)
    }
  }, [selectedProject])

  const loadDocuments = async () => {
    if (!selectedProject) return
    try {
      const docs = await getDocuments(selectedProject)
      setDocuments(docs)
    } catch {
      toast.error('Failed to load documents')
    }
  }

  const handleProjectChange = (pid) => {
    setSelectedProject(pid)
    setSearchParams({ project: pid })
  }

  const handleDelete = async (doc) => {
    if (!confirm(`Delete "${doc.original_filename}"?`)) return
    try {
      await deleteDocument(selectedProject, doc.id)
      setDocuments(prev => prev.filter(d => d.id !== doc.id))
      toast.success('Document deleted')
    } catch { toast.error('Failed to delete') }
  }

  const handleLabelDocument = (doc) => {
    navigate(`/label/${selectedProject}/${doc.id}`)
  }

  const handleMarkComplete = async (doc) => {
    try {
      const updated = await setLabelStatus(selectedProject, doc.id, 'complete')
      setDocuments(prev => prev.map(d => d.id === doc.id ? { ...d, label_status: 'complete' } : d))
      toast.success('Marked as complete')
    } catch { toast.error('Failed to update status') }
  }

  const completedCount = documents.filter(d => d.label_status === 'complete').length
  const readyCount = documents.filter(d => d.ocr_status === 'complete').length

  return (
    <div className="page-content">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Documents</h1>
          <p>Upload and manage training documents for your project</p>
        </div>
        {selectedProject && (
          <div className="page-header-actions">
            <button className="btn btn-secondary btn-sm" onClick={loadDocuments}>
              <RefreshCw size={14} /> Refresh
            </button>
            {completedCount >= 5 && (
              <button className="btn btn-primary btn-sm" onClick={() => navigate(`/train/${selectedProject}`)}>
                <ChevronRight size={14} /> Train Model ({completedCount} docs ready)
              </button>
            )}
          </div>
        )}
      </div>

      {/* Project Selector */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <label style={{ fontWeight: 500, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>Project:</label>
          <select className="input select" value={selectedProject} onChange={e => handleProjectChange(e.target.value)} style={{ maxWidth: 340 }}>
            <option value="">Select a project...</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          {selectedProject && (
            <div style={{ display: 'flex', gap: 10, marginLeft: 'auto' }}>
              <span className="badge badge-blue">{documents.length} docs</span>
              <span className="badge badge-green">{completedCount} labeled</span>
              <span className="badge badge-amber">{readyCount} OCR ready</span>
            </div>
          )}
        </div>
      </div>

      {!selectedProject ? (
        <div className="empty-state">
          <div className="empty-state-icon"><FileText size={28} /></div>
          <h3>Select a project</h3>
          <p>Choose a project from the dropdown above to manage its documents.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 20, flexDirection: 'column' }}>
          {/* Labeling progress */}
          {documents.length > 0 && (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontWeight: 500 }}>Labeling Progress</span>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  {completedCount} / {documents.length} complete
                  {completedCount < 5 && <span style={{ color: 'var(--amber)', marginLeft: 8 }}>⚠ Need 5+ to train</span>}
                </span>
              </div>
              <div className="progress-bar" style={{ height: 8 }}>
                <div className="progress-fill progress-green" style={{ width: `${documents.length > 0 ? (completedCount / documents.length) * 100 : 0}%` }} />
              </div>
            </div>
          )}

          {/* Upload */}
          <UploadZone
            projectId={selectedProject}
            onUploaded={(doc) => {
              setDocuments(prev => [...prev, doc])
              toast.success(`"${doc.original_filename}" uploaded — OCR running...`)
            }}
          />

          {/* Documents table */}
          {documents.length > 0 && (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Pages</th>
                    <th>Size</th>
                    <th>OCR Status</th>
                    <th>Label Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map(doc => {
                    const ocr = OCR_STATUS[doc.ocr_status] || OCR_STATUS.pending
                    const lbl = STATUS_CONFIG[doc.label_status] || STATUS_CONFIG.unlabeled
                    return (
                      <tr key={doc.id}>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <FileText size={16} color="var(--accent)" />
                            <span style={{ fontWeight: 500 }}>{doc.original_filename}</span>
                            {doc.is_scanned && <span className="badge badge-amber">scanned</span>}
                          </div>
                        </td>
                        <td>{doc.page_count || '—'}</td>
                        <td>{doc.file_size ? `${(doc.file_size / 1024).toFixed(0)} KB` : '—'}</td>
                        <td>
                          {doc.ocr_status === 'processing' && <span className="animate-pulse"><span className={`badge ${ocr.badge}`}>{ocr.label}</span></span>}
                          {doc.ocr_status !== 'processing' && <span className={`badge ${ocr.badge}`}>{ocr.label}</span>}
                        </td>
                        <td><span className={`badge ${lbl.badge}`}>{lbl.label}</span></td>
                        <td>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button
                              className="btn btn-secondary btn-sm"
                              disabled={doc.ocr_status !== 'complete'}
                              onClick={() => handleLabelDocument(doc)}
                              title={doc.ocr_status !== 'complete' ? 'Wait for OCR to complete' : 'Open in Label Studio'}
                            >
                              <Tag size={13} /> Label
                            </button>
                            {doc.label_status !== 'complete' && doc.ocr_status === 'complete' && (
                              <button className="btn btn-ghost btn-sm" onClick={() => handleMarkComplete(doc)}>
                                <CheckCircle size={13} />
                              </button>
                            )}
                            <button className="btn btn-ghost btn-icon btn-sm" style={{ color: 'var(--red)' }} onClick={() => handleDelete(doc)}>
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
