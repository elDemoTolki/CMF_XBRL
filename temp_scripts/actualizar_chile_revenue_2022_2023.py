"""
actualizar_chile_revenue_2022_2023.py - Actualiza CHILE.SN 2022-2023 con ingresos operacionales
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"

# Ingresos operacionales corregidos (en MM$)
INGRESOS_OPERACIONALES = {
    2023: {
        'revenue': 2997276,  # Valor corregido
    },
    2022: {
        'revenue': 3115793,  # Nuevo dato 2022
    },
}

def actualizar_chile():
    """Actualiza revenue de CHILE.SN"""

    print("=" * 100)
    print("ACTUALIZANDO CHILE.SN - INGRESOS OPERACIONALES (2022-2023)")
    print("Datos en MM$ (millones de pesos)")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    actualizados = 0

    for anno, datos in sorted(INGRESOS_OPERACIONALES.items()):
        year = anno
        revenue_mm = datos['revenue']

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
            continue

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
            actualizados += 1

        except Exception as e:
            con.rollback()
            print(f"  [ERROR] {e}")

    con.close()

    print()
    print("=" * 100)
    print(f"[OK] CHILE.SN actualizado: {actualizados} años")
    print("Ahora CHILE.SN tiene revenue para 2022-2025")
    print("Falta revenue para 2018-2021")
    print("=" * 100)

if __name__ == '__main__':
    actualizar_chile()
