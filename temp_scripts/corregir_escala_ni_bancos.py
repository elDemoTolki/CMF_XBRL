"""
corregir_escala_ni_bancos.py - Corrige escala de net_income para BCI, BSANTANDER, ITAUCL
PROBLEMA: net_income está en CLP en vez de miles de CLP (1,000x más grande)
SOLUCIÓN: Dividir net_income por 1,000
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
BANKS = ["BCI.SN", "BSANTANDER.SN", "ITAUCL.SN"]

def corregir_ni_bancos():
    """Corrige net_income dividiendo por 1,000"""

    print("=" * 100)
    print("CORRIGIENDO ESCALA DE NET_INCOME PARA BANCOS")
    print("Dividiendo net_income por 1,000 (CLP → miles de CLP)")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    total_corregidos = 0

    for ticker in BANKS:
        print(f"{ticker}:")
        print("-" * 100)

        cursor.execute("""
            SELECT year, net_income, dividends_paid
            FROM normalized_financials
            WHERE ticker = ? AND year BETWEEN 2018 AND 2025
            ORDER BY year DESC
        """, (ticker,))

        rows = cursor.fetchall()

        for year, ni, div in rows:
            if ni and ni > 0:
                ni_antiguo = ni
                ni_nuevo = ni / 1_000

                # Recalcular payout con net_income corregido
                payout_nuevo = (div / ni_nuevo * 100) if div and ni_nuevo else 0
                payout_viejo = (div / ni_antiguo * 100) if div and ni_antiguo else 0

                print(f"  {year}:")
                print(f"    NI antes: {ni_antiguo/1_000_000:,.1f}B CLP (escala incorrecta)")
                print(f"    NI después: {ni_nuevo/1_000_000:,.1f}B CLP (escala correcta)")
                print(f"    Payout antes: {payout_viejo:.2f}% → Payout después: {payout_nuevo:.2f}%")

                try:
                    cursor.execute("""
                        UPDATE normalized_financials
                        SET net_income = ?
                        WHERE ticker = ? AND year = ?
                    """, (ni_nuevo, ticker, year))

                    con.commit()
                    print(f"    [OK] Corregido")
                    total_corregidos += 1

                except Exception as e:
                    con.rollback()
                    print(f"    [ERROR] {e}")

        print()

    con.close()

    print("=" * 100)
    print("RESUMEN")
    print("=" * 100)
    print(f"Registros corregidos: {total_corregidos}")
    print()

    if total_corregidos > 0:
        print("[OK] Net income corregido")
        verificar_correccion()

def verificar_correccion():
    """Verifica que los corrección sea correcta"""

    print()
    print("=" * 100)
    print("VERIFICACIÓN DE CORRECCIÓN")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    print("Payout Ratios después de corrección:")
    print("-" * 100)
    print(f"{'Ticker':<15} {'Año':<6} {'Net Income (B CLP)':>20} {'Dividends (B CLP)':>20} {'Payout Ratio':<15}")
    print("-" * 100)

    for ticker in BANKS:
        cursor.execute("""
            SELECT year, net_income, dividends_paid
            FROM normalized_financials
            WHERE ticker = ? AND year IN (2022, 2023)
            ORDER BY year DESC
        """, (ticker,))

        rows = cursor.fetchall()

        for year, ni, div in rows:
            ni_b = ni / 1_000_000 if ni else 0
            div_b = div / 1_000_000 if div else 0
            payout = (div / ni * 100) if ni and div else 0

            estado = "OK" if 20 <= payout <= 80 else "REVISAR"
            print(f"{ticker:<15} {year:<6} {ni_b:>20,.1f} {div_b:>20,.1f} {payout:>14.2f}% ({estado})")

    con.close()

if __name__ == '__main__':
    corregir_ni_bancos()
