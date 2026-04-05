"""
cargar_pehuenche_2021.py - Inserta año 2021 de PEHUENCHE.SN
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "PEHUENCHE.SN"

def cargar_2021():
    """Inserta datos de 2021"""

    print("=" * 100)
    print("INSERTANDO PEHUENCHE.SN 2021")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Datos en M$ (miles de pesos)
    assets = 232099308 * 1_000
    liab = 86626803 * 1_000
    equity = 145472505 * 1_000
    revenue = 208152869 * 1_000
    ni = 104966173 * 1_000

    cursor.execute("""
        INSERT INTO normalized_financials
        (ticker, year, month, assets, liabilities, equity, revenue, net_income)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (TICKER, 2021, 12, assets, liab, equity, revenue, ni))

    con.commit()
    con.close()

    print("[OK] 2021 insertado")
    print()
    print("[OK] PEHUENCHE.SN ahora tiene datos 2021-2025 (5 años)")

if __name__ == '__main__':
    cargar_2021()
