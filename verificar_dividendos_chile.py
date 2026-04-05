"""
verificar_dividendos_chile.py - Verifica estado de dividendos CHILE.SN
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"

con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

cursor.execute("""
    SELECT year, dividends_paid, net_income
    FROM normalized_financials
    WHERE ticker = ? AND year BETWEEN 2018 AND 2025
    ORDER BY year
""", (TICKER,))

rows = cursor.fetchall()

print(f"{'Año':<6} {'Dividends':>20} {'Net Income':>25} {'Estado':<15}")
print("-" * 75)

for year, dividends, ni in rows:
    if dividends is None:
        div_str = "SIN dato"
    else:
        div_str = f"{dividends:,.0f}"

    ni_str = f"{ni:,.0f}" if ni else "0"

    estado = "CON dato" if dividends else "SIN dato"

    print(f"{year:<6} {div_str:>20} {ni_str:>25} {estado:<15}")

con.close()
