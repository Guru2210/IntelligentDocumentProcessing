"""
End-to-end audit of training and extraction pipelines for the 7-column ordertable field.
Run with: python audit_pipeline.py
"""
import sys, json
sys.path.insert(0, '.')

from app.database import SessionLocal
from app.models.project import Field, FieldColumn
from app.models.document import Label, Word, Page, Document
from app.models.training import ModelVersion

db = SessionLocal()

# ─── 1. Check field & columns ──────────────────────────────────────────────
print("=" * 60)
print("1. FIELD DEFINITION")
field = db.query(Field).filter(Field.name == 'ordertable').first()
cols  = db.query(FieldColumn).filter(FieldColumn.field_id == field.id).order_by(FieldColumn.order).all()
print(f"   Field: {field.name}  type={field.field_type}  project={field.project_id}")
print(f"   Columns ({len(cols)}): {[c.column_name for c in cols]}")

col_names = [c.column_name for c in cols]
assert len(col_names) == 7, "Expected 7 columns!"

# ─── 2. Check label data quality ──────────────────────────────────────────
print()
print("=" * 60)
print("2. LABEL QUALITY")
ALL_labels = db.query(Label).filter(Label.field_id == field.id).all()
print(f"   Total label records: {len(ALL_labels)}")

labels_with_word_ids = [l for l in ALL_labels if l.word_ids]
labels_with_bboxes   = [l for l in ALL_labels if l.bounding_boxes]
labels_no_col        = [l for l in ALL_labels if not l.column_name]

print(f"   Labels with word_ids:     {len(labels_with_word_ids)}")
print(f"   Labels with bounding_boxes: {len(labels_with_bboxes)}")
print(f"   Labels with NO column_name: {len(labels_no_col)}")

# Show sample rows
from collections import defaultdict
by_col = defaultdict(int)
for l in ALL_labels:
    by_col[l.column_name or '(none)'] += 1
print("   Label counts per column:")
for col, cnt in sorted(by_col.items()):
    print(f"     {col!r}: {cnt}")

# ─── 3. Neural training data prep audit ───────────────────────────────────
print()
print("=" * 60)
print("3. NEURAL TRAINING DATA PREP AUDIT")
# Simulate what _prepare_neural_data_sessionless does for one document
doc_id = db.query(Document).filter(
    Document.project_id == field.project_id,
    Document.label_status == 'complete'
).first().id

page = db.query(Page).filter(Page.document_id == doc_id, Page.page_number == 1).first()
words = db.query(Word).filter(Word.page_id == page.id).all()
labels_p1 = db.query(Label).filter(Label.document_id == doc_id, Label.page_number == 1).all()

word_idx_map = {str(w.id): i for i, w in enumerate(words)}
print(f"   Doc: {str(doc_id)[:8]}  page1 words: {len(words)}  labels: {len(labels_p1)}")

table_labels = [l for l in labels_p1 if l.field_id == field.id]
print(f"   ordertable labels on page 1: {len(table_labels)}")

word_coverage = set()
for lbl in table_labels:
    for wid in (lbl.word_ids or []):
        if wid in word_idx_map:
            word_coverage.add(word_idx_map[wid])

print(f"   Words covered by ordertable labels: {len(word_coverage)}")
print(f"   NOTE: Neural BIO training tags ALL these words as 'ordertable' — no column info")

# ─── 4. Template model audit ──────────────────────────────────────────────
print()
print("=" * 60)
print("4. TEMPLATE MODEL AUDIT")
template_model = db.query(ModelVersion).filter(
    ModelVersion.project_id == field.project_id,
    ModelVersion.model_type == 'template'
).order_by(ModelVersion.version.desc()).first()

if template_model:
    print(f"   Template model: v{template_model.version}  path={template_model.model_path}")
    try:
        with open(template_model.model_path) as f:
            artifact = json.load(f)
        fd = artifact['fields'].get('ordertable', {})
        print(f"   field_type: {fd.get('field_type')}")
        col_defs = fd.get('columns', {})
        print(f"   Stored columns ({len(col_defs)}): {list(col_defs.keys())}")
        for col, info in col_defs.items():
            mb = info['mean_box']
            print(f"     '{col}': mean_box=[{mb[0]:.3f},{mb[1]:.3f},{mb[2]:.3f},{mb[3]:.3f}] tol={info.get('tolerance',0.08)}")
    except Exception as e:
        print(f"   ERROR reading artifact: {e}")
else:
    print("   NO template model found — only neural models exist")

# ─── 5. Active model summary ──────────────────────────────────────────────
print()
print("=" * 60)
print("5. ACTIVE MODEL")
active = db.query(ModelVersion).filter(
    ModelVersion.project_id == field.project_id,
    ModelVersion.is_active == True
).first()
if active:
    print(f"   v{active.version}  type={active.model_type}  path={active.model_path}")
    print(f"   overall_accuracy={active.overall_accuracy}")

# ─── 6. pdfplumber test on real document ──────────────────────────────────
print()
print("=" * 60)
print("6. PDFPLUMBER TABLE EXTRACTION TEST")
from app.models.extraction import ExtractionJob
job = db.query(ExtractionJob).filter(
    ExtractionJob.original_filename.ilike('%.pdf')
).order_by(ExtractionJob.created_at.desc()).first()

if job:
    print(f"   Using doc: {job.original_filename}")
    try:
        from app.services.storage_service import download_file
        fb = download_file(job.document_key)
        import pdfplumber, io
        with pdfplumber.open(io.BytesIO(fb)) as pdf:
            total_tables = 0
            for i, pg in enumerate(pdf.pages):
                tables = pg.extract_tables() or []
                for t in tables:
                    row_count = len(t)
                    col_count = max((len(r) for r in t if r), default=0)
                    print(f"   Page {i+1}: table with {row_count} rows x {col_count} cols")
                    if t:
                        print(f"     Header row: {[str(c)[:20] for c in t[0]]}")
                    total_tables += 1
        print(f"   Total tables found: {total_tables}")
        
        # Test header matching against our 7 column names
        print()
        print("   Column fuzzy matching test:")
        from app.services.inference_service import _col_similarity
        with pdfplumber.open(io.BytesIO(fb)) as pdf:
            for pg in pdf.pages:
                for t in (pg.extract_tables() or []):
                    if not t:
                        continue
                    header = [str(c or '').strip().lower() for c in t[0]]
                    for cn in col_names:
                        best_score = 0
                        best_match = None
                        for hidx, hcell in enumerate(header):
                            cn_lower = cn.strip().lower()
                            if cn_lower in hcell or hcell in cn_lower:
                                score = 1.0
                            else:
                                score = _col_similarity(cn_lower, hcell)
                            if score > best_score:
                                best_score = score
                                best_match = (hidx, hcell)
                        print(f"     '{cn}' -> col_idx={best_match[0] if best_match else '?'} match='{best_match[1] if best_match else ''}' score={best_score:.2f}")
    except Exception as e:
        import traceback
        traceback.print_exc()
else:
    print("   No PDF extraction jobs found")

print()
print("=" * 60)
print("AUDIT COMPLETE")
db.close()
