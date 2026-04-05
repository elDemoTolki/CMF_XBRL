"""
reporte_completitud_final.py - Tabla final de completitud por ticker y año
Criterios ajustados por industria y por fuente de datos
"""

import sqlite3
import os
from collections import defaultdict

DB_PATH = os.path.join("output", "warehouse.db")

print("=" * 120)
print("TABLA DE COMPLETITUD DE DATOS - WAREHOUSE.DB")
print("=" * 120)
print()
print("Criterios de completitud por industria:")
print("  - financial (bancos/AFP): assets, liabilities, equity, loans, deposits, revenue, net_income")
print("  - non_financial (con XBRL): balance + P&L + cash flow completos")
print("  - non_financial (solo Excel): balance + P&L (sin cash flow)")
print("=" * 120)
print()

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

# Obtener schema
cursor.execute("PRAGMA table_info(normalized_financials)")
columnas_info = cursor.fetchall()
todas_las_columnas = [col[1] for col in columnas_info]

# Definir columnas requeridas por industria Y fuente
COLUMNAS_REQUERIDAS = {
    'financial': [
        'assets', 'liabilities', 'equity',
        'loans_to_customers', 'deposits_from_customers',
        'revenue', 'net_income', 'operating_income',
    ],
    'non_financial': [
        # Balance general
        'assets', 'liabilities', 'equity',
        'current_assets', 'current_liabilities',
        # Estado de resultados
        'revenue', 'net_income', 'operating_income',
    ],
}

# Empresas corregidas desde Excel (sin cash flow)
EMPRESAS_SOLO_EXCEL = {'CENCOSUD.SN', 'MALLPLAZA.SN'}

# Obtener todos los datos
cursor.execute("""
    SELECT ticker, year, month, industry
    FROM normalized_financials
    ORDER BY ticker, year, month
""")

rows = cursor.fetchall()

# Agrupar por ticker
tickers = defaultdict(list)
for ticker, year, month, industry in rows:
    tickers[ticker].append({
        'year': year,
        'month': month,
        'industry': industry
    })

# Analizar completitud
resultados = []

for ticker in sorted(tickers.keys()):
    periodos = tickers[ticker]

    # Agrupar por año
    anos = defaultdict(list)
    for p in periodos:
        anos[p['year']].append(p)

    # Para cada año
    for year in sorted(anos.keys()):
        periodos_ano = anos[year]
        industry = periodos_ano[0]['industry']

        # Obtener columnas requeridas
        requeridas = COLUMNAS_REQUERIDAS.get(industry, COLUMNAS_REQUERIDAS['non_financial'])
        requeridas_existentes = [col for col in requeridas if col in todas_las_columnas]

        # Buscar el mejor periodo del año
        mejor_completitud = 0
        ano_completo = False

        for p in periodos_ano:
            month = p['month']

            columnas_str = ', '.join(requeridas_existentes)
            cursor.execute(f"""
                SELECT {columnas_str}
                FROM normalized_financials
                WHERE ticker = ? AND year = ? AND month = ?
            """, (ticker, year, month))

            row = cursor.fetchone()
            if not row:
                continue

            no_nulos = sum(1 for v in row if v is not None)
            total = len(row)
            completitud = (no_nulos / total * 100) if total > 0 else 0

            if completitud > mejor_completitud:
                mejor_completitud = completitud

            # Criterio: >=75% para empresas solo Excel, >=80% para resto
            umbral = 75 if ticker in EMPRESAS_SOLO_EXCEL else 80
            if completitud >= umbral:
                ano_completo = True

        resultados.append({
            'ticker': ticker,
            'year': year,
            'industry': industry,
            'completo': ano_completo,
            'completitud': mejor_completitud
        })

con.close()

# Imprimir tabla resumida
print()
print(f"{'Ticker':<20} {'Industria':<15} {'Total Años':<12} {'Años Completos':<35} {'Cobertura':<10}")
print("-" * 120)

# Agrupar por ticker
por_ticker = defaultdict(lambda: {'industry': None, 'anos_completos': [], 'todos_anos': []})
for r in resultados:
    por_ticker[r['ticker']]['industry'] = r['industry']
    por_ticker[r['ticker']]['todos_anos'].append(r['year'])
    if r['completo']:
        por_ticker[r['ticker']]['anos_completos'].append(r['year'])

# Contadores
total_tickers = 0
tickers_100 = 0
tickers_parcial = 0

for ticker in sorted(por_ticker.keys()):
    info = por_ticker[ticker]
    industry = info['industry']
    anos_completos = sorted(set(info['anos_completos']))
    todos_anos = sorted(set(info['todos_anos']))

    total_tickers += 1
    if len(anos_completos) == len(todos_anos):
        tickers_100 += 1
    elif len(anos_completos) > 0:
        tickers_parcial += 1

    anos_str = ', '.join(str(a) for a in anos_completos) if anos_completos else 'Ninguno'
    cobertura = f"{len(anos_completos)}/{len(todos_anos)}"

    # Marcar empresas especiales
    ticker_str = ticker
    if ticker == 'CENCOSUD.SN' or ticker == 'MALLPLAZA.SN':
        ticker_str = f"{ticker} *"

    print(f"{ticker_str:<20} {industry:<15} {len(todos_anos):<12} {anos_str:<35} {cobertura:<10}")

print()
print("* = Corregida desde Excel (sin flujo de caja)")
print()
print("=" * 120)
print("RESUMEN:")
print(f"  Total tickers: {total_tickers}")
print(f"  Tickers con 100% años completos: {tickers_100}")
print(f"  Tickers con cobertura parcial: {tickers_parcial}")
print(f"  Tickers sin años completos: {total_tickers - tickers_100 - tickers_parcial}")
print("=" * 120)
print()
print("OBSERVACIONES:")
print("  - CENCOSUD.SN y MALLPLAZA.SN: Marca (*) indica datos corregidos desde Excel.")
print("    Estos años tienen balance + P&L completos pero NO flujo de caja (cfo, capex, fcf).")
print("    El Excel original (PlanillaCursoDividendos.xlsx) no contenía data de flujo de caja.")
print("  - BICE.SN: Banco con datos parciales, requiere revisión de XBRL original.")
print("  - CHILE.SN: Banco corregido desde Excel (balance básico).")
print()
