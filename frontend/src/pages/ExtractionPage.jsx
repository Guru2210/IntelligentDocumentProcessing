import { useState, useEffect, useRef } from 'react'
import { Upload, Zap, Download, FileText, CheckCircle, Clock, AlertCircle, Eye, RefreshCw } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import toast from 'react-hot-toast'
import { getProjects, getModels, submitExtraction, getJobStatus, getResultDownloadUrl } from '../lib/api'

function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100)
  const color = pct >= 90 ? 'var(--green)' : pct >= 70 ? 'var(--amber)' : 'var(--red)'
  return (
    <div className="conf-bar">
      <div className="conf-bar-track">
        <div className="conf-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontSize: '0.75rem', fontWeight: 600, color, minWidth: 36 }}>{pct}%</span>
    </div>
  )
}

function FieldResult({ name, data }) {
  if (!data) return null
  if (data.type === 'array') {
    const rows = data.valueArray || []
    if (rows.length === 0) return null
    const cols = Object.keys(rows[0]?.valueObject || {})
    return (
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: 8, color: 'var(--accent-bright)' }}>{name} (table)</div>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                {cols.map(c => <th key={c}>{c}</th>)}
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                const obj = row.valueObject || {}
                const avgConf = cols.reduce((s, c) => s + (obj[c]?.confidence || 0), 0) / Math.max(cols.length, 1)
                return (
                  <tr key={i}>
                    {cols.map(c => <td key={c}>{obj[c]?.valueString || obj[c]?.valueNumber || '—'}</td>)}
                    <td><ConfidenceBar value={avgConf} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    )
  }
  const value = data.valueString || data.valueNumber || data.valueDate || data.valueInteger || data.valueSelectionMark || ''
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', marginBottom: 6 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{name}</div>
        <div style={{ fontWeight: 600, fontSize: '0.95rem', marginTop: 1 }}>{String(value) || '—'}</div>
      </div>
      <div style={{ width: 120 }}>
        <ConfidenceBar value={data.confidence} />
      </div>
    </div>
  )
}

export default function ExtractionPage() {
  const [projects, setProjects] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [models, setModels] = useState([])
  const [selectedModelId, setSelectedModelId] = useState('')
  const [outputFormat, setOutputFormat] = useState('json')
  const [job, setJob] = useState(null)
  const [result, setResult] = useState(null)
  const [polling, setPolling] = useState(false)
  const pollRef = useRef(null)

  useEffect(() => { getProjects().then(setProjects).catch(() => {}) }, [])

  useEffect(() => {
    if (!selectedProjectId) { setModels([]); setSelectedModelId(''); return }
    getModels(selectedProjectId).then(m => {
      setModels(m)
      const active = m.find(mv => mv.is_active)
      if (active) setSelectedModelId(active.id)
    }).catch(() => {})
  }, [selectedProjectId])

  const { getRootProps, getInputProps, isDragActive, acceptedFiles } = useDropzone({
    multiple: false,
    accept: { 'application/pdf': ['.pdf'], 'image/*': ['.jpg', '.jpeg', '.png', '.tiff'] },
  })

  const file = acceptedFiles[0]

  const handleExtract = async () => {
    if (!file) return toast.error('Drop a document first')
    if (!selectedModelId) return toast.error('Select a model')
    try {
      const submitted = await submitExtraction(selectedModelId, file, outputFormat)
      setJob(submitted)
      setResult(null)
      toast.success('Extraction queued!')
      startPolling(submitted.id)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Extraction failed')
    }
  }

  const startPolling = (jobId) => {
    setPolling(true)
    pollRef.current = setInterval(async () => {
      try {
        const status = await getJobStatus(jobId)
        setJob(status)
        if (status.status === 'succeeded') {
          clearInterval(pollRef.current)
          setPolling(false)
          // Fetch result JSON
          const res = await fetch(`/api/v1/results/${jobId}`)
          const data = await res.json()
          setResult(data)
          toast.success('Extraction complete!')
        } else if (status.status === 'failed') {
          clearInterval(pollRef.current)
          setPolling(false)
          toast.error('Extraction failed')
        }
      } catch { clearInterval(pollRef.current); setPolling(false) }
    }, 2000)
  }

  const getStatusIcon = () => {
    if (!job) return null
    if (job.status === 'succeeded') return <CheckCircle size={16} color="var(--green)" />
    if (job.status === 'failed') return <AlertCircle size={16} color="var(--red)" />
    return <span className="spinner" />
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Extract</h1>
          <p>Run trained models on new documents to extract structured data</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: 24 }}>
        {/* Left: Config */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <h3 style={{ marginBottom: 16 }}>Extraction Setup</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="form-group">
                <label className="form-label">Project</label>
                <select className="input select" value={selectedProjectId} onChange={e => setSelectedProjectId(e.target.value)}>
                  <option value="">Select project...</option>
                  {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Model</label>
                <select className="input select" value={selectedModelId} onChange={e => setSelectedModelId(e.target.value)} disabled={!selectedProjectId || models.length === 0}>
                  <option value="">{models.length === 0 ? 'No trained models yet' : 'Select model...'}</option>
                  {models.map(m => <option key={m.id} value={m.id}>v{m.version} · {m.model_type} · {(m.overall_accuracy * 100).toFixed(0)}% acc {m.is_active ? '(active)' : ''}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Output Format</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  {['json', 'csv', 'excel'].map(f => (
                    <button key={f} className={`btn btn-sm ${outputFormat === f ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setOutputFormat(f)}>
                      {f.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              {/* Upload zone */}
              <div {...getRootProps()} className={`upload-zone ${isDragActive ? 'drag-active' : ''}`} style={{ padding: 24 }}>
                <input {...getInputProps()} />
                <div className="upload-icon"><Upload size={22} /></div>
                {file ? (
                  <div>
                    <div style={{ fontWeight: 600 }}>{file.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{(file.size / 1024).toFixed(0)} KB</div>
                  </div>
                ) : (
                  <>
                    <p style={{ fontWeight: 500 }}>Drop document here</p>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>PDF, JPG, PNG, TIFF</p>
                  </>
                )}
              </div>

              <button className="btn btn-primary btn-lg" onClick={handleExtract} disabled={!file || !selectedModelId || polling}>
                {polling ? <span className="spinner" /> : <Zap size={17} />}
                {polling ? 'Extracting...' : 'Extract Document'}
              </button>
            </div>
          </div>

          {/* Job status */}
          {job && (
            <div className="card">
              <h4 style={{ marginBottom: 10 }}>Job Status</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Status</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>{getStatusIcon()} <span style={{ textTransform: 'capitalize' }}>{job.status}</span></div>
                </div>
                {job.overall_confidence && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Confidence</span>
                    <ConfidenceBar value={job.overall_confidence} />
                  </div>
                )}
                {job.pages_processed > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Pages</span>
                    <span>{job.pages_processed}</span>
                  </div>
                )}

                {job.status === 'succeeded' && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    {['json', 'csv', 'excel'].map(fmt => (
                      <a key={fmt} href={getResultDownloadUrl(job.id, fmt)} download className="btn btn-secondary btn-sm">
                        <Download size={13} /> {fmt.toUpperCase()}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right: Results */}
        <div className="card" style={{ overflow: 'auto' }}>
          <h3 style={{ marginBottom: 16 }}>Extraction Results</h3>
          {!result ? (
            <div className="empty-state" style={{ padding: '40px 0' }}>
              <div className="empty-state-icon"><FileText size={26} /></div>
              <h3>No results yet</h3>
              <p>Upload a document and click Extract to see structured output.</p>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                <span className="badge badge-green">✓ {result.status}</span>
                <span className="badge badge-blue">{result.modelType}</span>
                {result.confidence && <span className="badge badge-purple">Confidence: {(result.confidence * 100).toFixed(0)}%</span>}
                <span className="badge badge-gray">{result.pages?.length || 0} pages</span>
              </div>
              {Object.entries(result.fields || {}).map(([name, data]) => (
                <FieldResult key={name} name={name} data={data} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
