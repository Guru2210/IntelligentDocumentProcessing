import sqlite3

conn = sqlite3.connect('idp_local.db')
cur = conn.cursor()

# Add table_mode and rows_per_record to fields table
try:
    cur.execute('ALTER TABLE fields ADD COLUMN table_mode VARCHAR(20) DEFAULT "normal"')
    print("Added fields.table_mode")
except Exception as e:
    print(f"fields.table_mode: {e}")

try:
    cur.execute('ALTER TABLE fields ADD COLUMN rows_per_record INTEGER DEFAULT 1')
    print("Added fields.rows_per_record")
except Exception as e:
    print(f"fields.rows_per_record: {e}")

# Add row_level to field_columns table
try:
    cur.execute('ALTER TABLE field_columns ADD COLUMN row_level INTEGER DEFAULT 0')
    print("Added field_columns.row_level")
except Exception as e:
    print(f"field_columns.row_level: {e}")

conn.commit()
conn.close()
print("Migration complete!")
