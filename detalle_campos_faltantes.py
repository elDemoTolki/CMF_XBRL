"""
detalle_campos_faltantes.py - Muestra qué campos faltan en años recientes
"""
import sqlite3

con = sqlite3.connect('output/warehouse.db')
cursor = con.cursor()

tickers_problema = ['CAP.SN', 'ECL.SN', 'HITES.SN', 'MASISA.SN', 'RIPLEY.SN', 'SOCOVESA.SN', 'SQM-A.SN']
anios_criticos = [2023, 2024, 2025]

print("=" * 120)
print("DETALLE DE CAMPOS FALTANTES EN AÑOS RECIENTES (2023-2025)")
print("=" * 120)
print()

for ticker in tickers_problema:
    print(f"{ticker}:")
    print("-" * 120)

    for ano in anios_criticos:
        cursor.execute("""
            SELECT assets, liabilities, equity, revenue, net_income
            FROM normalized_financials
            WHERE ticker = ? AND year = ?
        """, (ticker, ano))

        row = cursor.fetchone()

        if not row:
            print(f"  {ano}: SIN DATOS")
            continue

        assets, liab, equity, revenue, ni = row

        # Determinar tipo
        es_banco = (revenue == 0)

        # Verificar campos
        campos_faltantes = []
        campos_ok = []

        if es_banco:
            # Banco requiere: assets, liab, equity, ni
            if assets > 0:
                campos_ok.append("assets")
            else:
                campos_faltantes.append("assets")

            if liab > 0:
                campos_ok.append("liab")
            else:
                campos_faltantes.append("liab")

            if equity > 0:
                campos_ok.append("equity")
            else:
                campos_faltantes.append("equity")

            if ni > 0:
                campos_ok.append("net_income")
            else:
                campos_faltantes.append("net_income")
        else:
            # Non-financial requiere: assets, liab, equity, revenue, ni
            if assets > 0:
                campos_ok.append("assets")
            else:
                campos_faltantes.append("assets")

            if liab > 0:
                campos_ok.append("liab")
            else:
                campos_faltantes.append("liab")

            if equity > 0:
                campos_ok.append("equity")
            else:
                campos_faltantes.append("equity")

            if revenue > 0:
                campos_ok.append("revenue")
            else:
                campos_faltantes.append("revenue")

            if ni > 0:
                campos_ok.append("net_income")
            else:
                campos_faltantes.append("net_income")

        if campos_faltantes:
            print(f"  {ano}: FALTAN {campos_faltantes} (OK: {campos_ok})")
        else:
            print(f"  {ano}: OK")

    print()

print("=" * 120)
print("LEYENDA:")
print("  FALTAN = Campos que están en 0 o NULL")
print("  OK = Todos los campos requeridos tienen datos")
print("=" * 120)

con.close()
