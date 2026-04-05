"""
tabla_completa_tickers.py - Tabla de completud de datos por ticker y año
"""
import sqlite3

con = sqlite3.connect('output/warehouse.db')
cursor = con.cursor()

# Obtener lista de tickers únicos
cursor.execute("""
    SELECT DISTINCT ticker
    FROM normalized_financials
    ORDER BY ticker
""")
tickers = [row[0] for row in cursor.fetchall()]

print("=" * 120)
print("TABLA DE COMPLETUD DE DATOS POR TICKER Y AÑO")
print("=" * 120)
print()

# Para cada ticker, obtener años disponibles
datos_tickers = {}

for ticker in tickers:
    cursor.execute("""
        SELECT year,
               CASE WHEN assets > 0 THEN 1 ELSE 0 END as assets,
               CASE WHEN liabilities > 0 THEN 1 ELSE 0 END as liab,
               CASE WHEN equity > 0 THEN 1 ELSE 0 END as equity,
               CASE WHEN revenue > 0 THEN 1 ELSE 0 END as revenue,
               CASE WHEN net_income > 0 THEN 1 ELSE 0 END as ni
        FROM normalized_financials
        WHERE ticker = ?
        ORDER BY year
    """, (ticker,))

    rows = cursor.fetchall()

    for year, assets, liab, equity, revenue, ni in rows:
        if ticker not in datos_tickers:
            datos_tickers[ticker] = {}

        # Determinar tipo de empresa
        # Bancos/AFP: tienen assets, liab, equity, NI pero NO revenue (opcional)
        # Non-financial: tienen assets, liab, equity, revenue, NI

        # Para considerar completo:
        # Bancos/AFP: assets, liab, equity, NI
        # Non-financial: assets, liab, equity, revenue, NI

        es_banco = (revenue == 0)  # Si no tiene revenue, probablemente es banco

        if es_banco:
            completo = (assets == 1 and liab == 1 and equity == 1 and ni == 1)
        else:
            completo = (assets == 1 and liab == 1 and equity == 1 and revenue == 1 and ni == 1)

        datos_tickers[ticker][year] = {
            'completo': completo,
            'es_banco': es_banco
        }

# Obtener rango de años
cursor.execute("""
    SELECT MIN(year), MAX(year)
    FROM normalized_financials
""")
min_year, max_year = cursor.fetchone()
anios = list(range(min_year, max_year + 1))

# Imprimir tabla
print(f"{'TICKER':<15} ", end="")
for ano in anios:
    print(f"{ano:>4} ", end="")
print(f"TOTAL")
print("-" * 120)

for ticker in sorted(datos_tickers.keys()):
    print(f"{ticker:<15} ", end="")

    total_completos = 0

    for ano in anios:
        if ano in datos_tickers[ticker]:
            if datos_tickers[ticker][ano]['completo']:
                print(f"{'X':>4} ", end="")
                total_completos += 1
            else:
                print(f"{'?':>4} ", end="")
        else:
            print(f"{'-':>4} ", end="")

    print(f"  {total_completos}/{len(anios)}")

print()
print("=" * 120)
print("LEYENDA:")
print("  X = Datos completos para ese año")
print("  ? = Datos incompletos (faltan campos)")
print("  - = Sin datos para ese año")
print()
print("Bancos/AFP requieren: assets, liabilities, equity, net_income")
print("Non-financial requieren: assets, liabilities, equity, revenue, net_income")
print("=" * 120)

con.close()
