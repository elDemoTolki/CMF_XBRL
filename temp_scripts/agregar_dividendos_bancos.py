"""
agregar_dividendos_bancos.py - Agrega dividends_paid para bancos desde StockAnalysis.com
DATOS: dividend_per_share y shares_outstanding desde StockAnalysis.com
CÁLCULO: dividends_paid = dividend_per_share × shares_outstanding
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")

# Datos desde StockAnalysis.com
# dividend_per_share en CLP, shares_outstanding en millones
BANK_DIVIDEND_DATA = {
    "BCI.SN": {
        "shares_outstanding": 188_000_000,  # 188M shares
        "dividends": {
            2023: 1000.000,  # CLP per share
            2022: 1329.163,
        }
    },
    "BSANTANDER.SN": {
        "shares_outstanding": 188_446_000,  # 188.446M shares
        "dividends": {
            2023: 1.844,  # CLP per share
            2022: 2.575,
        }
    },
    "ITAUCL.SN": {
        "shares_outstanding": 216_000_000,  # 216M shares
        "dividends": {
            2023: 492.122,  # CLP per share
            2022: 601.489,
        }
    }
}

def agregar_dividendos_bancos():
    """Agrega dividends_paid calculado desde dividend_per_share × shares_outstanding"""

    print("=" * 100)
    print("AGREGANDO dividends_paid PARA BANCOS DESDE STOCKANALYSIS.COM")
    print("Fórmula: dividends_paid = dividend_per_share × shares_outstanding")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    total_agregados = 0
    total_errores = 0

    for ticker, data in BANK_DIVIDEND_DATA.items():
        shares = data["shares_outstanding"]
        dividends = data["dividends"]

        print(f"{ticker}:")
        print(f"  Shares outstanding: {shares:,}")
        print()

        for year, div_per_share in dividends.items():
            # Calcular dividends_total en CLP
            dividends_total = div_per_share * shares

            # Convertir a miles de CLP (unidad del warehouse)
            dividends_paid_miles = dividends_total / 1_000

            print(f"  {year}:")
            print(f"    Dividend per share: {div_per_share:,.3f} CLP")
            print(f"    Dividends total: {dividends_total:,.0f} CLP = {dividends_total/1_000_000:,.1f}B CLP")
            print(f"    Warehouse (miles CLP): {dividends_paid_miles:,.0f}")

            # Verificar si ya existe
            cursor.execute("""
                SELECT dividends_paid, net_income FROM normalized_financials
                WHERE ticker = ? AND year = ?
            """, (ticker, year))

            existing = cursor.fetchone()

            if existing:
                div_existente, ni = existing
                if div_existente:
                    print(f"    [YA EXISTE] dividends_paid={div_existente/1_000_000:,.1f}B CLP (se omite)")
                    print()
                    continue
                else:
                    # Calcular payout ratio
                    payout = (dividends_total / ni * 100) if ni else 0
                    print(f"    Payout ratio: {payout:.2f}%")

            # Insertar o actualizar
            try:
                cursor.execute("""
                    UPDATE normalized_financials
                    SET dividends_paid = ?
                    WHERE ticker = ? AND year = ?
                """, (dividends_paid_miles, ticker, year))

                con.commit()
                print(f"    [OK] Agregado")
                total_agregados += 1

            except Exception as e:
                con.rollback()
                total_errores += 1
                print(f"    [ERROR] {e}")

            print()

    con.close()

    print("=" * 100)
    print("RESUMEN")
    print("=" * 100)
    print(f"Registros agregados: {total_agregados}")
    print(f"Errores: {total_errores}")
    print()

    if total_agregados > 0:
        print("[OK] Datos de dividendos agregados")
        print("Verificando consistencia...")
        verificar_dividendos_agregados()

def verificar_dividendos_agregados():
    """Verifica los dividendos agregados"""

    print()
    print("=" * 100)
    print("VERIFICACIÓN DE DIVIDENDOS AGREGADOS")
    print("=" * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    for ticker in BANK_DIVIDEND_DATA.keys():
        cursor.execute("""
            SELECT year, net_income, dividends_paid
            FROM normalized_financials
            WHERE ticker = ? AND year IN (2022, 2023)
            ORDER BY year DESC
        """, (ticker,))

        rows = cursor.fetchall()

        if rows:
            print(f"{ticker}:")
            print(f"{'Año':<6} {'Net Income (B CLP)':>20} {'Dividends (B CLP)':>20} {'Payout Ratio':<15}")
            print("-" * 70)

            for year, ni, div in rows:
                ni_b = ni / 1_000_000 if ni else 0
                div_b = div / 1_000_000 if div else 0
                payout = (div / ni * 100) if ni and div else 0

                estado = "OK" if 20 <= payout <= 80 else "REVISAR"
                print(f"{year:<6} {ni_b:>20,.1f} {div_b:>20,.1f} {payout:>14.2f}% ({estado})")

            print()

    con.close()

if __name__ == '__main__':
    agregar_dividendos_bancos()
