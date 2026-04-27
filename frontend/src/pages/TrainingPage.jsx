import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Brain, Play, AlertTriangle, CheckCircle, XCircle, BarChart2, ChevronLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import { getProjects, getProject, startTraining, getTrainingJobs, getTrainingStreamUrl } from '../lib/api'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

export default function TrainingPage() {
  const { projectId: paramProjectId } = useParams()
  const navigate = useNavigate()
  const [projects, setProjects] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState(paramProjectId || '')
  const [project, setProject] = useState(null)
  const [jobs, setJobs] = useState([])
  const [currentJob, setCurrentJob] = useState(null)
  const [logLines, setLogLines] = useState([])
  const [streaming, setStreaming] = useState(false)
  const [modelType, setModelType] = useState('template')
  const [loading, setLoading] = useState(false)
  const logRef = useRef(null)
  const esRef = useRef(null)

  useEffect(() => { getProjects().then(setProjects).catch(() => {}) }, [])

  useEffect(() => {
    if (!selectedProjectId) return
    getProject(selectedProjectId).then(setProject).catch(() => {})
    getTrainingJobs(selectedProjectId).then(setJobs).catch(() => {})
  }, [selectedProjectId])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logLines])

  const startSSEStream = (projectId, jobId) => {
    if (esRef.current) esRef.current.close()
    const url = getTrainingStreamUrl(projectId, jobId)
    const es = new EventSource(url)
    esRef.current = es
    setStreaming(true)

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type === 'log') {
          setLogLines(prev => [...prev, data.message])
        } else if (data.type === 'complete') {
          setStreaming(false)
          es.close()
          setCurrentJob(prev => ({ ...prev, status: data.status, metrics: data.metrics || {} }))
          getTrainingJobs(projectId).then(setJobs)
          if (data.status === 'succeeded') toast.success('Training complete!')
          else toast.error('Training failed')
        }
      } catch {}
    }
    es.onerror = () => {
      setStreaming(false)
      es.close()
    }
  }

  const handleTrain = async () => {
    if (!selectedProjectId) return toast.error('Select a project')
    setLoading(true)
    setLogLines([])
    try {
      const job = await startTraining(selectedProjectId, { model_type: modelType, force: false })
      setCurrentJob(job)
      setJobs(prev => [job, ...prev])
      toast.success('Training started!')
      setTimeout(() => startSSEStream(selectedProjectId, job.id), 1000)
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to start training'
      toast.error(msg)
    } finally { setLoading(false) }
  }

  const handleForceTraining = async () => {
    if (!selectedProjectId) return
    setLoading(true)
    setLogLines([])
    try {
      const job = await startTraining(selectedProjectId, { model_type: modelType, force: true })
      setCurrentJob(job)
      setJobs(prev => [job, ...prev])
      toast.success('Training started (forced)!')
      setTimeout(() => startSSEStream(selectedProjectId, job.id), 1000)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to start training')
    } finally { setLoading(false) }
  }

  const labeledCount = project?.labeled_count || 0
  const docCount = project?.document_count || 0
  const canTrain = labeledCount >= 5
  const latestJob = jobs[0]
  const fieldMetrics = currentJob?.metrics?.field_f1 || latestJob?.metrics?.field_f1 || {}
  const chartData = Object.entries(fieldMetrics).map(([name, f1]) => ({ name, f1: Math.round(f1 * 100) }))

  const getLogClass = (line) => {
    if (line.includes('✓') || line.includes('complete') || line.includes('succeeded')) return 'log-line-success'
    if (line.includes('ERROR') || line.includes('failed')) return 'log-line-error'
    if (line.includes('Epoch')) return 'log-line-epoch'
    if (line.includes('Loading') || line.includes('Starting')) return 'log-line-info'
    return ''
  }

  const getStatusIcon = (status) => {
    if (status === 'succeeded') return <CheckCircle size={14} color="var(--green)" />
    if (status === 'failed') return <XCircle size={14} color="var(--red)" />
    if (status === 'running') return <span className="spinner" />
    return <span className="animate-pulse" style={{ width: 14, height: 14, borderRadius: '50%', background: 'var(--amber)', display: 'inline-block' }} />
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Model Training</h1>
          <p>Train extraction models from your labeled documents</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Left: Config */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <h3 style={{ marginBottom: 16 }}>Training Configuration</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div className="form-group">
                <label className="form-label">Project</label>
                <select className="input select" value={selectedProjectId} onChange={e => { setSelectedProjectId(e.target.value); setCurrentJob(null); setLogLines([]) }}>
                  <option value="">Select project...</option>
                  {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
              {project && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div style={{ padding: '10px 14px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{labeledCount}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Labeled docs</div>
                  </div>
                  <div style={{ padding: '10px 14px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', textAlign: 'center' }}>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700 }}>{project?.fields?.length || 0}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Fields</div>
                  </div>
                </div>
              )}

              {!canTrain && selectedProjectId && (
                <div style={{ padding: '10px 14px', background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 'var(--radius-sm)', display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <AlertTriangle size={16} color="var(--amber)" style={{ flexShrink: 0, marginTop: 1 }} />
                  <div style={{ fontSize: '0.8rem' }}>
                    <strong>Need {5 - labeledCount} more labeled documents</strong><br />
                    <span style={{ color: 'var(--text-secondary)' }}>Azure minimum is 5. Recommend 50+ for production accuracy.</span>
                  </div>
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Model Type</label>
                <div style={{ display: 'flex', gap: 8 }}>
                  {[
                    { value: 'template', label: 'Template', desc: 'Fast · CPU · Fixed forms' },
                    { value: 'neural', label: 'Neural (LayoutLMv3)', desc: 'Accurate · Variable layouts' },
                  ].map(mt => (
                    <label key={mt.value} style={{
                      flex: 1, padding: '10px 12px', cursor: 'pointer',
                      background: modelType === mt.value ? 'var(--accent-glow)' : 'var(--bg-secondary)',
                      border: `1px solid ${modelType === mt.value ? 'var(--accent)' : 'var(--border)'}`,
                      borderRadius: 'var(--radius-sm)', display: 'flex', flexDirection: 'column', gap: 4,
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input type="radio" value={mt.value} checked={modelType === mt.value} onChange={() => setModelType(mt.value)} />
                        <span style={{ fontWeight: 500, fontSize: '0.85rem' }}>{mt.label}</span>
                      </div>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{mt.desc}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="btn btn-primary"
                  style={{ flex: 1 }}
                  onClick={handleTrain}
                  disabled={!selectedProjectId || loading || streaming}
                >
                  {loading || streaming ? <span className="spinner" /> : <Play size={15} />}
                  {streaming ? 'Training...' : 'Train Model'}
                </button>
                {!canTrain && selectedProjectId && (
                  <button className="btn btn-secondary" onClick={handleForceTraining} disabled={loading || streaming} title="Train with fewer than 5 docs">
                    Force
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Training history */}
          {jobs.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: 12 }}>Training History</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {jobs.slice(0, 5).map(job => (
                  <div key={job.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', cursor: 'pointer' }} onClick={() => { setCurrentJob(job); setLogLines(job.log?.split('\n').filter(Boolean) || []) }}>
                    {getStatusIcon(job.status)}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: 500 }}>{job.model_type} · {job.document_count} docs</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{new Date(job.created_at).toLocaleString()}</div>
                    </div>
                    {job.metrics?.overall_f1 && (
                      <span className="badge badge-green" style={{ fontSize: '0.65rem' }}>F1: {(job.metrics.overall_f1 * 100).toFixed(1)}%</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: Log + Metrics */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Live log */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <h3>Training Log</h3>
              {streaming && <span className="badge badge-amber animate-pulse">● Live</span>}
              {currentJob?.status === 'succeeded' && <span className="badge badge-green">Complete</span>}
              {currentJob?.status === 'failed' && <span className="badge badge-red">Failed</span>}
            </div>
            <div ref={logRef} className="training-log" style={{ height: 280 }}>
              {logLines.length === 0 ? (
                <span style={{ color: 'var(--text-muted)' }}>Training log will appear here when you start training...</span>
              ) : (
                logLines.map((line, i) => (
                  <div key={i} className={getLogClass(line)}>{line}</div>
                ))
              )}
            </div>
          </div>

          {/* Field metrics */}
          {chartData.length > 0 && (
            <div className="card">
              <h3 style={{ marginBottom: 4 }}>Per-Field F1 Score</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 14 }}>
                Overall: {((currentJob?.metrics?.overall_f1 || latestJob?.metrics?.overall_f1 || 0) * 100).toFixed(1)}%
              </p>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 30 }}>
                  <XAxis type="number" domain={[0, 100]} tickFormatter={v => `${v}%`} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" width={120} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <Tooltip formatter={(v) => `${v}%`} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                  <Bar dataKey="f1" radius={[0, 4, 4, 0]}>
                    {chartData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.f1 >= 90 ? 'var(--green)' : entry.f1 >= 70 ? 'var(--amber)' : 'var(--red)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Accuracy expectations */}
          <div className="card">
            <h4 style={{ marginBottom: 10 }}>Expected Accuracy by Training Volume</h4>
            {[
              { docs: '5 docs', acc: '70–80%', color: 'var(--red)' },
              { docs: '20–30 docs', acc: '85–92%', color: 'var(--amber)' },
              { docs: '50 docs', acc: '94–97%', color: 'var(--green)' },
              { docs: '100+ docs', acc: '>97%', color: 'var(--cyan)' },
            ].map(row => (
              <div key={row.docs} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <div style={{ width: 28, height: 6, background: row.color, borderRadius: 99 }} />
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', minWidth: 80 }}>{row.docs}</span>
                <span style={{ fontWeight: 600 }}>{row.acc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
