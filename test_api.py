import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('ufo_matrix.db')
query = """
SELECT motif_number
FROM Motif_Dictionary
LIMIT 5
"""
print(pd.read_sql_query(query, conn))
conn.close()
