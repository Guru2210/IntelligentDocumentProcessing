import sqlite3
conn = sqlite3.connect('idp_local.db')
cur = conn.cursor()
cur.execute('UPDATE field_columns SET row_level = 2 WHERE column_name IN ("ORDER QUANTITY", "BOAT DATE", "MAX CTNS") AND field_id = (SELECT id FROM fields WHERE name = "ship_table")')
conn.commit()
print('DB updated.')
