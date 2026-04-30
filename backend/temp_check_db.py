import sqlite3
import json

conn = sqlite3.connect('idp_local.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('''
    SELECT f.name, f.table_mode, f.rows_per_record, c.column_name, c.row_level 
    FROM fields f 
    JOIN field_columns c ON f.id = c.field_id 
    WHERE f.name = "ship_table"
''')
rows = cur.fetchall()
print(json.dumps([dict(r) for r in rows], indent=2))
