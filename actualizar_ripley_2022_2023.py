"""
actualizar_ripley_2022_2023.py - Actualiza datos de RIPLEY.SN para 2022-2023
Datos en miles de pesos chilenos (M$)
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "RIPLEY.SN"

# Datos extraídos (en M$ - miles de pesos chilenos)
DATOS_RIPLEY = {
    2023: {
        'assets': 2544688618,
        'liabilities': 1586889626,
        'equity': 957798992,
        'revenue': 1278733798,
        'net_income': -24052924,  # Pérdida
    },
    2022: {
        'assets': 2649000139,
        'liabilities': 1644515426,
        'equity': 1004484713,
        'revenue': 1395597383,
        'net_income': 58413677,  # Ganancia
    },
}

def actualizar_ripley():
    """Actualiza datos de RIPLEY.SN al warehouse"""

    print("=" * 100)
    print("ACTUALIZANDO DATOS DE RIPLEY.SN (2022-2023)")
    print("Datos en miles de pesos chilenos (M$)")
    print("=" * 100)
    print()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe {DB_PATH}")
        return

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    actualizados = 0
    errores = 0

    for anno, datos in sorted(DATOS_RIPLEY.items()):
        print(f"\nAño {anno}:")

        # Verificar si existe registro
        cursor.execute("""
            SELECT month, assets, liabilities, equity, revenue, net_income
            FROM normalized_financials
            WHERE ticker = ? AND year = ?
        """, (TICKER, anno))

        existing = cursor.fetchone()

        if not existing:
            print(f"  [AVISO] No existe registro para {anno}, insertando...")

            # Convertir de M$ a miles de CLP para warehouse
            assets_clp = datos['assets'] * 1_000
            liab_clp = datos['liabilities'] * 1_000
            equity_clp = datos['equity'] * 1_000
            revenue_clp = datos['revenue'] * 1_000
            ni_clp = datos['net_income'] * 1_000

            try:
                cursor.execute("""
                    INSERT INTO normalized_financials
                    (ticker, year, month, assets, liabilities, equity, revenue, net_income)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (TICKER, anno, 12, assets_clp, liab_clp, equity_clp, revenue_clp, ni_clp))

                con.commit()
                actualizados += 1
                print(f"  [OK] Insertado")

            except Exception as e:
                con.rollback()
                errores += 1
                print(f"  [ERROR] {e}")

        else:
            month, assets_actual, liab_actual, equity_actual, revenue_actual, ni_actual = existing

            print(f"  Antes: Assets={assets_actual:,.0f}, Liab={liab_actual:,.0f}, Equity={equity_actual:,.0f}, Revenue={revenue_actual:,.0f}, NI={ni_actual:,.0f}")

            # Convertir de M$ a miles de CLP para warehouse
            assets_clp = datos['assets'] * 1_000
            liab_clp = datos['liabilities'] * 1_000
            equity_clp = datos['equity'] * 1_000
            revenue_clp = datos['revenue'] * 1_000
            ni_clp = datos['net_income'] * 1_000

            try:
                cursor.execute("""
                    UPDATE normalized_financials
                    SET assets = ?, liabilities = ?, equity = ?, revenue = ?, net_income = ?
                    WHERE ticker = ? AND year = ? AND month = ?
                """, (assets_clp, liab_clp, equity_clp, revenue_clp, ni_clp, TICKER, anno, month))

                con.commit()

                # Verificar actualización
                cursor.execute("""
                    SELECT assets, liabilities, equity, revenue, net_income
                    FROM normalized_financials
                    WHERE ticker = ? AND year = ?
                """, (TICKER, anno))

                new_vals = cursor.fetchone()
                print(f"  Después: Assets={new_vals[0]:,.0f}, Liab={new_vals[1]:,.0f}, Equity={new_vals[2]:,.0f}, Revenue={new_vals[3]:,.0f}, NI={new_vals[4]:,.0f}")

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
    print(f"Años procesados: {len(DATOS_RIPLEY)}")
    print(f"Registros actualizados: {actualizados}")
    print(f"Errores: {errores}")
    print()

    if actualizados > 0:
        print("[OK] Datos de RIPLEY.SN 2022-2023 actualizados correctamente")
    else:
        print("[ERROR] No se actualizaron datos")

if __name__ == '__main__':
    actualizar_ripley()
