import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { 
  ZoomIn, ZoomOut, Move, Square, Type, Table2, CheckSquare, Pen,
  Plus, Trash2, Save, ChevronLeft, ChevronRight, CheckCircle, AlertCircle,
  X, RotateCcw, Tag, Eye, Pencil
} from 'lucide-react'
import toast from 'react-hot-toast'
import {
  getProject, getDocuments, getDocumentPages, getPageWords, getPageImageUrl,
  getLabels, saveLabels, addField, updateField, deleteField, setLabelStatus, getProjects, extractTableBbox
} from '../lib/api'

const FIELD_COLORS = [
  '#3B82F6','#8B5CF6','#10B981','#F59E0B','#EF4444','#F97316',
  '#06B6D4','#7C3AED','#EC4899','#14B8A6','#84CC16','#F43F5E'
]

const FIELD_TYPES = [
  { value: 'text', label: 'Text', icon: Type },
  { value: 'table', label: 'Table', icon: Table2 },
  { value: 'checkbox', label: 'Checkbox', icon: CheckSquare },
  { value: 'signature', label: 'Signature', icon: Pen },
]

const DATA_TYPES = ['string', 'number', 'date', 'time', 'integer', 'selectionMark', 'countryRegion', 'phoneNumber']

// ==================== TableCellModal ====================
function TableCellModal({ field, onConfirm, onClose }) {
  const [rowIndex, setRowIndex] = useState(0)
  const [columnName, setColumnName] = useState(field.columns?.[0]?.column_name || '')
  const columns = field.columns || []
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 380 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Assign Table Cell</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={16} /></button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="form-group">
            <label className="form-label">Column</label>
            <select className="input select" value={columnName} onChange={e => setColumnName(e.target.value)}>
              {columns.map(c => <option key={c.column_name} value={c.column_name}>{c.column_name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Row Index (0-based)</label>
            <input type="number" className="input" value={rowIndex} onChange={e => setRowIndex(parseInt(e.target.value) || 0)} min={0} />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={() => onConfirm(rowIndex, columnName)}>Assign</button>
        </div>
      </div>
    </div>
  )
}

// ==================== AddFieldModal ====================
function AddFieldModal({ project, onClose, onCreated }) {
  const [name, setName] = useState('')
  const [fieldType, setFieldType] = useState('text')
  const [dataType, setDataType] = useState('string')
  const [columns, setColumns] = useState([{ column_name: '', data_type: 'string' }])
  const [loading, setLoading] = useState(false)
  const colorIdx = (project.fields?.length || 0) % FIELD_COLORS.length

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return toast.error('Field name required')
    setLoading(true)
    try {
      const field = await addField(project.id, {
        name: name.trim().replace(/\s+/g, '_').toLowerCase(),
        field_type: fieldType,
        data_type: dataType,
        color: FIELD_COLORS[colorIdx],
        columns: fieldType === 'table' ? columns.filter(c => c.column_name.trim()).map((c, i) => ({ ...c, order: i })) : [],
      })
      toast.success(`Field "${field.name}" added`)
      onCreated(field)
      onClose()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add field')
    } finally { setLoading(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 460, maxHeight: '90vh', display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ flexShrink: 0 }}>
          <h3>Add Field</h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1, padding: '16px 20px' }}>
            <div className="form-group">
              <label className="form-label">Field Name</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g., invoice_number" autoFocus />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Lowercase, underscores only. Auto-formatted on save.</span>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Field Type</label>
                <select className="input select" value={fieldType} onChange={e => setFieldType(e.target.value)}>
                  {FIELD_TYPES.map(ft => <option key={ft.value} value={ft.value}>{ft.label}</option>)}
                </select>
              </div>
              {fieldType !== 'table' && (
                <div className="form-group" style={{ flex: 1 }}>
                  <label className="form-label">Data Type</label>
                  <select className="input select" value={dataType} onChange={e => setDataType(e.target.value)}>
                    {DATA_TYPES.map(dt => <option key={dt} value={dt}>{dt}</option>)}
                  </select>
                </div>
              )}
            </div>
            {fieldType === 'table' && (
              <div className="form-group">
                <label className="form-label">Table Columns</label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {columns.map((col, i) => (
                    <div key={i} style={{ display: 'flex', gap: 6 }}>
                      <input className="input" value={col.column_name} onChange={e => setColumns(prev => prev.map((c, ci) => ci === i ? { ...c, column_name: e.target.value } : c))} placeholder={`Column ${i + 1} name`} />
                      <select className="input select" style={{ width: 130 }} value={col.data_type} onChange={e => setColumns(prev => prev.map((c, ci) => ci === i ? { ...c, data_type: e.target.value } : c))}>
                        {DATA_TYPES.map(dt => <option key={dt} value={dt}>{dt}</option>)}
                      </select>
                      <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => setColumns(prev => prev.filter((_, ci) => ci !== i))}><X size={14} /></button>
                    </div>
                  ))}
                  <button type="button" className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => setColumns(prev => [...prev, { column_name: '', data_type: 'string' }])}>
                    <Plus size={13} /> Add Column
                  </button>
                </div>
              </div>
            )}
          </div>
          <div className="modal-footer" style={{ flexShrink: 0 }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <span className="spinner" /> : <Plus size={15} />} Add Field
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ==================== EditFieldModal ====================
function EditFieldModal({ project, field, onClose, onUpdated }) {
  const [name, setName] = useState(field.name)
  const [fieldType, setFieldType] = useState(field.field_type)
  const [dataType, setDataType] = useState(field.data_type || 'string')
  const [columns, setColumns] = useState(
    field.columns?.length
      ? field.columns.map(c => ({ column_name: c.column_name, data_type: c.data_type || 'string' }))
      : [{ column_name: '', data_type: 'string' }]
  )
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!name.trim()) return toast.error('Field name required')
    setLoading(true)
    try {
      const updated = await updateField(project.id, field.id, {
        name: name.trim().replace(/\s+/g, '_').toLowerCase(),
        field_type: fieldType,
        data_type: dataType,
        color: field.color,
        columns: fieldType === 'table'
          ? columns.filter(c => c.column_name.trim()).map((c, i) => ({ ...c, order: i }))
          : [],
      })
      toast.success(`Field "${updated.name}" updated`)
      onUpdated(updated)
      onClose()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update field')
    } finally { setLoading(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 460, maxHeight: '90vh', display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header" style={{ flexShrink: 0 }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ width: 12, height: 12, borderRadius: '50%', background: field.color, display: 'inline-block' }} />
            Edit Field
          </h3>
          <button className="btn btn-ghost btn-icon" onClick={onClose}><X size={16} /></button>
        </div>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto', flex: 1, padding: '16px 20px' }}>
            <div className="form-group">
              <label className="form-label">Field Name</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g., invoice_number" autoFocus />
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Lowercase, underscores only. Auto-formatted on save.</span>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Field Type</label>
                <select className="input select" value={fieldType} onChange={e => setFieldType(e.target.value)}>
                  {FIELD_TYPES.map(ft => <option key={ft.value} value={ft.value}>{ft.label}</option>)}
                </select>
              </div>
              {fieldType !== 'table' && (
                <div className="form-group" style={{ flex: 1 }}>
                  <label className="form-label">Data Type</label>
                  <select className="input select" value={dataType} onChange={e => setDataType(e.target.value)}>
                    {DATA_TYPES.map(dt => <option key={dt} value={dt}>{dt}</option>)}
                  </select>
                </div>
              )}
            </div>
            {fieldType === 'table' && (
              <div className="form-group">
                <label className="form-label">Table Columns</label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {columns.map((col, i) => (
                    <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', minWidth: 18, textAlign: 'right' }}>{i + 1}.</span>
                      <input className="input" value={col.column_name} onChange={e => setColumns(prev => prev.map((c, ci) => ci === i ? { ...c, column_name: e.target.value } : c))} placeholder={`Column ${i + 1} name`} />
                      <select className="input select" style={{ width: 130 }} value={col.data_type} onChange={e => setColumns(prev => prev.map((c, ci) => ci === i ? { ...c, data_type: e.target.value } : c))}>
                        {DATA_TYPES.map(dt => <option key={dt} value={dt}>{dt}</option>)}
                      </select>
                      <button type="button" className="btn btn-ghost btn-icon btn-sm" onClick={() => setColumns(prev => prev.filter((_, ci) => ci !== i))}><X size={14} /></button>
                    </div>
                  ))}
                  <button type="button" className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => setColumns(prev => [...prev, { column_name: '', data_type: 'string' }])}>
                    <Plus size={13} /> Add Column
                  </button>
                </div>
              </div>
            )}
          </div>
          <div className="modal-footer" style={{ flexShrink: 0 }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <span className="spinner" /> : <Pencil size={15} />} Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ==================== Main Label Studio ====================
export default function LabelStudio() {
  const { projectId: paramProjectId, docId: paramDocId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  // State
  const [projects, setProjects] = useState([])
  const [selectedProjectId, setSelectedProjectId] = useState(paramProjectId || '')
  const [project, setProject] = useState(null)
  const [documents, setDocuments] = useState([])
  const [selectedDocId, setSelectedDocId] = useState(paramDocId || '')
  const [pages, setPages] = useState([])
  const [currentPage, setCurrentPage] = useState(1)
  const [words, setWords] = useState([])
  const [labels, setLabels] = useState([]) // [{field_id, field_name, page_number, text, bounding_boxes, word_ids, row_index, column_name}]
  const [activeFieldId, setActiveFieldId] = useState(null)
  const [zoom, setZoom] = useState(1.0)
  const [tool, setTool] = useState('select') // select | draw
  const [showAddField, setShowAddField] = useState(false)
  const [editingField, setEditingField] = useState(null) // field object being edited
  const [continueTable, setContinueTable] = useState(true)
  const [ignoreFirstRow, setIgnoreFirstRow] = useState(true)
  const [labelsHeight, setLabelsHeight] = useState(280)
  const [tableCellPending, setTableCellPending] = useState(null) // {wordIds, text, bboxes} — used when cursor is OFF
  const [tableCursor, setTableCursor] = useState(null)           // {fieldId, row, col, overwrite} — auto-advance mode
  const [selectedWords, setSelectedWords] = useState(new Set())
  const [saving, setSaving] = useState(false)
  const [imageLoaded, setImageLoaded] = useState(false)
  
  const [drawingBox, setDrawingBox] = useState(null)
  const [selectionBox, setSelectionBox] = useState(null)  // drag-select rectangle

  const canvasRef = useRef(null)
  const containerRef = useRef(null)
  const isDragging = useRef(false)
  const hasDragged = useRef(false)    // true once mouse moves > threshold after mousedown
  const tableCursorRef = useRef(null) // always-current mirror of tableCursor state
  const autoZoomDone = useRef({})

  // Load projects
  useEffect(() => { getProjects().then(setProjects).catch(() => {}) }, [])

  // Load project details when selected
  useEffect(() => {
    if (!selectedProjectId) return
    getProject(selectedProjectId).then(setProject).catch(() => {})
    getDocuments(selectedProjectId).then(setDocuments).catch(() => {})
  }, [selectedProjectId])

  // Load document pages
  useEffect(() => {
    if (!selectedProjectId || !selectedDocId) return
    getDocumentPages(selectedProjectId, selectedDocId).then(setPages).catch(() => {})
    loadAllLabels()
    setCurrentPage(1)
    setImageLoaded(false)
  }, [selectedProjectId, selectedDocId])

  // Load words for current page
  useEffect(() => {
    if (!selectedProjectId || !selectedDocId || !pages.length) return
    getPageWords(selectedProjectId, selectedDocId, currentPage).then(setWords).catch(() => {})
    setSelectedWords(new Set())
    setImageLoaded(false)
  }, [currentPage, selectedDocId, pages.length])

  const loadAllLabels = async () => {
    try {
      const data = await getLabels(selectedProjectId, selectedDocId)
      setLabels(data)
    } catch {}
  }

  const activeField = project?.fields?.find(f => f.id === activeFieldId) || null
  const currentPageLabels = labels.filter(l => l.page_number === currentPage)
  const currentPage_ = pages.find(p => p.page_number === currentPage)
  const pageWidth = currentPage_?.width || 612
  const pageHeight = currentPage_?.height || 792

  // Keep ref in sync with cursor state so memoized callbacks always see latest value
  useEffect(() => { tableCursorRef.current = tableCursor }, [tableCursor])

  // Cursor derived values (computed here so JSX stays simple)
  const activeFieldCols = (activeField?.columns || []).slice().sort((a, b) => a.order - b.order)
  const cursorActive = !!(tableCursor && activeField && tableCursor.fieldId === activeField.id)
  const currentColName = cursorActive ? activeFieldCols[tableCursor.col]?.column_name : null

  // Auto-zoom to fit container
  useEffect(() => {
    if (imageLoaded && containerRef.current && pageWidth && pageHeight && selectedDocId) {
      if (!autoZoomDone.current[`${selectedDocId}-${currentPage}`]) {
        autoZoomDone.current[`${selectedDocId}-${currentPage}`] = true;
        const containerW = containerRef.current.clientWidth - 40;
        const containerH = containerRef.current.clientHeight - 40;
        // canvas base dims are roughly page * (200/72) = page * 2.77
        const baseW = pageWidth * (200 / 72);
        const baseH = pageHeight * (200 / 72);
        const scaleW = containerW / baseW;
        const scaleH = containerH / baseH;
        let bestFit = Math.min(scaleW, scaleH);
        if (bestFit < 0.1) bestFit = 0.1;
        if (bestFit > 2.5) bestFit = 2.5;
        setZoom(bestFit);
      }
    }
  }, [imageLoaded, pageWidth, pageHeight, selectedDocId, currentPage]);

  // Canvas dimensions
  const canvasW = Math.round(pageWidth * zoom * (200 / 72))
  const canvasH = Math.round(pageHeight * zoom * (200 / 72))
  const scale = canvasW / pageWidth  // pixels per point

  // Scale factor from PDF points to canvas pixels
  const toCanvas = (v) => v * scale
  const fromCanvas = (v) => v / scale

  const handleMouseDown = (e) => {
    if (!activeField) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (tool === 'drawTable' && activeField.field_type === 'table') {
      e.preventDefault();
      isDragging.current = true;
      hasDragged.current = false;
      setDrawingBox({ x0: x, y0: y, x1: x, y1: y });
    } else if (tool === 'select' && activeField.field_type === 'table') {
      // Start drag-select for manual multi-word table labeling
      isDragging.current = true;
      hasDragged.current = false;
      setSelectionBox({ x0: x, y0: y, x1: x, y1: y });
    }
  }

  const handleMouseMove = (e) => {
    if (!isDragging.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, canvasW));
    const y = Math.max(0, Math.min(e.clientY - rect.top, canvasH));

    if (tool === 'drawTable' && drawingBox) {
      hasDragged.current = true;
      setDrawingBox(prev => ({ ...prev, x1: x, y1: y }));
    } else if (tool === 'select' && selectionBox) {
      const dx = Math.abs(x - selectionBox.x0);
      const dy = Math.abs(y - selectionBox.y0);
      if (dx > 5 || dy > 5) hasDragged.current = true; // Threshold to tell drag from click
      if (hasDragged.current) setSelectionBox(prev => ({ ...prev, x1: x, y1: y }));
    }
  }

  const handleMouseUp = async () => {
    if (!isDragging.current) return;
    isDragging.current = false;
    
    if (tool === 'drawTable' && drawingBox && activeField) {
      // Box must be at least 10x10 pixels
      if (Math.abs(drawingBox.x1 - drawingBox.x0) > 10 && Math.abs(drawingBox.y1 - drawingBox.y0) > 10) {
        const x0 = fromCanvas(Math.min(drawingBox.x0, drawingBox.x1));
        const y0 = fromCanvas(Math.min(drawingBox.y0, drawingBox.y1));
        const x1 = fromCanvas(Math.max(drawingBox.x0, drawingBox.x1));
        const y1 = fromCanvas(Math.max(drawingBox.y0, drawingBox.y1));
        
        const loadingToast = toast.loading('Extracting table rows/columns...');
        try {
          const res = await extractTableBbox(selectedProjectId, selectedDocId, {
            page_number: currentPage,
            bbox: [x0, y0, x1, y1]
          });
          
          if (res.cells && res.cells.length > 0) {
            let processedCells = res.cells;
            if (ignoreFirstRow) {
               processedCells = processedCells
                 .filter(c => c.row_index > 0)
                 .map(c => ({ ...c, row_index: c.row_index - 1 }));
            }

            let rowOffset = 0;
            if (continueTable) {
               // max row existing
               const fieldLabels = labels.filter(l => l.field_id === activeField.id && l.row_index != null);
               if (fieldLabels.length > 0) {
                 const maxRow = Math.max(...fieldLabels.map(l => l.row_index));
                 rowOffset = maxRow + 1;
               }
            }

            // Map cells to labels
            let newLabels = processedCells.map(c => {
               const columns = activeField.columns || [];
               let colName = `Column${c.column_index + 1}`;
               if (columns.length > c.column_index) {
                 colName = columns[c.column_index].column_name;
               }
               return {
                 field_id: activeField.id,
                 field_name: activeField.name,
                 page_number: currentPage,
                 text: c.text,
                 bounding_boxes: c.bounding_boxes,
                 word_ids: c.word_ids,
                 row_index: c.row_index + rowOffset,
                 column_name: colName,
               };
            }).filter(l => l.word_ids && l.word_ids.length > 0);
            
            if (newLabels.length > 0) {
               setLabels(prev => [...prev, ...newLabels]);
               toast.success(`Extracted ${newLabels.length} table cells`, { id: loadingToast });
               setTool('select'); // Revert tool
            } else {
               toast.error('No words found in the detected table grid', { id: loadingToast });
            }
          } else {
            toast.error('Could not detect table structure in that area', { id: loadingToast });
          }
        } catch (err) {
          toast.error('Failed to extract table structure', { id: loadingToast });
        }
      }
      setDrawingBox(null);
    }

    // ── Drag-select mode: collect words in selection rect ──
    if (tool === 'select' && selectionBox && activeField?.field_type === 'table') {
      if (hasDragged.current) {
        const sx0 = fromCanvas(Math.min(selectionBox.x0, selectionBox.x1));
        const sy0 = fromCanvas(Math.min(selectionBox.y0, selectionBox.y1));
        const sx1 = fromCanvas(Math.max(selectionBox.x0, selectionBox.x1));
        const sy1 = fromCanvas(Math.max(selectionBox.y0, selectionBox.y1));

        const captured = words.filter(w => {
          // Word overlaps selection rectangle
          return w.x0 < sx1 && w.x1 > sx0 && w.y0 < sy1 && w.y1 > sy0;
        });

        if (captured.length > 0) {
          const sorted = captured.sort((a, b) => (a.y0 - b.y0) || (a.x0 - b.x0));
          const wordIds = sorted.map(w => w.id)
          const text = sorted.map(w => w.text).join(' ')
          const bboxes = sorted.map(w => [w.x0, w.y0, w.x1, w.y1])
          // Route through cursor if active, otherwise show modal
          if (!assignWithCursor(wordIds, text, bboxes)) {
            setTableCellPending({ wordIds, text, bboxes })
          }
        } else {
          toast('No words in selected area', { icon: '⚠️' });
        }
      }
      // Defer resetting hasDragged so the immediate onClick event can still see it
      setTimeout(() => { hasDragged.current = false }, 50);
      setSelectionBox(null);
    }
  }

  // ── assignWithCursor: assign words to cursor position, then auto-advance ──
  // Uses ref so it always sees latest cursor even from memoized callbacks
  const assignWithCursor = (wordIds, text, bboxes) => {
    const cursor = tableCursorRef.current
    if (!cursor || !activeField) return false
    const cols = (activeField.columns || []).slice().sort((a, b) => a.order - b.order)
    if (cols.length === 0) return false
    const colName = cols[cursor.col]?.column_name
    if (!colName) return false

    const entry = {
      field_id: activeField.id,
      field_name: activeField.name,
      page_number: currentPage,
      text,
      bounding_boxes: bboxes,
      word_ids: wordIds,
      row_index: cursor.row,
      column_name: colName,
    }

    setLabels(prev => {
      const filtered = prev.filter(l =>
        !(l.field_id === activeField.id && l.row_index === cursor.row && l.column_name === colName)
      )
      return [...filtered, entry]
    })

    // Advance or stop
    if (!cursor.overwrite) {
      const nextCol = cursor.col + 1
      if (nextCol < cols.length) {
        const newCursor = { ...cursor, col: nextCol }
        tableCursorRef.current = newCursor
        setTableCursor(newCursor)
        toast.success(`✓ ${colName}  →  ${cols[nextCol].column_name}`, { duration: 900, icon: '▶' })
      } else {
        const newCursor = { ...cursor, row: cursor.row + 1, col: 0 }
        tableCursorRef.current = newCursor
        setTableCursor(newCursor)
        toast.success(`Row ${cursor.row + 1} done  —  Row ${cursor.row + 2} start`, { duration: 1000, icon: '↩' })
      }
    } else {
      tableCursorRef.current = null
      setTableCursor(null)
      toast.success('Cell updated', { duration: 800 })
    }
    return true
  }

  const handleWordClick = (word, e) => {
    if (!activeFieldId || !activeField) return
    // Ignore click if it was the end of a drag-select gesture
    if (hasDragged.current) return
    const wid = word.id

    if (activeField.field_type === 'table') {
      // Read from ref so we always get the current cursor, not a stale closure value
      if (tableCursorRef.current) {
        assignWithCursor([wid], word.text, [[word.x0, word.y0, word.x1, word.y1]])
        return
      }
      setTableCellPending({
        wordIds: [wid],
        text: word.text,
        bboxes: [[word.x0, word.y0, word.x1, word.y1]],
      })
      return
    }

    // For text fields: shift-click = multi-select
    if (e.shiftKey) {
      setSelectedWords(prev => {
        const next = new Set(prev)
        if (next.has(wid)) next.delete(wid)
        else next.add(wid)
        return next
      })
    } else {
      const field = activeField
      const labelEntry = {
        field_id: field.id,
        field_name: field.name,
        page_number: currentPage,
        text: word.text,
        bounding_boxes: [[word.x0, word.y0, word.x1, word.y1]],
        word_ids: [wid],
        row_index: null,
        column_name: null,
      }
      setLabels(prev => [...prev.filter(l => !(l.field_id === field.id && l.page_number === currentPage && l.word_ids.includes(wid))), labelEntry])
      toast.success(`"${word.text}" → ${field.name}`, { duration: 1500 })
    }
  }

  const handleConfirmMultiSelect = () => {
    if (!activeField || selectedWords.size === 0) return
    const selected = words.filter(w => selectedWords.has(w.id))
    const field = activeField
    // Remove existing label for this field on this page (non-table)
    setLabels(prev => {
      const filtered = prev.filter(l => !(l.field_id === field.id && l.page_number === currentPage))
      const newLabel = {
        field_id: field.id,
        field_name: field.name,
        page_number: currentPage,
        text: selected.sort((a, b) => (a.y0 - b.y0) || (a.x0 - b.x0)).map(w => w.text).join(' '),
        bounding_boxes: selected.map(w => [w.x0, w.y0, w.x1, w.y1]),
        word_ids: selected.map(w => w.id),
        row_index: null,
        column_name: null,
      }
      return [...filtered, newLabel]
    })
    setSelectedWords(new Set())
    toast.success(`${selected.length} words → ${field.name}`)
  }

  const handleTableCellConfirm = (rowIndex, columnName) => {
    if (!tableCellPending || !activeField) return
    const field = activeField
    const newLabel = {
      field_id: field.id,
      field_name: field.name,
      page_number: currentPage,
      text: tableCellPending.text,
      bounding_boxes: tableCellPending.bboxes,
      word_ids: tableCellPending.wordIds,
      row_index: rowIndex,
      column_name: columnName,
    }
    setLabels(prev => [...prev, newLabel])
    setTableCellPending(null)
    toast.success(`Cell (R${rowIndex + 1}, ${columnName}) labeled`)
  }

  const handleDeleteLabel = (labelIdx) => {
    setLabels(prev => prev.filter((_, i) => i !== labelIdx))
  }

  const handleSave = async (markComplete = false) => {
    if (!selectedDocId) return
    setSaving(true)
    try {
      // Group labels by field_id
      const byField = {}
      for (const lbl of labels) {
        if (!byField[lbl.field_id]) byField[lbl.field_id] = []
        byField[lbl.field_id].push({
          page: lbl.page_number,
          text: lbl.text || '',
          bounding_boxes: lbl.bounding_boxes || [],
          word_ids: lbl.word_ids || [],
          row_index: lbl.row_index,
          column_name: lbl.column_name,
        })
      }
      const labelsPayload = Object.entries(byField).map(([fieldId, values]) => ({ field_id: fieldId, values }))
      await saveLabels(selectedProjectId, selectedDocId, { labels: labelsPayload, mark_complete: markComplete })
      toast.success(markComplete ? 'Saved & marked complete!' : 'Labels saved!')
    } catch (err) {
      toast.error('Failed to save labels')
    } finally { setSaving(false) }
  }

  const imageUrl = selectedDocId ? getPageImageUrl(selectedProjectId, selectedDocId, currentPage) : null
  const completedPages = Array.from(new Set(labels.map(l => l.page_number)))

  const getWordLabelInfo = (wordId) => {
    for (const lbl of currentPageLabels) {
      if (lbl.word_ids.includes(wordId)) {
        const field = project?.fields?.find(f => f.id === lbl.field_id)
        return { field, lbl }
      }
    }
    return null
  }

  const handleDeleteField = async (fieldId, e) => {
    e.stopPropagation()
    if (!window.confirm('Delete this field? All associated labels will be removed.')) return
    try {
      await deleteField(selectedProjectId, fieldId)
      setProject(prev => ({ ...prev, fields: prev.fields.filter(f => f.id !== fieldId) }))
      if (activeFieldId === fieldId) setActiveFieldId(null)
      setLabels(prev => prev.filter(l => l.field_id !== fieldId))
      toast.success('Field deleted')
    } catch {
      toast.error('Failed to delete field')
    }
  }

  const handleFieldUpdated = (updatedField) => {
    setProject(prev => ({
      ...prev,
      fields: prev.fields.map(f => f.id === updatedField.id ? updatedField : f)
    }))
  }

  const handleDragDivider = (e) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = labelsHeight;
    const onMouseMove = (moveEvent) => {
      const deltaY = moveEvent.clientY - startY;
      // dragging down -> deltaY positive -> height decreases
      setLabelsHeight(Math.max(100, Math.min(800, startHeight - deltaY)));
    };
    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.cursor = 'default';
    };
    document.body.style.cursor = 'row-resize';
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Top toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 14px', borderBottom: '1px solid var(--border)', background: 'var(--bg-sidebar)', flexShrink: 0, flexWrap: 'wrap' }}>
        {/* Project/Doc selectors */}
        <select className="input select" value={selectedProjectId} onChange={e => { setSelectedProjectId(e.target.value); setSelectedDocId('') }} style={{ width: 180, padding: '5px 10px', fontSize: '0.8rem' }}>
          <option value="">Select project...</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <select className="input select" value={selectedDocId} onChange={e => setSelectedDocId(e.target.value)} style={{ width: 220, padding: '5px 10px', fontSize: '0.8rem' }} disabled={!selectedProjectId}>
          <option value="">Select document...</option>
          {documents.map(d => <option key={d.id} value={d.id} disabled={d.ocr_status !== 'complete'}>{d.original_filename} {d.ocr_status !== 'complete' ? '(OCR pending)' : ''}</option>)}
        </select>

        <div className="separator-v" style={{ height: 24, margin: '0 4px' }} />

        {/* Toolbar modes */}
        <div style={{ display: 'flex', gap: 4 }}>
          <button className={`btn btn-sm ${tool === 'select' ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setTool('select')}>
            <Move size={14} /> Select
          </button>
          <button 
            className={`btn btn-sm ${tool === 'drawTable' ? 'btn-primary' : 'btn-ghost'}`} 
            onClick={() => setTool('drawTable')}
            disabled={!activeField || activeField.field_type !== 'table'}
            title={activeField?.field_type === 'table' ? "Draw box to auto-extract table" : "Select a table field first"}
          >
            <Square size={14} /> Draw Auto-Table
          </button>
        </div>

        <div className="separator-v" style={{ height: 24, margin: '0 4px' }} />

        {/* Zoom controls */}
        <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setZoom(z => Math.max(0.1, z - 0.1))}><ZoomOut size={15} /></button>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', minWidth: 42, textAlign: 'center' }}>{Math.round(zoom * 100)}%</span>
        <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setZoom(z => Math.min(2.5, z + 0.1))}><ZoomIn size={15} /></button>

        <div className="separator-v" style={{ height: 24, margin: '0 4px' }} />

        {/* Page navigation */}
        <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage <= 1}><ChevronLeft size={15} /></button>
        <span style={{ fontSize: '0.8rem' }}>Page {currentPage} / {pages.length || '?'}</span>
        <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setCurrentPage(p => Math.min(pages.length, p + 1))} disabled={currentPage >= pages.length}><ChevronRight size={15} /></button>

        {/* Multi-select confirm */}
        {selectedWords.size > 0 && activeField && (
          <>
            <div className="separator-v" style={{ height: 24, margin: '0 4px' }} />
            <button className="btn btn-primary btn-sm" onClick={handleConfirmMultiSelect}>
              <CheckCircle size={13} /> Assign {selectedWords.size} words → {activeField.name}
            </button>
            <button className="btn btn-ghost btn-sm" onClick={() => setSelectedWords(new Set())}><X size={13} /></button>
          </>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm" onClick={() => handleSave(false)} disabled={saving || !selectedDocId}>
            {saving ? <span className="spinner" style={{ width: 14, height: 14 }} /> : <Save size={13} />} Save
          </button>
          <button className="btn btn-success btn-sm" onClick={() => handleSave(true)} disabled={saving || !selectedDocId}>
            <CheckCircle size={13} /> Save & Complete
          </button>
        </div>
      </div>

      {/* Main studio area */}
      <div className="studio-layout" style={{ flex: 1 }}>
        {/* Left: Page thumbnails */}
        <div className="studio-thumbnails">
          {pages.map(pg => (
            <div
              key={pg.page_number}
              className={`thumbnail-item ${currentPage === pg.page_number ? 'active' : ''}`}
              onClick={() => setCurrentPage(pg.page_number)}
            >
              <div className="thumbnail-img" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-card)' }}>
                <img
                  src={selectedDocId ? getPageImageUrl(selectedProjectId, selectedDocId, pg.page_number) : ''}
                  alt={`Page ${pg.page_number}`}
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                  onError={(e) => { e.target.style.display = 'none' }}
                />
              </div>
              <div className="thumbnail-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                <span>{pg.page_number}</span>
                {completedPages.includes(pg.page_number) && <Tag size={9} color="var(--green)" />}
              </div>
            </div>
          ))}
        </div>

        {/* Center: Canvas */}
        <div className="studio-canvas-area">
          {!selectedDocId ? (
            <div className="empty-state" style={{ flex: 1 }}>
              <div className="empty-state-icon"><Eye size={28} /></div>
              <h3>Select a document</h3>
              <p>Choose a project and document above to begin labeling.</p>
            </div>
          ) : (
            <div ref={containerRef} style={{ flex: 1, overflow: 'auto', position: 'relative', padding: 20, display: 'flex', justifyContent: 'center', alignItems: 'flex-start' }}>
              <div 
                ref={canvasRef} 
                style={{ position: 'relative', width: canvasW, height: canvasH, flexShrink: 0, cursor: tool === 'drawTable' ? 'crosshair' : 'default' }}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
              >
                {/* PDF page image */}
                {imageUrl && (
                  <img
                    src={imageUrl}
                    alt={`Page ${currentPage}`}
                    style={{ position: 'absolute', top: 0, left: 0, width: canvasW, height: canvasH, display: 'block' }}
                    onLoad={() => setImageLoaded(true)}
                  />
                )}

                {/* OCR word overlays */}
                {imageLoaded && words.map(word => {
                  const labelInfo = getWordLabelInfo(word.id)
                  const isSelected = selectedWords.has(word.id)
                  const fieldColor = labelInfo?.field?.color || (isSelected ? 'var(--accent)' : 'transparent')
                  const isLabeled = !!labelInfo

                  return (
                    <div
                      key={word.id}
                      onClick={(e) => handleWordClick(word, e)}
                      style={{
                        position: 'absolute',
                        left: toCanvas(word.x0),
                        top: toCanvas(word.y0),
                        width: toCanvas(word.x1 - word.x0),
                        height: toCanvas(word.y1 - word.y0),
                        border: `2px solid ${isLabeled ? fieldColor : isSelected ? 'var(--accent)' : 'transparent'}`,
                        background: isLabeled ? `${fieldColor}22` : isSelected ? 'rgba(59,130,246,0.2)' : 'transparent',
                        cursor: activeFieldId ? 'crosshair' : 'default',
                        borderRadius: 2,
                        transition: 'all 0.1s',
                        zIndex: 2,
                        boxSizing: 'border-box',
                      }}
                      title={`"${word.text}" ${isLabeled ? `→ ${labelInfo.field?.name}` : ''}`}
                    >
                      {isLabeled && (
                        <div style={{
                          position: 'absolute',
                          top: -18,
                          left: 0,
                          background: fieldColor,
                          color: 'white',
                          fontSize: 9,
                          padding: '1px 5px',
                          borderRadius: 3,
                          whiteSpace: 'nowrap',
                          fontWeight: 600,
                          zIndex: 5,
                          pointerEvents: 'none',
                        }}>
                          {labelInfo.field?.name}{labelInfo.lbl.column_name ? `.${labelInfo.lbl.column_name}` : ''}
                          {labelInfo.lbl.row_index != null ? `[${labelInfo.lbl.row_index}]` : ''}
                        </div>
                      )}
                    </div>
                  )
                })}

                {/* Drawing Box overlay (drawTable tool — TATR auto extract) */}
                {drawingBox && (
                  <div style={{
                    position: 'absolute',
                    left: Math.min(drawingBox.x0, drawingBox.x1),
                    top: Math.min(drawingBox.y0, drawingBox.y1),
                    width: Math.abs(drawingBox.x1 - drawingBox.x0),
                    height: Math.abs(drawingBox.y1 - drawingBox.y0),
                    border: '2px dashed var(--accent)',
                    backgroundColor: 'rgba(59,130,246,0.1)',
                    zIndex: 10,
                    pointerEvents: 'none'
                  }} />
                )}

                {/* Drag-select overlay (select tool on table field — multi-word) */}
                {selectionBox && hasDragged.current && (
                  <div style={{
                    position: 'absolute',
                    left: Math.min(selectionBox.x0, selectionBox.x1),
                    top: Math.min(selectionBox.y0, selectionBox.y1),
                    width: Math.abs(selectionBox.x1 - selectionBox.x0),
                    height: Math.abs(selectionBox.y1 - selectionBox.y0),
                    border: '2px dashed #10B981',
                    backgroundColor: 'rgba(16,185,129,0.08)',
                    borderRadius: 3,
                    zIndex: 10,
                    pointerEvents: 'none'
                  }} />
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right: Field panel */}
        <div className="studio-field-panel">
          <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h4 style={{ fontWeight: 600 }}>Fields</h4>
            <button className="btn btn-primary btn-sm" onClick={() => setShowAddField(true)} disabled={!selectedProjectId}>
              <Plus size={13} /> Add
            </button>
          </div>
          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '8px' }}>
            {!project?.fields?.length ? (
              <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: '0.8rem', textAlign: 'center' }}>
                No fields defined.<br />Add fields to start labeling.
              </div>
            ) : project.fields.map(field => {
              const fieldLabels = labels.filter(l => l.field_id === field.id)
              const hasLabels = fieldLabels.length > 0
              return (
                <div
                  key={field.id}
                  className={`field-item ${activeFieldId === field.id ? 'active' : ''}`}
                  onClick={() => setActiveFieldId(activeFieldId === field.id ? null : field.id)}
                >
                  <div className="field-color-dot" style={{ background: field.color }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span className="truncate">{field.name}</span>
                      {hasLabels && <CheckCircle size={11} color="var(--green)" />}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{field.field_type} · {field.data_type}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span className={`badge ${field.field_type === 'table' ? 'badge-purple' : field.field_type === 'checkbox' ? 'badge-amber' : 'badge-blue'}`} style={{ fontSize: '0.6rem' }}>
                      {field.field_type.substring(0, 3).toUpperCase()}
                    </span>
                    <button
                      className="btn btn-ghost btn-icon"
                      style={{ width: 22, height: 22, padding: 0 }}
                      onClick={(e) => { e.stopPropagation(); setEditingField(field) }}
                      title="Edit Field"
                    >
                      <Pencil size={12} color="var(--text-secondary)" />
                    </button>
                    <button 
                      className="btn btn-ghost btn-icon" 
                      style={{ width: 22, height: 22, padding: 0 }}
                      onClick={(e) => handleDeleteField(field.id, e)}
                      title="Delete Field"
                    >
                      <Trash2 size={13} color="var(--red)" />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>



          {/* Labels for current page */}
          {currentPageLabels.length > 0 && (() => {
            // Group labels by field
            const labelsByField = {}
            for (const lbl of currentPageLabels) {
              if (!labelsByField[lbl.field_id]) labelsByField[lbl.field_id] = []
              labelsByField[lbl.field_id].push(lbl)
            }
            const tableFields = project?.fields?.filter(f => f.field_type === 'table' && labelsByField[f.id]) || []
            const textFields = project?.fields?.filter(f => f.field_type !== 'table' && labelsByField[f.id]) || []

            return (
              <div style={{ display: 'flex', flexDirection: 'column', height: labelsHeight, flexShrink: 0, minHeight: 0, borderTop: '1px solid var(--border)' }}>
                {/* Divider handle */}
                <div
                  onMouseDown={handleDragDivider}
                  style={{ height: 8, background: 'var(--bg-card-hover)', cursor: 'row-resize', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background 0.2s' }}
                  onMouseEnter={e => e.target.style.background = 'var(--border)'}
                  onMouseLeave={e => e.target.style.background = 'var(--bg-card-hover)'}
                >
                  <div style={{ width: 30, height: 2, background: 'var(--text-muted)', borderRadius: 2 }} />
                </div>

                <div style={{ padding: '8px 14px 4px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <h4 style={{ fontWeight: 500, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    Page {currentPage} Labels ({currentPageLabels.length})
                  </h4>
                </div>

                <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '0 10px 10px' }}>

                  {/* ── Table fields → grid view ── */}
                  {tableFields.map(field => {
                    const fieldLbls = labelsByField[field.id] || []
                    const colDefs = (field.columns || []).slice().sort((a, b) => a.order - b.order)
                    const colNames = colDefs.map(c => c.column_name)

                    // Build row map: rowIndex → { colName → lbl }
                    const rowMap = {}
                    for (const lbl of fieldLbls) {
                      const r = lbl.row_index ?? '__nr'
                      if (!rowMap[r]) rowMap[r] = {}
                      rowMap[r][lbl.column_name] = lbl
                    }
                    const sortedRows = Object.keys(rowMap).sort((a, b) => Number(a) - Number(b))

                    return (
                      <div key={field.id} style={{ marginBottom: 12 }}>
                        {/* Field header */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: field.color }} />
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: field.color }}>{field.name}</span>
                          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{sortedRows.length} rows · {colNames.length} cols</span>
                        </div>

                        {/* Table grid */}
                        <div style={{ overflowX: 'auto', borderRadius: 6, border: `1px solid ${field.color}44` }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.7rem', tableLayout: 'auto' }}>
                            <thead>
                              <tr style={{ background: `${field.color}22` }}>
                                <th style={{ padding: '4px 6px', borderBottom: `1px solid ${field.color}44`, color: 'var(--text-muted)', fontWeight: 600, whiteSpace: 'nowrap', textAlign: 'center', minWidth: 30 }}>#</th>
                                {colNames.map(cn => (
                                  <th key={cn} style={{ padding: '4px 8px', borderBottom: `1px solid ${field.color}44`, color: field.color, fontWeight: 600, whiteSpace: 'nowrap', textAlign: 'left' }}>
                                    {cn}
                                  </th>
                                ))}
                                <th style={{ padding: '4px 6px', borderBottom: `1px solid ${field.color}44`, width: 24 }} />
                              </tr>
                            </thead>
                            <tbody>
                              {sortedRows.map((rowKey, ri) => (
                                <tr
                                  key={rowKey}
                                  style={{ background: ri % 2 === 0 ? 'transparent' : 'var(--bg-secondary)', transition: 'background 0.1s' }}
                                >
                                  <td style={{ padding: '3px 6px', color: 'var(--text-muted)', textAlign: 'center', fontWeight: 500 }}>
                                    {rowKey === '__nr' ? '—' : Number(rowKey) + 1}
                                  </td>
                                  {colNames.map(cn => {
                                    const cell = rowMap[rowKey][cn]
                                    const isEditTarget = tableCursor?.fieldId === field.id &&
                                      tableCursor?.row === Number(rowKey) &&
                                      colDefs[tableCursor?.col]?.column_name === cn
                                    return (
                                      <td
                                        key={cn}
                                        title={cell ? `${cell.text} (click to edit)` : 'Click to label this cell'}
                                        onClick={() => {
                                          const colIdx = colNames.indexOf(cn)
                                          setActiveFieldId(field.id)
                                          setTableCursor({ fieldId: field.id, row: Number(rowKey), col: colIdx, overwrite: true })
                                          toast(`Click or drag words → ${cn} [Row ${Number(rowKey)+1}]`, { icon: '✏️', duration: 2000 })
                                        }}
                                        style={{
                                          padding: '3px 8px',
                                          maxWidth: 140,
                                          overflow: 'hidden',
                                          textOverflow: 'ellipsis',
                                          whiteSpace: 'nowrap',
                                          cursor: 'pointer',
                                          color: cell ? 'var(--text-primary)' : 'var(--text-muted)',
                                          background: isEditTarget ? `${field.color}33` : 'transparent',
                                          outline: isEditTarget ? `2px solid ${field.color}` : 'none',
                                          borderRadius: isEditTarget ? 3 : 0,
                                          transition: 'background 0.15s',
                                        }}
                                      >
                                        {cell?.text || <span style={{ opacity: 0.35 }}>—</span>}
                                      </td>
                                    )
                                  })}
                                  <td style={{ padding: '2px 4px', textAlign: 'right' }}>
                                    <button
                                      className="btn btn-ghost btn-icon"
                                      style={{ width: 18, height: 18, padding: 0, opacity: 0.5 }}
                                      title="Delete row"
                                      onClick={() => {
                                        const rowLbls = Object.values(rowMap[rowKey])
                                        setLabels(prev => prev.filter(l => !rowLbls.some(r => r === l)))
                                      }}
                                    >
                                      <X size={10} />
                                    </button>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {sortedRows.length === 0 && (
                            <div style={{ padding: '10px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.72rem' }}>No rows labeled yet</div>
                          )}
                        </div>
                      </div>
                    )
                  })}

                  {/* ── Non-table fields → compact list ── */}
                  {textFields.length > 0 && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: tableFields.length > 0 ? 8 : 0 }}>
                      {textFields.map(field => {
                        const fieldLbls = labelsByField[field.id] || []
                        return fieldLbls.map((lbl, i) => (
                          <div key={`${field.id}-${i}`} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 6px', background: 'var(--bg-secondary)', borderRadius: 4 }}>
                            <div style={{ width: 6, height: 6, borderRadius: '50%', background: field.color, flexShrink: 0 }} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: '0.7rem', fontWeight: 500, color: field.color }}>{lbl.field_name}</div>
                              <div style={{ fontSize: '0.8rem' }} className="truncate">{lbl.text || '—'}</div>
                            </div>
                            <button className="btn btn-ghost btn-icon" style={{ width: 20, height: 20, padding: 0, color: 'var(--text-muted)' }} onClick={() => handleDeleteLabel(labels.indexOf(lbl))}>
                              <X size={11} />
                            </button>
                          </div>
                        ))
                      })}
                    </div>
                  )}
                </div>
              </div>
            )
          })()}

          {/* Active field helper + Cursor controls */}
          {activeField && (
            <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border)', background: `${activeField.color}11`, flexShrink: 0 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: activeField.color, marginBottom: 6 }}>
                ● ACTIVE: {activeField.name}
              </div>

              {activeField.field_type === 'table' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>

                  {/* Cursor status pill */}
                  {cursorActive ? (
                    <div style={{ background: `${activeField.color}22`, border: `1px solid ${activeField.color}55`, borderRadius: 6, padding: '6px 10px' }}>
                      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginBottom: 2 }}>Labeling cursor</div>
                      <div style={{ fontWeight: 700, fontSize: '0.82rem', color: activeField.color }}>
                        Row {tableCursor.row + 1}  ›  {currentColName || '—'}
                      </div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 2 }}>
                        Col {tableCursor.col + 1} / {activeFieldCols.length}  ·  click or drag words to assign
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                      Click words to label individually · or start cursor mode to go column-by-column
                    </div>
                  )}

                  {/* Cursor action buttons */}
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    {!cursorActive ? (
                      <button
                        className="btn btn-primary btn-sm"
                        style={{ fontSize: '0.72rem' }}
                        onClick={() => setTableCursor({ fieldId: activeField.id, row: 0, col: 0, overwrite: false })}
                      >
                        ▶ Start cursor (Row 1)
                      </button>
                    ) : (
                      <>
                        <button
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: '0.72rem' }}
                          title="Skip this cell without labeling"
                          onClick={() => {
                            const nextCol = tableCursor.col + 1
                            if (nextCol < activeFieldCols.length) setTableCursor(prev => ({ ...prev, col: nextCol }))
                            else setTableCursor(prev => ({ ...prev, row: prev.row + 1, col: 0 }))
                          }}
                        >
                          Skip →
                        </button>
                        <button
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: '0.72rem' }}
                          title="Go back one cell"
                          onClick={() => {
                            if (tableCursor.col > 0) setTableCursor(prev => ({ ...prev, col: prev.col - 1 }))
                            else if (tableCursor.row > 0) setTableCursor(prev => ({ ...prev, row: prev.row - 1, col: activeFieldCols.length - 1 }))
                          }}
                        >
                          ← Back
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ fontSize: '0.72rem', color: 'var(--red)' }}
                          onClick={() => setTableCursor(null)}
                        >
                          ✕ Stop
                        </button>
                      </>
                    )}
                  </div>

                  {/* Auto-table draw options */}
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', paddingTop: 2, borderTop: '1px solid var(--border)' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                      <input type="checkbox" checked={continueTable} onChange={e => setContinueTable(e.target.checked)} />
                      Continue table
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                      <input type="checkbox" checked={ignoreFirstRow} onChange={e => setIgnoreFirstRow(e.target.checked)} />
                      Ignore 1st row
                    </label>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                  Click words to label · Shift+click for multiple
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Modals */}
      {showAddField && project && (
        <AddFieldModal
          project={project}
          onClose={() => setShowAddField(false)}
          onCreated={(field) => {
            setProject(prev => ({ ...prev, fields: [...(prev.fields || []), field] }))
            setActiveFieldId(field.id)
          }}
        />
      )}
      {tableCellPending && activeField && (
        <TableCellModal
          field={activeField}
          onConfirm={handleTableCellConfirm}
          onClose={() => setTableCellPending(null)}
        />
      )}
      {editingField && project && (
        <EditFieldModal
          project={project}
          field={editingField}
          onClose={() => setEditingField(null)}
          onUpdated={handleFieldUpdated}
        />
      )}
    </div>
  )
}
