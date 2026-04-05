"""
actualizar_chile_revenue_2019.py - Actualiza CHILE.SN 2019 con ingresos operacionales
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"

def actualizar_chile_2019():
    """Actualiza revenue de CHILE.SN 2019"""

    print("=" * 100)
    print("ACTUALIZANDO CHILE.SN 2019 - INGRESOS OPERACIONALES")
    print("Datos en MM$ (millones de pesos)")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    year = 2019
    revenue_mm = 2014520  # Total Ingresos Operacionales 2019 en MM$

    print(f"Año {year}:")
    print(f"  TOTAL INGRESOS OPERACIONALES: {revenue_mm:,} MM$")

    # Verificar registro actual
    cursor.execute("""
        SELECT month, revenue, net_income
        FROM normalized_financials
        WHERE ticker = ? AND year = ?
    """, (TICKER, year))

    row = cursor.fetchone()

    if not row:
        print("  [ERROR] No existe registro")
        con.close()
        return

    month, revenue_actual, ni_actual = row
    print(f"  Antes: Revenue={revenue_actual or 0:,.0f}, NI={ni_actual:,.0f}")

    # Convertir de MM$ a miles de CLP
    revenue_clp = revenue_mm * 1_000

    try:
        cursor.execute("""
            UPDATE normalized_financials
            SET revenue = ?
            WHERE ticker = ? AND year = ? AND month = ?
        """, (revenue_clp, TICKER, year, month))

        con.commit()

        # Verificar actualización
        cursor.execute("""
            SELECT revenue, net_income
            FROM normalized_financials
            WHERE ticker = ? AND year = ?
        """, (TICKER, year))

        new_vals = cursor.fetchone()
        print(f"  Después: Revenue={new_vals[0]:,.0f}, NI={new_vals[1]:,.0f}")

        # Calcular margen neto
        if new_vals[0] and new_vals[0] > 0:
            margen_neto = new_vals[1] / new_vals[0]
            print(f"  Margen Neto: {margen_neto:.2%}")

        print("  [OK] Actualizado")

    except Exception as e:
        con.rollback()
        print(f"  [ERROR] {e}")

    con.close()

    print()
    print("=" * 100)
    print("[OK] CHILE.SN 2019 actualizado con ingresos operacionales")
    print("Ahora CHILE.SN tiene revenue para 2019-2025")
    print("Falta revenue para 2018")
    print("=" * 100)

if __name__ == '__main__':
    actualizar_chile_2019()
