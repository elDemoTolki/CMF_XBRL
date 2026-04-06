"""
actualizar_chile_revenue_2018.py - Actualiza CHILE.SN 2018 con ingresos operacionales
COMPLETA CHILE.SN PARA ANÁLISIS M1-M5 (2018-2025)
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"

def actualizar_chile_2018():
    """Actualiza revenue de CHILE.SN 2018 - ÚLTIMO AÑO FALTANTE"""

    print("=" * 100)
    print("ACTUALIZANDO CHILE.SN 2018 - INGRESOS OPERACIONALES")
    print("ÚLTIMO AÑO FALTANTE PARA COMPLETAR 2018-2025")
    print("Datos en MM$ (millones de pesos)")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    year = 2018
    revenue_mm = 1873283  # Total Ingresos Operacionales 2018 en MM$

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
    print("¡CHILE.SN 2018 ACTUALIZADO!")
    print("CHILE.SN AHORA 100% COMPLETO PARA ANÁLISIS M1-M5 (2018-2025)")
    print("=" * 100)

if __name__ == '__main__':
    actualizar_chile_2018()
