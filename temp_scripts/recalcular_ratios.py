"""
recalcular_ratios.py - Recalcula ratios sin pandas (solución al problema de DLLs)
Versión simplificada que solo requiere sqlite3
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join("output", "warehouse.db")

# Ratios a calcular
RATIOS_TO_CALCULATE = {
    # Profitability
    'roe': ('non_financial', 'net_income', 'equity'),
    'roa': ('non_financial', 'net_income', 'assets'),
    'net_margin': ('non_financial', 'net_income', 'revenue'),
    'ebit_margin': ('non_financial', 'operating_income', 'revenue'),

    # Liquidity
    'current_ratio': ('non_financial', 'current_assets', 'current_liabilities'),
    'cash_ratio': ('non_financial', 'cash', 'current_liabilities'),

    # Leverage
    'debt_to_equity': ('non_financial', 'debt_total', 'equity'),
    'debt_to_assets': ('non_financial', 'debt_total', 'assets'),

    # Efficiency
    'asset_turnover': ('non_financial', 'revenue', 'assets'),
    'inventory_turnover': ('non_financial', 'cost_of_sales', 'inventories'),
}


def calculate_ratio(numerator, denominator):
    """Calcula un ratio de forma segura."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    try:
        return numerator / denominator
    except:
        return None


def get_quality(numerator, denominator):
    """Determina calidad de un ratio."""
    if numerator is None or denominator is None:
        return 'missing'
    if denominator == 0:
        return 'invalid'

    # Ambos componentes vienen directo de XBRL
    return 'high'


def recalculate_ratios():
    """Recalcula todos los ratios."""
    print("=" * 80)
    print("Recalculando ratios financieros")
    print("=" * 80)
    print()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe {DB_PATH}")
        return

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Verificar si existe tabla de ratios
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ratios'")
    if not cursor.fetchone():
        print("[INFO] Tabla 'ratios' no existe. Se creará al ejecutar ratios.py con pandas.")
        con.close()
        return

    # Contar ratios existentes
    cursor.execute("SELECT COUNT(*) FROM ratios")
    existing = cursor.fetchone()[0]
    print(f"[INFO] Ratios existentes: {existing}")

    # Leer datos de normalized_financials (sin deuda por ahora)
    print("[INFO] Leyendo datos del warehouse...")

    cursor.execute("""
        SELECT ticker, year, month, industry,
               assets, equity, revenue, net_income, operating_income,
               current_assets, current_liabilities, cash,
               debt_short_term, debt_long_term, cost_of_sales, inventories
        FROM normalized_financials
        ORDER BY ticker, year
    """)

    rows = cursor.fetchall()
    print(f"[INFO] {len(rows)} períodos encontrados")

    # Calcular ratios
    calculated = 0
    updated = 0

    for row in rows:
        ticker, year, month, industry = row[0], row[1], row[2], row[3]

        # Calcular debt_total si existe
        debt_short = row[12] if len(row) > 12 else None
        debt_long = row[13] if len(row) > 13 else None
        debt_total = None
        if debt_short is not None and debt_long is not None:
            debt_total = debt_short + debt_long

        # Crear diccionario de campos
        data = {
            'assets': row[4],
            'equity': row[5],
            'revenue': row[6],
            'net_income': row[7],
            'operating_income': row[8],
            'current_assets': row[9],
            'current_liabilities': row[10],
            'cash': row[11],
            'debt_total': debt_total,
            'cost_of_sales': row[14] if len(row) > 14 else None,
            'inventories': row[15] if len(row) > 15 else None,
        }

        # Calcular ratios según industria
        ratios = {}
        qualities = {}

        for ratio_name, (req_industry, num_field, den_field) in RATIOS_TO_CALCULATE.items():
            # Verificar industria
            if industry != req_industry:
                continue

            numerator = data.get(num_field)
            denominator = data.get(den_field)

            value = calculate_ratio(numerator, denominator)
            quality = get_quality(numerator, denominator)

            if value is not None:
                ratios[ratio_name] = value
                qualities[f'{ratio_name}_quality'] = quality
                calculated += 1

        # Actualizar tabla de ratios
        if ratios:
            # Verificar si existe
            cursor.execute(
                "SELECT COUNT(*) FROM ratios WHERE ticker = ? AND year = ? AND month = ?",
                (ticker, year, month)
            )

            if cursor.fetchone()[0] > 0:
                # Actualizar
                set_clause = ', '.join([f"{k} = ?" for k in ratios.keys()])
                values = list(ratios.values()) + [ticker, year, month]
                cursor.execute(
                    f"UPDATE ratios SET {set_clause} WHERE ticker = ? AND year = ? AND month = ?",
                    values
                )
            else:
                # Insertar
                fields = ['ticker', 'year', 'month'] + list(ratios.keys())
                values = [ticker, year, month] + list(ratios.values())
                placeholders = ', '.join(['?' for _ in fields])
                field_names = ', '.join(fields)

                cursor.execute(
                    f"INSERT INTO ratios ({field_names}) VALUES ({placeholders})",
                    values
                )

            updated += 1

    con.commit()
    con.close()

    print()
    print("=" * 80)
    print(f"[OK] Ratios recalculados")
    print(f"  Ratios calculados: {calculated}")
    print(f"  Períodos actualizados: {updated}")
    print("=" * 80)


if __name__ == '__main__':
    recalculate_ratios()
