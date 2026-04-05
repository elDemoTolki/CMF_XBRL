"""
actualizar_cap_2024_2025.py - Actualiza datos de CAP.SN para 2024-2025
Datos en MUS$ convertidos a CLP usando tipos de cambio al cierre
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CAP.SN"

# Tipos de cambio al cierre
TIPOS_CAMBIO = {
    2024: 992.12,  # CLP/USD al 30 Dic 2024
    2025: 911.18,  # CLP/USD al 30 Dic 2025
}

# Datos extraídos (en MUS$ - miles de dólares)
DATOS_CAP = {
    2025: {
        'assets': 6116224,
        'liabilities': 3098483,
        'equity': 3017741,
        'revenue': 1930033,
        'net_income': -98515,  # Pérdida
    },
    2024: {
        'assets': 6355771,
        'liabilities': 3169800,
        'equity': 3185971,
        'revenue': 1801367,
        'net_income': -408027,  # Pérdida
    },
}

def actualizar_cap():
    """Actualiza datos de CAP.SN al warehouse"""

    print("=" * 100)
    print("ACTUALIZANDO DATOS DE CAP.SN (2024-2025)")
    print("Datos originales en MUS$, convertidos a CLP")
    print("=" * 100)
    print()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe {DB_PATH}")
        return

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    actualizados = 0
    errores = 0

    for anno, datos in sorted(DATOS_CAP.items()):
        print(f"\nAño {anno}:")

        # Obtener tipo de cambio
        tc = TIPOS_CAMBIO[anno]
        print(f"  Tipo de cambio: {tc:.2f} CLP/USD")

        # Verificar si existe registro
        cursor.execute("""
            SELECT month, assets, liabilities, equity, revenue, net_income
            FROM normalized_financials
            WHERE ticker = ? AND year = ?
        """, (TICKER, anno))

        existing = cursor.fetchone()

        if not existing:
            print(f"  [AVISO] No existe registro para {anno}, insertando...")

            # Convertir de MUS$ a miles de CLP
            # MUS$ × tipo de cambio = miles de CLP
            assets_clp = int(datos['assets'] * tc)
            liab_clp = int(datos['liabilities'] * tc)
            equity_clp = int(datos['equity'] * tc)
            revenue_clp = int(datos['revenue'] * tc)
            ni_clp = int(datos['net_income'] * tc)

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

            # Convertir de MUS$ a miles de CLP
            # MUS$ × tipo de cambio = miles de CLP
            assets_clp = int(datos['assets'] * tc)
            liab_clp = int(datos['liabilities'] * tc)
            equity_clp = int(datos['equity'] * tc)
            revenue_clp = int(datos['revenue'] * tc)
            ni_clp = int(datos['net_income'] * tc)

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
    print(f"Años procesados: {len(DATOS_CAP)}")
    print(f"Registros actualizados: {actualizados}")
    print(f"Errores: {errores}")
    print()

    if actualizados > 0:
        print("[OK] Datos de CAP.SN 2024-2025 actualizados correctamente")
    else:
        print("[ERROR] No se actualizaron datos")

if __name__ == '__main__':
    actualizar_cap()
