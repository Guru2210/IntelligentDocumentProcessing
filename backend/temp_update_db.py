import sqlite3

conn = sqlite3.connect('idp_local.db')
cur = conn.cursor()
cur.execute('''
    UPDATE field_columns 
    SET row_level = 1 
    WHERE column_name = 'GC ITEM DESCRIPTION' 
      AND field_id = (SELECT id FROM fields WHERE name = 'ship_table')
''')
conn.commit()

cur.execute('''
    UPDATE fields 
    SET rows_per_record = 3 
    WHERE name = 'ship_table'
''')
conn.commit()

print("Updated GC ITEM DESCRIPTION to row_level 1 and set rows_per_record to 3")
