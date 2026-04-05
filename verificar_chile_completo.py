"""
verificar_chile_completo.py - Verifica datos completos de CHILE.SN
"""
import sqlite3

con = sqlite3.connect('output/warehouse.db')
cursor = con.cursor()

print("=" * 100)
print("CHILE.SN - ESTADO DE DATOS 2018-2025")
print("=" * 100)
print()

cursor.execute("""
    SELECT year, month,
           CASE WHEN assets > 0 THEN 'X' ELSE NULL END as assets,
           CASE WHEN liabilities > 0 THEN 'X' ELSE NULL END as liab,
           CASE WHEN equity > 0 THEN 'X' ELSE NULL END as equity,
           CASE WHEN revenue > 0 THEN 'X' ELSE NULL END as revenue,
           CASE WHEN net_income > 0 THEN 'X' ELSE NULL END as ni
    FROM normalized_financials
    WHERE ticker = 'CHILE.SN' AND year BETWEEN 2018 AND 2025
    ORDER BY year
""")

rows = cursor.fetchall()

print("Año    Mes  Assets  Liab  Equity  Revenue  NetIncome")
print("-" * 60)

for row in rows:
    year, month, assets, liab, equity, revenue, ni = row
    print(f"{year}  {month:>3}  {assets or '':<6} {liab or '':<5} {equity or '':<7} {revenue or '':<7} {ni or '':<9}")

print()

# Contar campos completos
cursor.execute("""
    SELECT
        COUNT(CASE WHEN assets > 0 THEN 1 END) as assets_count,
        COUNT(CASE WHEN liabilities > 0 THEN 1 END) as liab_count,
        COUNT(CASE WHEN equity > 0 THEN 1 END) as equity_count,
        COUNT(CASE WHEN revenue > 0 THEN 1 END) as revenue_count,
        COUNT(CASE WHEN net_income > 0 THEN 1 END) as ni_count
    FROM normalized_financials
    WHERE ticker = 'CHILE.SN' AND year BETWEEN 2018 AND 2025
""")

counts = cursor.fetchone()
assets_count, liab_count, equity_count, revenue_count, ni_count = counts

print("=" * 100)
print("RESUMEN 2018-2025:")
print("=" * 100)
print(f"  Assets:       {assets_count}/8 años")
print(f"  Liabilities:  {liab_count}/8 años")
print(f"  Equity:       {equity_count}/8 años")
print(f"  Revenue:      {revenue_count}/8 años")
print(f"  Net Income:   {ni_count}/8 años")
print()

# Verificar si está completo
banco_completo = (
    assets_count >= 8 and
    liab_count >= 8 and
    equity_count >= 8 and
    ni_count >= 8
)

if banco_completo:
    print("[OK] CHILE.SN esta COMPLETO para 2018-2025")
    print("    (Bancos no requieren revenue)")
else:
    print("[AVISO] CHILE.SN INCOMPLETO")

print()
con.close()
