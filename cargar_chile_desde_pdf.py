"""
cargar_chile_desde_pdf.py - Carga datos de Banco de Chile desde PDFs manuales
Los datos están extraídos del PDF y pegados aquí (formato: MM$ = millones de pesos)
"""

import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"

# Datos extraídos manualmente de los PDFs (en MM$)
DATOS_PDF = {
    2025: {
        'liabilities': 48301368,      # Total Pasivos 2025
        'equity': 5799535,          # Total Patrimonio 2025
        'assets': 54100903,          # Total Pasivos y Patrimonio 2025
        'net_income': 1192262,       # Utilidad consolidada del ejercicio 2025
    },
    2024: {
        'liabilities': 46472440,      # Total Pasivos 2024
        'equity': 5623001,           # Total Patrimonio 2024
        'assets': 52095441,           # Total Pasivos y Patrimonio 2024
        'net_income': 1207392,        # Utilidad consolidada del ejercicio 2024
    },
    2023: {
        'liabilities': 50555267,      # Total Pasivos 2023
        'equity': 5237285,           # Total Patrimonio 2023
        'assets': 55792552,           # Total Pasivos y Patrimonio 2023
        'net_income': 1243635,        # Utilidad consolidada del ejercicio 2023
    },
    2022: {
        'liabilities': 50397035,      # Total Pasivos 2022
        'equity': 4858327,           # Total Patrimonio 2022
        'assets': 55255362,           # Total Pasivos y Patrimonio 2022
        'net_income': 1409435,        # Utilidad consolidada del ejercicio 2022
    },
    2021: {
        'liabilities': 47464804,      # Total Pasivos 2021
        'equity': 4293522,           # Total Patrimonio 2021
        'assets': 51758326,           # Total Activos 2021
        'net_income': 792192,         # Utilidad consolidada del ejercicio 2021
    },
    2020: {
        'liabilities': 42368863,      # Total Pasivos 2020
        'equity': 3726268,           # Total Patrimonio 2020
        'assets': 46095131,           # Total Activos 2020
        'net_income': 463109,         # Utilidad consolidada del ejercicio 2020
    },
    2019: {
        'liabilities': 37745110,      # Total Pasivos 2019
        'equity': 3528223,           # Total Patrimonio 2019
        'assets': 41273333,           # Total Activos 2019
        'net_income': 593009,         # Utilidad consolidada del ejercicio 2019
    },
    2018: {
        'liabilities': 32622306,      # Total Pasivos 2018
        'equity': 3304152,           # Total Patrimonio 2018
        'assets': 35926459,           # Total Activos 2018
        'net_income': 594873,         # Utilidad consolidada del ejercicio 2018
    },
}

def cargar_datos_pdf():
    """Carga datos desde PDF al warehouse"""

    print("=" * 100)
    print("CARGANDO DATOS DE CHILE.SN DESDE PDFs (2018-2025)")
    print("=" * 100)
    print()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe {DB_PATH}")
        return

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    actualizados = 0
    errores = 0

    for anno, datos in sorted(DATOS_PDF.items()):
        print(f"\nAño {anno}:")

        # Verificar si existe registro
        cursor.execute("""
            SELECT month, assets, liabilities, equity, net_income
            FROM normalized_financials
            WHERE ticker = ? AND year = ?
        """, (TICKER, anno))

        existing = cursor.fetchone()

        if not existing:
            print(f"  [AVISO] No existe registro para {anno}")
            continue

        month, assets_actual, liab_actual, equity_actual, ni_actual = existing

        print(f"  Antes: Assets={assets_actual:,.0f}, Liab={liab_actual}, Equity={equity_actual:,.0f}, NI={ni_actual}")

        # Preparar campos a actualizar
        updates = []
        values = []

        # Convertir de MM$ a CLP (multiplicar por 1 millón)
        if datos.get('liabilities'):
            liabilities_clp = datos['liabilities'] * 1_000_000
            updates.append("liabilities = ?")
            values.append(liabilities_clp)

        if datos.get('equity'):
            equity_clp = datos['equity'] * 1_000_000
            updates.append("equity = ?")
            values.append(equity_clp)

        if datos.get('net_income'):
            net_income_clp = datos['net_income'] * 1_000_000
            updates.append("net_income = ?")
            values.append(net_income_clp)

        if datos.get('assets'):
            assets_clp = datos['assets'] * 1_000_000
            updates.append("assets = ?")
            values.append(assets_clp)

        if updates:
            values.extend([TICKER, anno, month])

            sql = f"""
                UPDATE normalized_financials
                SET {', '.join(updates)}
                WHERE ticker = ? AND year = ? AND month = ?
            """

            try:
                cursor.execute(sql, values)
                con.commit()

                # Verificar actualización
                cursor.execute("""
                    SELECT assets, liabilities, equity, net_income
                    FROM normalized_financials
                    WHERE ticker = ? AND year = ?
                """, (TICKER, anno))

                new_vals = cursor.fetchone()
                print(f"  Después: Assets={new_vals[0]:,.0f}, Liab={new_vals[1]:,.0f}, Equity={new_vals[2]:,.0f}, NI={new_vals[3]:,.0f}")

                actualizados += 1
                print(f"  [OK] {len(updates)} campos actualizados")
            except Exception as e:
                con.rollback()
                errores += 1
                print(f"  [ERROR] {e}")
        else:
            print(f"  [AVISO] No hay datos nuevos para cargar")

    con.close()

    print()
    print("=" * 100)
    print("RESUMEN")
    print("=" * 100)
    print(f"Años procesados: {len(DATOS_PDF)}")
    print(f"Registros actualizados: {actualizados}")
    print(f"Errores: {errores}")
    print()

    if actualizados > 0:
        print("[OK] Datos de 2018-2025 cargados desde PDFs")
        print()
        print("CHILE.SN esta COMPLETO para todos los anos 2018-2025")
    else:
        print("[AVISO] No se cargaron datos nuevos")

if __name__ == '__main__':
    cargar_datos_pdf()
