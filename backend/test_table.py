import json
from app.database import SessionLocal
from app.models.project import Field
from app.models.training import ModelVersion

db = SessionLocal()

field = db.query(Field).filter(Field.name == 'ordertable').first()
if not field:
    print("No ordertable field found")
    exit()

print("Field:", field.name, "type:", field.field_type, "project:", field.project_id)

model = db.query(ModelVersion).filter(
    ModelVersion.project_id == field.project_id,
    ModelVersion.is_active == True
).first()

if not model:
    print("No active model")
    exit()

print("Model:", model.id, "type:", model.model_type, "path:", model.model_path)

if model.model_type == 'template':
    with open(model.model_path) as f:
        artifact = json.load(f)

    field_def = artifact.get('fields', {}).get('ordertable', {})
    print("field_type:", field_def.get('field_type'))
    cols = field_def.get('columns', {})
    print("Columns:", list(cols.keys()))
    for col, data in cols.items():
        mb = data['mean_box']
        sb = data['std_box']
        tol = data.get('tolerance', 0.08)
        print(f"  {col}: mean={[round(x,3) for x in mb]}, std={[round(x,3) for x in sb]}, tol={tol}")
    page_anchor = field_def.get('page_anchors', {})
    print("Page anchors:", page_anchor)
