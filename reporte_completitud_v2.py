"""
reporte_completitud_v2.py - Criterios ajustados por industria
- Financial: balance + P&L básicos (loans/deposits son opcionales)
- Non-financial: balance + P&L básicos (cash flow es opcional)
"""

import sqlite3
import os
from collections import defaultdict

DB_PATH = os.path.join("output", "warehouse.db")

print("=" * 120)
print("TABLA DE COMPLETITUD - CRITERIOS AJUSTADOS POR INDUSTRIA")
print("=" * 120)
print()
print("Criterios de completitud:")
print("  - Financial (bancos/AFP): assets, liabilities, equity, revenue, net_income")
print("    loans/deposits/net_interest_income son OPCIONALES")
print()
print("  - Non-financial (empresas): assets, liabilities, equity, revenue, net_income")
print("    cash flow (cfo/capex/fcf) es OPCIONAL")
print("=" * 120)
print()

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

# Obtener schema
cursor.execute("PRAGMA table_info(normalized_financials)")
columnas_info = cursor.fetchall()
todas_las_columnas = [col[1] for col in columnas_info]

# Criterios ajustados - mínimo requerido (sin opcionales)
COLUMNAS_REQUERIDAS = {
    'financial': [
        'assets', 'liabilities', 'equity',
        'revenue', 'net_income',
    ],
    'non_financial': [
        'assets', 'liabilities', 'equity',
        'current_assets', 'current_liabilities',
        'revenue', 'net_income',
    ],
}

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

            # Criterio: >=70% de columnas requeridas
            if completitud >= 70:
                ano_completo = True

        resultados.append({
            'ticker': ticker,
            'year': year,
            'industry': industry,
            'completo': ano_completo,
            'completitud': mejor_completitud
        })

con.close()

# Imprimir tabla
print()
print(f"{'Ticker':<20} {'Industria':<15} {'Total Años':<12} {'Años Completos':<40} {'Cobertura':<10}")
print("-" * 120)

# Agrupar por ticker
por_ticker = defaultdict(lambda: {'industry': None, 'anos_completos': [], 'todos_anos': []})
for r in resultados:
    por_ticker[r['ticker']]['industry'] = r['industry']
    por_ticker[r['ticker']]['todos_anos'].append(r['year'])
    if r['completo']:
        por_ticker[r['ticker']]['anos_completos'].append(r['year'])

# Estadísticas
stats = {
    'financial': {'tickers': 0, 'completo': 0},
    'non_financial': {'tickers': 0, 'completo': 0},
}

for ticker in sorted(por_ticker.keys()):
    info = por_ticker[ticker]
    industry = info['industry']
    anos_completos = sorted(set(info['anos_completos']))
    todos_anos = sorted(set(info['todos_anos']))

    stats[industry]['tickers'] += 1
    if len(anos_completos) == len(todos_anos):
        stats[industry]['completo'] += 1

    anos_str = ', '.join(str(a) for a in anos_completos) if anos_completos else 'Ninguno'
    cobertura = f"{len(anos_completos)}/{len(todos_anos)}"

    # Marcar empresas con datos limitados
    ticker_str = ticker
    if ticker == 'CHILE.SN':
        ticker_str = f"{ticker} †"
    elif ticker in ['CENCOSUD.SN', 'MALLPLAZA.SN']:
        ticker_str = f"{ticker} *"

    print(f"{ticker_str:<20} {industry:<15} {len(todos_anos):<12} {anos_str:<40} {cobertura:<10}")

print()
print("† = Solo balance básico (assets + equity) desde Excel")
print("* = Corregida desde Excel (balance + P&L, sin flujo de caja)")
print()
print("=" * 120)
print("RESUMEN POR INDUSTRIA:")
print(f"  Financial (bancos/AFP): {stats['financial']['completo']}/{stats['financial']['tickers']} tickers con 100% cobertura")
print(f"  Non-financial: {stats['non_financial']['completo']}/{stats['non_financial']['tickers']} tickers con 100% cobertura")
print(f"  Total: {stats['financial']['completo'] + stats['non_financial']['completo']}/{stats['financial']['tickers'] + stats['non_financial']['tickers']} tickers con 100% cobertura")
print("=" * 120)
print()
