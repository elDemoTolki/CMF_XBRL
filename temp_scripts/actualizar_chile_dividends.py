"""
actualizar_chile_dividends.py - Actualiza CHILE.SN con dividendos pagados
Datos extraídos del Estado de Flujos de Efectivo
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"

# Dividendos pagados desde Cash Flow Statement (en MM$)
DIVIDENDOS_PAGADOS = {
    2025: {
        'dividends_paid': 995380,  # Pago de dividendos acciones comunes 2025
    },
    2024: {
        'dividends_paid': 815932,  # Pago de dividendos acciones comunes 2024
    },
    2023: {
        'dividends_paid': 866929,  # Pago de dividendos acciones comunes 2023
    },
    2022: {
        'dividends_paid': 539827,  # Pago de dividendos acciones comunes 2022
    },
    2021: {
        'dividends_paid': 220271,  # Dividendos pagados 2021
    },
    2020: {
        'dividends_paid': 350538,  # Dividendos pagados 2020
    },
    2019: {
        'dividends_paid': 356311,  # Dividendos pagados 2019
    },
    2018: {
        'dividends_paid': 374079,  # Dividendos pagados 2018
    },
}

def actualizar_dividendos():
    """Actualiza dividends_paid de CHILE.SN"""

    print("=" * 100)
    print("ACTUALIZANDO CHILE.SN - DIVIDENDOS PAGADOS")
    print("Datos desde Estado de Flujos de Efectivo (en MM$)")
    print("=" * 100)
    print()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe {DB_PATH}")
        return

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    actualizados = 0
    errores = 0

    for anno, datos in sorted(DIVIDENDOS_PAGADOS.items()):
        print(f"\nAño {anno}:")
        print(f"  Dividendos pagados: {datos['dividends_paid']:,} MM$")

        # Verificar si existe registro
        cursor.execute("""
            SELECT month, dividends_paid, net_income
            FROM normalized_financials
            WHERE ticker = ? AND year = ?
        """, (TICKER, anno))

        row = cursor.fetchone()

        if not row:
            print(f"  [AVISO] No existe registro para {anno}")
            continue

        month, dividends_actual, ni_actual = row

        # Convertir de MM$ a miles de CLP (MM$ × 1,000,000 = CLP, / 1,000 = miles de CLP)
        dividends_clp = datos['dividends_paid'] * 1_000

        print(f"  Antes: Dividends={dividends_actual or 0:,.0f}, NI={ni_actual:,.0f}")

        # Calcular payout ratio nuevo
        payout_nuevo = dividends_clp / ni_actual if ni_actual else 0

        try:
            cursor.execute("""
                UPDATE normalized_financials
                SET dividends_paid = ?
                WHERE ticker = ? AND year = ? AND month = ?
            """, (dividends_clp, TICKER, anno, month))

            con.commit()

            # Verificar actualización
            cursor.execute("""
                SELECT dividends_paid, net_income
                FROM normalized_financials
                WHERE ticker = ? AND year = ?
            """, (TICKER, anno))

            new_vals = cursor.fetchone()
            print(f"  Después: Dividends={new_vals[0]:,.0f}, NI={new_vals[1]:,.0f}")
            print(f"  Payout Ratio: {payout_nuevo:.2%}")

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
    print(f"Años procesados: {len(DIVIDENDOS_PAGADOS)}")
    print(f"Registros actualizados: {actualizados}")
    print(f"Errores: {errores}")
    print()

    if actualizados > 0:
        print("[OK] CHILE.SN dividendos actualizados")
        print("Payout ratio ahora disponible para 2018-2025")
        print("CHILE.SN 100% COMPLETO")
    else:
        print("[ERROR] No se actualizaron datos")

if __name__ == '__main__':
    actualizar_dividendos()
