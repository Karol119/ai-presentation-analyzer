import sqlite3

DB = "storage/DB/ai_analyzer.db"

conn = sqlite3.connect(DB)
cursor = conn.cursor()

# Tablas
cursor.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name;
""")

tables = cursor.fetchall()

print("TABLAS:")
for table in tables:
    print(f"- {table[0]}")

# Estructura de cada tabla
for (table_name,) in tables:
    print(f"\n--- {table_name} ---")

    cursor.execute(f'PRAGMA table_info("{table_name}")')
    columns = cursor.fetchall()

    for column in columns:
        print(column)

conn.close()