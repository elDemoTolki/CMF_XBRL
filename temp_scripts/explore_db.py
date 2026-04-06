"""Explora la estructura del warehouse.db"""
import sqlite3

conn = sqlite3.connect('output/warehouse.db')
cursor = conn.cursor()

# Listar tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tablas en warehouse.db:")
for t in tables:
    print(f"  - {t[0]}")

# Para cada tabla, mostrar columnas
for table in tables:
    table_name = table[0]
    print(f"\n=== {table_name} ===")
    
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print("Columnas:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"Registros: {count}")
    
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        rows = cursor.fetchall()
        print("Primeros 3 registros:")
        for row in rows:
            print(f"  {row}")

conn.close()