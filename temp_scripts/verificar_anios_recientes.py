"""
verificar_anios_recientes.py - Identifica tickers con datos faltantes en 2023-2025
"""
import sqlite3

con = sqlite3.connect('output/warehouse.db')
cursor = con.cursor()

print("=" * 100)
print("TICKERS CON DATOS INCOMPLETOS O FALTANTES EN 2023-2025")
print("=" * 100)
print()

# Obtener lista de tickers únicos
cursor.execute("""
    SELECT DISTINCT ticker
    FROM normalized_financials
    ORDER BY ticker
""")
tickers = [row[0] for row in cursor.fetchall()]

anios_criticos = [2023, 2024, 2025]
problemas = {}

for ticker in tickers:
    for ano in anios_criticos:
        # Verificar si existe registro
        cursor.execute("""
            SELECT year,
                   CASE WHEN assets > 0 THEN 1 ELSE 0 END as assets,
                   CASE WHEN liabilities > 0 THEN 1 ELSE 0 END as liab,
                   CASE WHEN equity > 0 THEN 1 ELSE 0 END as equity,
                   CASE WHEN revenue > 0 THEN 1 ELSE 0 END as revenue,
                   CASE WHEN net_income > 0 THEN 1 ELSE 0 END as ni
            FROM normalized_financials
            WHERE ticker = ? AND year = ?
        """, (ticker, ano))

        row = cursor.fetchone()

        if not row:
            # No existe registro
            if ticker not in problemas:
                problemas[ticker] = {}
            problemas[ticker][ano] = "SIN DATOS"
        else:
            year, assets, liab, equity, revenue, ni = row

            # Determinar si es banco (no tiene revenue)
            es_banco = (revenue == 0 and assets == 1 and liab == 1 and equity == 1 and ni == 1) or \
                       (assets == 1 and liab == 1 and equity == 1 and ni == 1 and revenue == 0)

            # Verificar completitud
            if es_banco:
                if not (assets and liab and equity and ni):
                    if ticker not in problemas:
                        problemas[ticker] = {}
                    problemas[ticker][ano] = "INCOMPLETO"
            else:
                # Non-financial
                if not (assets and liab and equity and revenue and ni):
                    if ticker not in problemas:
                        problemas[ticker] = {}
                    problemas[ticker][ano] = "INCOMPLETO"

if problemas:
    print(f"{'TICKER':<20}  2023      2024      2025")
    print("-" * 100)

    for ticker in sorted(problemas.keys()):
        print(f"{ticker:<20}  ", end="")

        for ano in anios_criticos:
            if ano in problemas[ticker]:
                problema = problemas[ticker][ano]
                print(f"{problema:<10} ", end="")
            else:
                print(f"{'OK':<10} ", end="")

        print()
else:
    print("[OK] Todos los tickers tienen datos completos para 2023-2025")

print()
print("=" * 100)
print("VERIFICANDO PEHUENCHE.SN Y ZOFRI.SN")
print("=" * 100)
print()

# Buscar PEHUENCHE y ZOFRI
tickers_buscar = ['PEHUENCHE.SN', 'ZOFRI.SN', 'PEHUENCHE', 'ZOFRI']

for ticker_buscar in tickers_buscar:
    cursor.execute("""
        SELECT COUNT(*)
        FROM normalized_financials
        WHERE ticker LIKE ?
    """, (f"%{ticker_buscar}%",))

    count = cursor.fetchone()[0]

    if count > 0:
        print(f"[ENCONTRADO] {ticker_buscar}: {count} registros")

        # Mostrar años disponibles
        cursor.execute("""
            SELECT DISTINCT year
            FROM normalized_financials
            WHERE ticker LIKE ?
            ORDER BY year
        """, (f"%{ticker_buscar}%",))

        years = [row[0] for row in cursor.fetchall()]
        print(f"  Años: {years}")
    else:
        print(f"[NO ENCONTRADO] {ticker_buscar}: No está en el warehouse")

print()
print("=" * 100)
con.close()
