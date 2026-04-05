"""
generar_ratios_simple.py - Genera ratios financieros sin pandas
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")

def generar_ratios():
    """Genera ratios financieros para todos los tickers y años"""

    print("=" * 140)
    print("RATIOS FINANCIEROS POR TICKER Y AÑO")
    print("=" * 140)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Obtener todos los tickers y años
    cursor.execute("""
        SELECT DISTINCT ticker, year
        FROM normalized_financials
        WHERE year >= 2018
        ORDER BY ticker, year
    """)

    registros = cursor.fetchall()

    if not registros:
        print("[ERROR] No hay datos en el warehouse")
        con.close()
        return

    # Agrupar por ticker
    tickers_data = {}
    for ticker, year in registros:
        if ticker not in tickers_data:
            tickers_data[ticker] = []
        tickers_data[ticker].append(year)

    # Procesar cada ticker
    for ticker in sorted(tickers_data.keys()):
        print(f"{ticker}:")
        print("-" * 140)

        for year in sorted(tickers_data[ticker]):
            # Obtener datos financieros
            cursor.execute("""
                SELECT assets, liabilities, equity, revenue, net_income
                FROM normalized_financials
                WHERE ticker = ? AND year = ?
            """, (ticker, year))

            row = cursor.fetchone()

            if not row:
                print(f"  {year}: SIN DATOS")
                continue

            assets, liab, equity, revenue, ni = row

            # Calcular ratios
            ratios = {}

            # Ratio de liquidez (Assets / Liabilities)
            if liab and liab != 0:
                ratios['liquidez'] = assets / liab
            else:
                ratios['liquidez'] = None

            # Ratio de endeudamiento (Liabilities / Assets)
            if assets and assets != 0:
                ratios['endeudamiento'] = liab / assets
            else:
                ratios['endeudamiento'] = None

            # Margen neto (Net Income / Revenue)
            if revenue and revenue != 0:
                ratios['margen_neto'] = ni / revenue
            else:
                ratios['margen_neto'] = None

            # ROE - Return on Equity (Net Income / Equity)
            if equity and equity != 0:
                ratios['roe'] = ni / equity
            else:
                ratios['roe'] = None

            # ROA - Return on Assets (Net Income / Assets)
            if assets and assets != 0:
                ratios['roa'] = ni / assets
            else:
                ratios['roa'] = None

            # Imprimir ratios
            print(f"  {year}:", end="")

            if ratios['liquidez'] is not None:
                print(f" Liq={ratios['liquidez']:.2f}", end="")
            else:
                print(f" Liq=N/A", end="")

            if ratios['endeudamiento'] is not None:
                print(f" End={ratios['endeudamiento']:.2%}", end="")
            else:
                print(f" End=N/A", end="")

            if ratios['margen_neto'] is not None:
                print(f" MN={ratios['margen_neto']:.2%}", end="")
            else:
                print(f" MN=N/A", end="")

            if ratios['roe'] is not None:
                print(f" ROE={ratios['roe']:.2%}", end="")
            else:
                print(f" ROE=N/A", end="")

            if ratios['roa'] is not None:
                print(f" ROA={ratios['roa']:.2%}", end="")
            else:
                print(f" ROA=N/A", end="")

            print()

        print()

    con.close()

    print("=" * 140)
    print("LEYENDA:")
    print("  Liq  = Ratio de liquidez (Assets / Liabilities)")
    print("  End  = Ratio de endeudamiento (Liabilities / Assets)")
    print("  MN   = Margen neto (Net Income / Revenue)")
    print("  ROE  = Return on Equity (Net Income / Equity)")
    print("  ROA  = Return on Assets (Net Income / Assets)")
    print("  N/A  = No aplicable (división por cero o datos faltantes)")
    print("=" * 140)

if __name__ == '__main__':
    generar_ratios()
