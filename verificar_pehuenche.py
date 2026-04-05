"""
verificar_pehuenche.py - Verifica si PEHUENCHE existe en el warehouse
"""
import sqlite3

con = sqlite3.connect('output/warehouse.db')
cursor = con.cursor()

print("=" * 100)
print("VERIFICANDO PEHUENCHE EN WAREHOUSE")
print("=" * 100)
print()

# Buscar cualquier ticker que contenga "PEHUENCHE"
cursor.execute("""
    SELECT DISTINCT ticker
    FROM normalized_financials
    WHERE ticker LIKE '%PEHUENCHE%'
""")
matches = [row[0] for row in cursor.fetchall()]

if matches:
    print(f"Encontrados: {matches}")
    for ticker in matches:
        cursor.execute("""
            SELECT year, month, assets, liabilities, equity, revenue, net_income
            FROM normalized_financials
            WHERE ticker = ?
            ORDER BY year
        """, (ticker,))

        rows = cursor.fetchall()
        print(f"\n{ticker}: {len(rows)} registros")

        for row in rows:
            year, month, assets, liab, equity, revenue, ni = row
            print(f"  {year}: assets={assets}, liab={liab}, equity={equity}, revenue={revenue}, ni={ni}")
else:
    print("[INFO] PEHUENCHE no existe en el warehouse")
    print("      Necesito INSERTAR nuevos registros")
    print()
    print("Por favor, pásame las tablas con los siguientes datos:")
    print("  - Año")
    print("  - Total Activos (assets)")
    print("  - Total Pasivos (liabilities)")
    print("  - Total Patrimonio (equity)")
    print("  - Ingresos/Revenue (revenue)")
    print("  - Utilidad Neta/Resultado del ejercicio (net_income)")

con.close()
