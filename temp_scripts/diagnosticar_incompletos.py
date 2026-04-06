"""
diagnosticar_incompletos.py - Investiga por qué años recientes están incompletos
"""

import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

# Obtener todas las columnas
cursor.execute("PRAGMA table_info(normalized_financials)")
columnas_info = cursor.fetchall()
todas_las_columnas = [col[1] for col in columnas_info]

# Columnas requeridas para non_financial
COLUMNAS_REQUERIDAS = [
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

print("=" * 100)
print("DIAGNOSTICO: CENCOSUD.SN y MALLPLAZA.SN años recientes")
print("=" * 100)
print()

for ticker in ['CENCOSUD.SN', 'MALLPLAZA.SN', 'CHILE.SN']:
    print(f"\n{'=' * 100}")
    print(f"TICKER: {ticker}")
    print(f"{'=' * 100}")

    # Obtener datos del año más reciente
    cursor.execute("""
        SELECT year, month
        FROM normalized_financials
        WHERE ticker = ?
        ORDER BY year DESC, month DESC
        LIMIT 1
    """, (ticker,))

    row = cursor.fetchone()
    if not row:
        print("  [ERROR] No se encontraron datos")
        continue

    year, month = row
    print(f"  Periodo más reciente: {year}-{month}")

    # Obtener todas las columnas para ese año
    cursor.execute(f"""
        SELECT {', '.join(todas_las_columnas)}
        FROM normalized_financials
        WHERE ticker = ? AND year = ? AND month = ?
    """, (ticker, year, month))

    row = cursor.fetchone()
    if not row:
        print("  [ERROR] No se encontraron datos para ese periodo")
        continue

    # Crear diccionario de valores
    datos = dict(zip(todas_las_columnas, row))

    # Analizar columnas requeridas
    print(f"\n  Columnas Requeridas (non_financial):")
    print(f"  {'Columna':<30} {'Valor':<20} {'Estado'}")
    print(f"  {'-' * 70}")

    presentes = 0
    faltantes = []

    for col in COLUMNAS_REQUERIDAS:
        valor = datos.get(col)
        if valor is not None:
            # Formatear valor
            if isinstance(valor, float):
                valor_str = f"{valor:,.0f}" if abs(valor) > 1000 else f"{valor:.2f}"
            else:
                valor_str = str(valor)
            print(f"  {col:<30} {valor_str:<20} [OK]")
            presentes += 1
        else:
            print(f"  {col:<30} {'NULL':<20} [FALTA]")
            faltantes.append(col)

    print(f"\n  Resumen:")
    print(f"    Presentes: {presentes}/{len(COLUMNAS_REQUERIDAS)}")
    print(f"    Porcentaje: {presentes/len(COLUMNAS_REQUERIDAS)*100:.1f}%")
    print(f"    Faltantes: {len(faltantes)}")

    if faltantes:
        print(f"\n  Columnas faltantes:")
        for col in faltantes:
            print(f"    - {col}")

    # Verificar industria
    industry = datos.get('industry')
    print(f"\n  Industria: {industry}")

    if industry == 'financial':
        print(f"  [NOTA] Es banco/AFP, debería usar columnas de financial")
    else:
        print(f"  [NOTA] Es non_financial, debería tener columnas de P&L y Cash Flow")

con.close()

print()
print("=" * 100)
