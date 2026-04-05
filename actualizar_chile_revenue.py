"""
actualizar_chile_revenue.py - Actualiza CHILE.SN con ingresos operacionales (revenue)
Datos en MM$ (millones de pesos) desde estados de resultados
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"

# Ingresos operacionales extraídos del estado de resultados (en MM$)
INGRESOS_OPERACIONALES = {
    2025: {
        'revenue': 3026043,  # Total Ingresos Operacionales 2025 en MM$
    },
    2024: {
        'revenue': 3056285,  # Total Ingresos Operacionales 2024 en MM$
    },
}

def actualizar_chile_revenue():
    """Actualiza revenue de CHILE.SN al warehouse"""

    print("=" * 100)
    print("ACTUALIZANDO CHILE.SN - INGRESOS OPERACIONALES (REVENUE)")
    print("Datos en MM$ (millones de pesos) desde estados de resultados")
    print("=" * 100)
    print()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe {DB_PATH}")
        return

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    actualizados = 0
    errores = 0

    for anno, datos in sorted(INGRESOS_OPERACIONALES.items()):
        print(f"\nAño {anno}:")

        # Verificar si existe registro
        cursor.execute("""
            SELECT month, revenue, net_income
            FROM normalized_financials
            WHERE ticker = ? AND year = ?
        """, (TICKER, anno))

        existing = cursor.fetchone()

        if not existing:
            print(f"  [AVISO] No existe registro para {anno}")
            continue

        month, revenue_actual, ni_actual = existing

        print(f"  Antes: Revenue={revenue_actual or 0:,.0f}, NI={ni_actual or 0:,.0f}")

        # Convertir de MM$ a miles de CLP para warehouse
        # MM$ × 1,000,000 = CLP, luego / 1,000 = miles de CLP
        # Simplificando: MM$ × 1,000 = miles de CLP
        revenue_clp = datos['revenue'] * 1_000

        try:
            cursor.execute("""
                UPDATE normalized_financials
                SET revenue = ?
                WHERE ticker = ? AND year = ? AND month = ?
            """, (revenue_clp, TICKER, anno, month))

            con.commit()

            # Verificar actualización
            cursor.execute("""
                SELECT revenue, net_income
                FROM normalized_financials
                WHERE ticker = ? AND year = ?
            """, (TICKER, anno))

            new_vals = cursor.fetchone()
            print(f"  Después: Revenue={new_vals[0]:,.0f}, NI={new_vals[1]:,.0f}")

            # Calcular margen neto
            if new_vals[0] and new_vals[0] > 0:
                margen_neto = new_vals[1] / new_vals[0]
                print(f"  Margen Neto: {margen_neto:.2%}")

            actualizados += 1
            print(f"  [OK] Actualizado")

        except Exception as e:
            con.rollback()
            errores += 1
            print(f"  [ERROR] {e}")

    con.close()

    print()
    print("=" * 100)
    print("RESUMEN")
    print("=" * 100)
    print(f"Años procesados: {len(INGRESOS_OPERACIONALES)}")
    print(f"Registros actualizados: {actualizados}")
    print(f"Errores: {errores}")
    print()

    if actualizados > 0:
        print("[OK] CHILE.SN ahora COMPLETO para análisis M1-M5")
        print("Ingresos operacionales agregados como revenue para 2024-2025")
    else:
        print("[ERROR] No se actualizaron datos")

if __name__ == '__main__':
    actualizar_chile_revenue()
