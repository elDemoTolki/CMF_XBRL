"""
corregir_chile_revenue.py - Corrige error de conversión en CHILE.SN revenue
PROBLEMA: Los datos de revenue están 1,000 veces más pequeños de lo debido
SOLUCIÓN: Multiplicar revenue por 1,000 para todos los años 2018-2025
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"

def corregir_chile_revenue():
    """Corrige revenue de CHILE.SN multiplicando por 1,000"""

    print("=" * 100)
    print("CORIGIENDO ERROR DE CONVERSIÓN EN CHILE.SN REVENUE")
    print("Multiplicando revenue por 1,000 (años 2018-2025)")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Obtener todos los años 2018-2025
    cursor.execute("""
        SELECT year, revenue, net_income, month
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
    for year, revenue, ni, month in rows:
        if revenue and revenue > 0:
            ratio = ni / revenue
            print(f"{year}: Revenue={revenue:,.0f}, NI={ni:,.0f}, Ratio NI/Rev={ratio:.2%}")
        else:
            print(f"{year}: Revenue={revenue or 0:,.0f}, NI={ni:,.0f}")

    print()
    print("APLICANDO CORRECCIÓN (× 1,000):")
    print("-" * 100)

    corregidos = 0
    errores = 0

    for year, revenue, ni, month in rows:
        if revenue and revenue > 0:
            revenue_antiguo = revenue
            revenue_nuevo = revenue * 1_000

            print(f"{year}:")
            print(f"  Antes: Revenue={revenue_antiguo:,.0f}")
            print(f"  Después: Revenue={revenue_nuevo:,.0f}")

            try:
                cursor.execute("""
                    UPDATE normalized_financials
                    SET revenue = ?
                    WHERE ticker = ? AND year = ? AND month = ?
                """, (revenue_nuevo, TICKER, year, month))

                con.commit()

                # Calcular nuevo ratio
                nuevo_ratio = ni / revenue_nuevo
                print(f"  Ratio NI/Rev corregido: {nuevo_ratio:.2%}")
                print(f"  [OK] Corregido")
                corregidos += 1

            except Exception as e:
                con.rollback()
                errores += 1
                print(f"  [ERROR] {e}")
        else:
            print(f"{year}: Revenue=0 (se omite)")

        print()

    con.close()

    print("=" * 100)
    print("RESUMEN DE CORRECCIÓN")
    print("=" * 100)
    print(f"Años corregidos: {corregidos}/8")
    print(f"Errores: {errores}")
    print()

    if corregidos > 0:
        print("[OK] CHILE.SN revenue corregido")
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

    # Comparar con 2017 (dato correcto de referencia)
    cursor.execute("""
        SELECT year, revenue, net_income
        FROM normalized_financials
        WHERE ticker = ? AND year BETWEEN 2017 AND 2025
        ORDER BY year
    """, (TICKER,))

    rows = cursor.fetchall()

    print("Comparación con 2017 (dato de referencia correcto):")
    print("-" * 100)
    print(f"{'Año':<6} {'Revenue (CLP)':>25} {'NI (CLP)':>20} {'Ratio NI/Rev':<12} {'Estado':<10}")
    print("-" * 100)

    for year, revenue, ni in rows:
        if revenue and revenue > 0:
            ratio = ni / revenue
            estado = "OK" if 10 <= ratio <= 60 else "REVISAR"
            print(f"{year:<6} {revenue:>25,.0f} {ni:>20,.0f} {ratio:>11.2%} {estado:<10}")
        else:
            print(f"{year:<6} {'Sin datos':>25} {ni:>20,.0f} {'N/A':>12}")

    print()
    print("CRITERIOS DE VALIDACIÓN:")
    print("-" * 100)
    print("✓ Ratio NI/Rev debe estar entre 10% y 60% (margen realista para banco)")
    print("✓ Revenue debe ser mayor que Net Income (margen < 100%)")
    print("✓ Valores deben estar en el mismo orden de magnitud que 2017")

    con.close()

if __name__ == '__main__':
    corregir_chile_revenue()
