import { useState, useEffect } from 'react'
import { CheckCircle, X, AlertCircle, RefreshCw, Check, XCircle, Edit2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { getReviewItems, getReviewStats, reviewItem } from '../lib/api'

function ReviewCard({ item, onAction }) {
  const [correcting, setCorrecting] = useState(false)
  const [correctedValue, setCorrectedValue] = useState(item.predicted_value || '')
  const [note, setNote] = useState('')

  const handleAction = async (action) => {
    try {
      await onAction(item.id, {
        action,
        corrected_value: action === 'correct' ? correctedValue : undefined,
        reviewer_note: note || undefined,
        add_to_training: false,
      })
    } catch {}
  }

  const confPct = Math.round((item.predicted_confidence || 0) * 100)
  const confColor = confPct >= 85 ? 'var(--green)' : confPct >= 70 ? 'var(--amber)' : 'var(--red)'

  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 12 }}>
        <AlertCircle size={18} color="var(--amber)" style={{ flexShrink: 0, marginTop: 2 }} />
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontWeight: 600 }}>{item.field_name}</span>
            <span className="badge badge-amber" style={{ fontSize: '0.65rem' }}>Confidence: {confPct}%</span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginLeft: 'auto' }}>
              Page {item.page_number} · {item.original_filename}
            </span>
          </div>
          <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', marginBottom: 8 }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 2 }}>Predicted Value</div>
            <div style={{ fontWeight: 500 }}>{item.predicted_value || '—'}</div>
          </div>

          {/* Confidence bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: 99, overflow: 'hidden' }}>
              <div style={{ width: `${confPct}%`, height: '100%', background: confColor, borderRadius: 99 }} />
            </div>
            <span style={{ fontSize: '0.72rem', color: confColor, fontWeight: 600 }}>{confPct}%</span>
          </div>

          {/* Correction input */}
          {correcting && (
            <div style={{ marginBottom: 10 }}>
              <input
                className="input"
                value={correctedValue}
                onChange={e => setCorrectedValue(e.target.value)}
                placeholder="Enter correct value..."
                autoFocus
              />
            </div>
          )}

          <input
            className="input"
            value={note}
            onChange={e => setNote(e.target.value)}
            placeholder="Reviewer note (optional)..."
            style={{ marginBottom: 8, fontSize: '0.8rem' }}
          />

          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-success btn-sm" onClick={() => handleAction('accept')}>
              <Check size={13} /> Accept
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => { setCorrecting(!correcting); if (!correcting) setCorrectedValue(item.predicted_value || '') }}>
              <Edit2 size={13} /> {correcting ? 'Cancel Edit' : 'Correct'}
            </button>
            {correcting && (
              <button className="btn btn-primary btn-sm" onClick={() => handleAction('correct')}>
                <CheckCircle size={13} /> Save Correction
              </button>
            )}
            <button className="btn btn-danger btn-sm" onClick={() => handleAction('reject')}>
              <XCircle size={13} /> Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function ReviewPage() {
  const [items, setItems] = useState([])
  const [stats, setStats] = useState({})
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState('pending')

  useEffect(() => {
    load()
  }, [filterStatus])

  const load = async () => {
    setLoading(true)
    try {
      const [its, st] = await Promise.all([getReviewItems(filterStatus), getReviewStats()])
      setItems(its)
      setStats(st)
    } catch { toast.error('Failed to load review queue') }
    finally { setLoading(false) }
  }

  const handleAction = async (itemId, action) => {
    try {
      await reviewItem(itemId, action)
      setItems(prev => prev.filter(i => i.id !== itemId))
      setStats(prev => ({ ...prev, pending: Math.max(0, (prev.pending || 0) - 1), [action.action + 'd']: (prev[action.action + 'd'] || 0) + 1 }))
      toast.success(`Field ${action.action}ed`)
    } catch { toast.error('Failed to update review item') }
  }

  return (
    <div className="page-content">
      <div className="page-header">
        <div className="page-header-left">
          <h1>Review Queue</h1>
          <p>Review and correct low-confidence field extractions</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary btn-sm" onClick={load}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid-4" style={{ marginBottom: 20 }}>
        {[
          { label: 'Pending', value: stats.pending || 0, badge: 'badge-amber' },
          { label: 'Accepted', value: stats.accepted || 0, badge: 'badge-green' },
          { label: 'Corrected', value: stats.corrected || 0, badge: 'badge-blue' },
          { label: 'Rejected', value: stats.rejected || 0, badge: 'badge-red' },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div>
              <div className="stat-number">{s.value}</div>
              <div className="stat-label">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {['pending', 'accepted', 'corrected', 'rejected'].map(s => (
          <button key={s} className={`btn btn-sm ${filterStatus === s ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setFilterStatus(s)}>
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="empty-state"><span className="spinner" style={{ width: 28, height: 28 }} /></div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><CheckCircle size={28} /></div>
          <h3>Queue is empty</h3>
          <p>No {filterStatus} items in the review queue.</p>
        </div>
      ) : (
        <div>
          {items.map(item => (
            <ReviewCard key={item.id} item={item} onAction={handleAction} />
          ))}
        </div>
      )}
    </div>
  )
}
