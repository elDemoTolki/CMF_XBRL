"""
cargar_pehuenche_2020.py - Inserta año 2020 de PEHUENCHE.SN
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "PEHUENCHE.SN"

def cargar_2020():
    """Inserta datos de 2020"""

    print("=" * 100)
    print("INSERTANDO PEHUENCHE.SN 2020")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Datos en M$ (miles de pesos)
    assets = 223605612 * 1_000
    liab = 86048171 * 1_000
    equity = 137557441 * 1_000
    revenue = 162555069 * 1_000
    ni = 87102068 * 1_000

    cursor.execute("""
        INSERT INTO normalized_financials
        (ticker, year, month, assets, liabilities, equity, revenue, net_income)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (TICKER, 2020, 12, assets, liab, equity, revenue, ni))

    con.commit()
    con.close()

    print("[OK] 2020 insertado")
    print()
    print("[OK] PEHUENCHE.SN ahora tiene datos 2020-2025 (6 años)")

if __name__ == '__main__':
    cargar_2020()
