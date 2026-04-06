"""
corregir_chile_net_income.py - Corrige error de escala en net_income de CHILE.SN
PROBLEMA: net_income 2018-2025 está 1,000 veces más grande de lo debido
SOLUCIÓN: Dividir net_income por 1,000 para años 2018-2025
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"

def corregir_net_income():
    """Corrige net_income de CHILE.SN dividiendo por 1,000"""

    print("=" * 100)
    print("CORRIGIENDO ERROR DE ESCALA EN CHILE.SN NET_INCOME")
    print("Dividiendo net_income por 1,000 (años 2018-2025)")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Obtener años 2018-2025
    cursor.execute("""
        SELECT year, net_income, dividends_paid, month
        FROM normalized_financials
        WHERE ticker = ? AND year BETWEEN 2018 AND 2025
        ORDER BY year
    """, (TICKER,))

    rows = cursor.fetchall()

    if not rows:
        print("[ERROR] No hay datos para corregir")
        con.close()
        return

    print("VERIFICACIÓN ANTES DE LA CORRECCIÓN:")
    print("-" * 100)
    for year, ni, div, month in rows:
        ni_b = ni / 1_000_000 if ni else 0
        payout = (div / ni * 100) if ni and div else 0
        print(f"{year}: NI={ni_b:>12,.1f}B CLP | Div={div/1_000_000:>8,.1f}B CLP | Payout={payout:>6.2f}%")

    print()
    print("APLICANDO CORRECCIÓN (÷ 1,000):")
    print("-" * 100)

    corregidos = 0
    errores = 0

    for year, ni, div, month in rows:
        if ni and ni > 0:
            ni_antiguo = ni
            ni_nuevo = ni / 1_000

            # Recalcular payout ratio correcto
            payout_nuevo = (div / ni_nuevo * 100) if div and ni_nuevo else 0

            print(f"{year}:")
            print(f"  Antes: NI={ni_antiguo/1_000_000:>12,.1f}B CLP")
            print(f"  Después: NI={ni_nuevo/1_000_000:>12,.1f}B CLP")
            print(f"  Payout Ratio corregido: {payout_nuevo:>6.2f}%")

            try:
                cursor.execute("""
                    UPDATE normalized_financials
                    SET net_income = ?
                    WHERE ticker = ? AND year = ? AND month = ?
                """, (ni_nuevo, TICKER, year, month))

                con.commit()
                print(f"  [OK] Corregido")
                corregidos += 1

            except Exception as e:
                con.rollback()
                errores += 1
                print(f"  [ERROR] {e}")
        else:
            print(f"{year}: NI=0 (se omite)")

        print()

    con.close()

    print("=" * 100)
    print("RESUMEN DE CORRECCIÓN")
    print("=" * 100)
    print(f"Años corregidos: {corregidos}/8")
    print(f"Errores: {errores}")
    print()

    if corregidos > 0:
        print("[OK] CHILE.SN net_income corregido")
        print("Verificando consistencia de datos...")
        verificar_consistencia()

def verificar_consistencia():
    """Verifica que los datos corregidos sean consistentes"""

    print()
    print("=" * 100)
    print("VERIFICACIÓN DE CONSISTENCIA DE DATOS CORREGIDOS")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Comparar payout ratios corregidos
    cursor.execute("""
        SELECT year, net_income, dividends_paid
        FROM normalized_financials
        WHERE ticker = ? AND year BETWEEN 2017 AND 2025
        ORDER BY year
    """, (TICKER,))

    rows = cursor.fetchall()

    print("Payout Ratios corregidos:")
    print("-" * 100)
    print(f"{'Año':<6} {'Net Income (B CLP)':>20} {'Dividends (B CLP)':>20} {'Payout Ratio':<15}")
    print("-" * 100)

    for year, ni, div in rows:
        ni_b = ni / 1_000_000 if ni else 0
        div_b = div / 1_000_000 if div else 0
        payout = (div / ni * 100) if ni and div else 0

        estado = "OK" if 20 <= payout <= 80 else "REVISAR"
        print(f"{year:<6} {ni_b:>20,.1f} {div_b:>20,.1f} {payout:>14.2f}% ({estado})")

    print()
    print("CRITERIOS DE VALIDACIÓN:")
    print("-" * 100)
    print("✓ Payout Ratio debe estar entre 20% y 80% para banco")
    print("✓ Net Income debe estar en orden de decenas de miles de millones (30-50B)")
    print("✓ Dividends deben estar en orden de miles de millones (0.5-20B)")

    con.close()

if __name__ == '__main__':
    corregir_net_income()
