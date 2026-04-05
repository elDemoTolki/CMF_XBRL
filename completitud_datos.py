"""
completitud_datos.py - Analiza completitud de datos por ticker y año
Considera diferencias entre financial (bancos/AFP) y non_financial
"""

import sqlite3
import os
from collections import defaultdict

DB_PATH = os.path.join("output", "warehouse.db")

print("=" * 100)
print("ANALISIS DE COMPLETITUD DE DATOS POR TICKER Y AÑO")
print("=" * 100)
print()

if not os.path.exists(DB_PATH):
    print(f"[ERROR] No existe {DB_PATH}")
    exit(1)

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

# Obtener schema para conocer todas las columnas
cursor.execute("PRAGMA table_info(normalized_financials)")
columnas_info = cursor.fetchall()
todas_las_columnas = [col[1] for col in columnas_info]

print(f"[INFO] Total columnas en BD: {len(todas_las_columnas)}")
print(f"[INFO] Columnas disponibles:")
for i, col in enumerate(todas_las_columnas, 1):
    print(f"  {i:2d}. {col}")
print()

# Definir columnas requeridas por industria (solo las que realmente existen)
COLUMNAS_REQUERIDAS = {
    'financial': [
        # Balance bancario
        'assets', 'liabilities', 'equity',
        'loans_to_customers', 'deposits_from_customers',
        'cash',
        # Resultados bancarios
        'revenue', 'net_income',
        'operating_income',
    ],
    'non_financial': [
        # Balance general
        'assets', 'liabilities', 'equity',
        'current_assets', 'current_liabilities',
        'cash', 'inventories', 'trade_receivables',
        # Estado de resultados
        'revenue', 'net_income', 'operating_income',
        'cost_of_sales',
        # Flujo de caja
        'cfo', 'capex', 'fcf',
    ]
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

print(f"[INFO] Total tickers únicos: {len(tickers)}")
print()

# Analizar completitud por ticker y año
resultados = []

for ticker in sorted(tickers.keys()):
    periodos = tickers[ticker]

    # Agrupar por año (un ticker puede tener múltiples meses por año)
    anos = defaultdict(list)
    for p in periodos:
        anos[p['year']].append(p)

    # Para cada año, verificar si tiene datos completos
    for year in sorted(anos.keys()):
        periodos_ano = anos[year]
        industry = periodos_ano[0]['industry']

        # Obtener columnas requeridas para esta industria
        requeridas = COLUMNAS_REQUERIDAS.get(industry, COLUMNAS_REQUERIDAS['non_financial'])

        # Filtrar solo columnas que existen en la BD
        requeridas_existentes = [col for col in requeridas if col in todas_las_columnas]

        # Verificar si AL MENOS UN periodo del año tiene todos los datos
        ano_completo = False
        mejor_completitud = 0
        mejor_mes = None

        for p in periodos_ano:
            month = p['month']

            # Construir query dinámico
            columnas_str = ', '.join(requeridas_existentes)
            cursor.execute(f"""
                SELECT {columnas_str}
                FROM normalized_financials
                WHERE ticker = ? AND year = ? AND month = ?
            """, (ticker, year, month))

            row = cursor.fetchone()
            if not row:
                continue

            # Contar valores NO nulos
            no_nulos = sum(1 for v in row if v is not None)
            total = len(row)

            porcentaje_completitud = (no_nulos / total * 100) if total > 0 else 0

            if porcentaje_completitud > mejor_completitud:
                mejor_completitud = porcentaje_completitud
                mejor_mes = month

            # Considerar completo si tiene al menos 80% de datos
            if porcentaje_completitud >= 80:
                ano_completo = True

        resultados.append({
            'ticker': ticker,
            'year': year,
            'industry': industry,
            'completo': ano_completo,
            'completitud': mejor_completitud,
            'mejor_mes': mejor_mes,
            'total_periodos': len(periodos_ano)
        })

con.close()

# Imprimir resultados
print()
print("=" * 100)
print("RESUMEN DE COMPLETITUD POR TICKER Y AÑO")
print("=" * 100)
print()
print(f"{'Ticker':<20} {'Industria':<15} {'Años Completos (>=80% datos)'}")
print("-" * 100)

# Agrupar por ticker
por_ticker = defaultdict(lambda: {'industry': None, 'anos': [], 'todos_anos': []})
for r in resultados:
    por_ticker[r['ticker']]['industry'] = r['industry']
    por_ticker[r['ticker']]['todos_anos'].append(r['year'])
    if r['completo']:
        por_ticker[r['ticker']]['anos'].append(r['year'])

for ticker in sorted(por_ticker.keys()):
    info = por_ticker[ticker]
    industry = info['industry']
    anos_completos = sorted(info['anos'])
    todos_anos = sorted(info['todos_anos'])

    if anos_completos:
        anos_str = ', '.join(str(a) for a in anos_completos)
        faltan = [a for a in todos_anos if a not in anos_completos]
        if faltan:
            print(f"{ticker:<20} {industry:<15} {anos_str} (incompletos: {faltan})")
        else:
            print(f"{ticker:<20} {industry:<15} {anos_str}")
    else:
        todos_str = ', '.join(str(a) for a in todos_anos)
        print(f"{ticker:<20} {industry:<15} (ninguno completo - años: {todos_str})")

print()
print("=" * 100)
print("LEYENDA:")
print("  - Datos completos = tiene al menos 80% de las columnas requeridas para su industria")
print("  - financial: bancos y AFPs (requieren métricas bancarias)")
print("  - non_financial: empresas regulares (requieren balance, P&L, cash flow completos)")
print("=" * 100)
print()

# Estadísticas finales
total_tickers = len(por_ticker)
tickers_con_datos = sum(1 for t in por_ticker.values() if t['anos'])

print(f"Total tickers en BD: {total_tickers}")
print(f"Tickers con al menos 1 año completo: {tickers_con_datos}")
print(f"Porcentaje de cobertura: {tickers_con_datos/total_tickers*100:.1f}%")
print()

# Tabla resumen por ticker
print()
print("=" * 100)
print("TABLA DETALLADA POR TICKER")
print("=" * 100)
print()
print(f"{'Ticker':<20} {'Industria':<15} {'Años en BD':<20} {'Años Completos':<20} {'Cobertura':<10}")
print("-" * 100)

for ticker in sorted(por_ticker.keys()):
    info = por_ticker[ticker]
    industry = info['industry']
    anos_completos = sorted(info['anos'])
    todos_anos = sorted(info['todos_anos'])

    todos_str = ', '.join(str(a) for a in todos_anos)
    completos_str = ', '.join(str(a) for a in anos_completos) if anos_completos else 'Ninguno'
    cobertura = f"{len(anos_completos)}/{len(todos_anos)}"

    print(f"{ticker:<20} {industry:<15} {todos_str:<20} {completos_str:<20} {cobertura:<10}")

print("=" * 100)
