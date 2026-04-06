"""
verificar_unidad_warehouse.py - Verifica qué unidad se usa en el warehouse
"""
import sqlite3

con = sqlite3.connect('output/warehouse.db')
cursor = con.cursor()

print("=" * 100)
print("VERIFICANDO UNIDAD DE MEDIDA EN WAREHOUSE")
print("=" * 100)
print()

# Verificar una empresa no-financiera con datos conocidos
# Por ejemplo, CAP.SN (no es banco)
cursor.execute("""
    SELECT ticker, year, assets, revenue
    FROM normalized_financials
    WHERE ticker = 'CAP.SN' AND year = 2024
""")

row = cursor.fetchone()

if row:
    ticker, year, assets, revenue = row
    print(f"{ticker} {year}:")
    print(f"  Assets:   {assets:,.0f}")
    print(f"  Revenue:  {revenue:,.0f}")
    print()

    # Según fuentes externas, CAP.SN tiene activos de aproximadamente 10-12 BILLONES de pesos
    # Si assets = 10,000,000,000,000 entonces está en pesos
    # Si assets = 10,000,000,000 entonces está en miles
    # Si assets = 10,000,000 entonces está en millones
    # Si assets = 10,000 entonces está en miles de millones

    print(f"Si estos valores corresponden a ~10-12 billones de pesos:")
    if assets > 1_000_000_000_000:  # > 1 billón
        print("  -> El warehouse está en PESOS (unidad base)")
    elif assets > 1_000_000_000:  # > 1,000 millones
        print("  -> El warehouse está en MILES de pesos")
    elif assets > 1_000_000:  # > 1 millón
        print("  -> El warehouse está en MILLONES de pesos")
    elif assets > 1_000:  # > 1 mil
        print("  -> El warehouse está en MILES DE MILLONES (MM$)")

print()

# Verificar CHILE.SN para comparar
cursor.execute("""
    SELECT ticker, year, assets, net_income
    FROM normalized_financials
    WHERE ticker = 'CHILE.SN' AND year = 2024
""")

row = cursor.fetchone()

if row:
    ticker, year, assets, ni = row
    print(f"{ticker} {year}:")
    print(f"  Assets:     {assets:,.0f}")
    print(f"  Net Income: {ni:,.0f}")
    print()
    print("  (Sabemos que CHILE.SN se cargó desde PDF en MM$ y se multiplicó por 1,000,000)")

print()
print("=" * 100)

con.close()
