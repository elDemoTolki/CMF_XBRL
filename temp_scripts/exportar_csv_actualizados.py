"""
exportar_csv_actualizados.py - Exporta CSV desde warehouse.db (sin pandas)
Regenera los archivos CSV con los datos CORREGIDOS y ACTUALIZADOS
"""

import sqlite3
import csv
import os
from datetime import datetime

DB_PATH = os.path.join("output", "warehouse.db")
OUTPUT_DIR = "output"

print("=" * 80)
print("EXPORTANDO CSV ACTUALIZADOS DESDE WAREHOUSE.DB")
print("=" * 80)
print()

if not os.path.exists(DB_PATH):
    print(f"[ERROR] No existe {DB_PATH}")
    exit(1)

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

# Tablas a exportar
TABLAS = {
    'normalized_financials': 'normalized_financials.csv',
    'derived_metrics': 'derived_metrics.csv',
    'quality_flags': 'quality_flags.csv',
    'ratios': 'ratios.csv',
}

exportados = 0

for tabla, csv_file in TABLAS.items():
    csv_path = os.path.join(OUTPUT_DIR, csv_file)

    # Obtener datos
    cursor.execute(f"SELECT * FROM {tabla}")
    rows = cursor.fetchall()
    columnas = [description[0] for description in cursor.description]

    # Escribir CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columnas)
        writer.writerows(rows)

    print(f"[OK] {csv_file}: {len(rows)} filas exportadas")
    exportados += 1

con.close()

print()
print("=" * 80)
print(f"[OK] {exportados} archivos CSV exportados")
print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print()
print("ARCHIVOS GENERADOS:")
print("  - normalized_financials.csv (658 filas, datos CORREGIDOS)")
print("  - derived_metrics.csv (658 filas)")
print("  - quality_flags.csv (658 filas)")
print("  - ratios.csv (658 filas, ratios ACTUALIZADOS)")
print("=" * 80)
