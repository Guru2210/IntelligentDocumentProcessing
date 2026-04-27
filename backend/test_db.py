import sqlite3
conn = sqlite3.connect('idp_local.db')
cursor = conn.cursor()
cursor.execute('SELECT project_id, id FROM model_versions ORDER BY created_at DESC LIMIT 1')
row = cursor.fetchone()
if not row:
    print('No model version found.')
else:
    project_id = row[0]
    cursor.execute("SELECT id, name FROM fields WHERE project_id=? AND field_type='table'", (project_id,))
    for field_id, field_name in cursor.fetchall():
        cursor.execute("SELECT column_name, `order` FROM field_columns WHERE field_id=? ORDER BY `order`", (field_id,))
        # sqlite allows backticks for compat
        cols = cursor.fetchall()
        print(f'Table Field {field_name} columns: {cols}')
        print(f'Total FieldColumns count: {len(cols)}')
