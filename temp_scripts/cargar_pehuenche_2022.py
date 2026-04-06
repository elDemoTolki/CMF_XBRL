"""
cargar_pehuenche_2022.py - Inserta año 2022 de PEHUENCHE.SN
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "PEHUENCHE.SN"

def cargar_2022():
    """Inserta datos de 2022"""

    print("=" * 100)
    print("INSERTANDO PEHUENCHE.SN 2022")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Verificar si ya existe 2022
    cursor.execute("""
        SELECT COUNT(*)
        FROM normalized_financials
        WHERE ticker = ? AND year = 2022
    """, (TICKER,))

    exists = cursor.fetchone()[0] > 0

    if exists:
        print("[AVISO] 2022 ya existe. Actualizando...")

        # Datos en M$ (miles de pesos)
        assets = 310220075 * 1_000
        liab = 135582221 * 1_000
        equity = 174637854 * 1_000
        revenue = 272441946 * 1_000
        ni = 186909221 * 1_000

        cursor.execute("""
            UPDATE normalized_financials
            SET assets = ?, liabilities = ?, equity = ?, revenue = ?, net_income = ?
            WHERE ticker = ? AND year = 2022
        """, (assets, liab, equity, revenue, ni, TICKER))

        print(f"[OK] 2022 actualizado")

    else:
        print("[INFO] Insertando 2022...")

        # Datos en M$ (miles de pesos)
        assets = 310220075 * 1_000
        liab = 135582221 * 1_000
        equity = 174637854 * 1_000
        revenue = 272441946 * 1_000
        ni = 186909221 * 1_000

        cursor.execute("""
            INSERT INTO normalized_financials
            (ticker, year, month, assets, liabilities, equity, revenue, net_income)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (TICKER, 2022, 12, assets, liab, equity, revenue, ni))

        print(f"[OK] 2022 insertado")

    con.commit()
    con.close()

    print()
    print("[OK] PEHUENCHE.SN ahora tiene datos 2022-2025")

if __name__ == '__main__':
    cargar_2022()
