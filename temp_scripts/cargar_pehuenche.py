"""
cargar_pehuenche.py - Inserta datos de PEHUENCHE.SN desde datos extraídos de imágenes
Los datos están en M$ (miles de pesos chilenos) y se multiplican por 1,000 para el warehouse
"""

import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "PEHUENCHE.SN"

# Datos extraídos de imágenes (en M$ - miles de pesos chilenos)
DATOS_IMAGENES = {
    2025: {
        'assets': 246480000,         # 246,480 M$
        'liabilities': 92748000,     # 92,748 M$
        'equity': 153732000,         # 153,732 M$
        'revenue': 210419000,        # 210,419 M$
        'net_income': 140409000,     # 140,409 M$
    },
    2024: {
        'assets': 251332239,         # 251,332,239 M$
        'liabilities': 85817301,     # 85,817,301 M$
        'equity': 165514938,         # 165,514,938 M$
        'revenue': 249124750,        # 249,124,750 M$
        'net_income': 161809029,     # 161,809,029 M$
    },
    2023: {
        'assets': 246528003,         # 246,528,003 M$
        'liabilities': 86663122,     # 86,663,122 M$
        'equity': 159864881,         # 159,864,881 M$
        'revenue': 217717148,        # 217,717,148 M$
        'net_income': 147655728,     # 147,655,728 M$
    },
}

def cargar_pehuenche():
    """Inserta datos de PEHUENCHE.SN al warehouse"""

    print("=" * 100)
    print("CARGANDO DATOS DE PEHUENCHE.SN (2023-2025)")
    print("=" * 100)
    print()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe {DB_PATH}")
        return

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Verificar si PEHUENCHE ya existe
    cursor.execute("""
        SELECT COUNT(*)
        FROM normalized_financials
        WHERE ticker = ?
    """, (TICKER,))

    count = cursor.fetchone()[0]

    if count > 0:
        print(f"[INFO] PEHUENCHE.SN ya tiene {count} registros en el warehouse")
        print()

        # Mostrar años existentes
        cursor.execute("""
            SELECT DISTINCT year
            FROM normalized_financials
            WHERE ticker = ?
            ORDER BY year
        """, (TICKER,))

        existing_years = [row[0] for row in cursor.fetchall()]
        print(f"Años existentes: {existing_years}")
        print()

        # Filtrar años a insertar
        years_to_insert = [y for y in DATOS_IMAGENES.keys() if y not in existing_years]

        if not years_to_insert:
            print("[AVISO] Todos los años ya existen en el warehouse")
            print("¿Deseas actualizar los datos existentes? (Usar UPDATE en lugar de INSERT)")
            con.close()
            return
        else:
            print(f"Insertando años: {years_to_insert}")
            datos_a_cargar = {y: DATOS_IMAGENES[y] for y in years_to_insert}
    else:
        print("[INFO] PEHUENCHE.SN no existe en el warehouse")
        print("Insertando todos los años...")
        datos_a_cargar = DATOS_IMAGENES

    insertados = 0
    errores = 0

    for anno, datos in sorted(datos_a_cargar.items()):
        print(f"\nAño {anno}:")

        # Convertir de M$ a CLP (multiplicar por 1,000 para warehouse en miles)
        assets_clp = datos['assets'] * 1_000
        liab_clp = datos['liabilities'] * 1_000
        equity_clp = datos['equity'] * 1_000
        revenue_clp = datos['revenue'] * 1_000
        ni_clp = datos['net_income'] * 1_000

        print(f"  Valores en M$: A={datos['assets']:,}, L={datos['liabilities']:,}, E={datos['equity']:,}, R={datos['revenue']:,}, NI={datos['net_income']:,}")
        print(f"  Valores en CLP (×1,000): A={assets_clp:,}, L={liab_clp:,}, E={equity_clp:,}, R={revenue_clp:,}, NI={ni_clp:,}")

        try:
            cursor.execute("""
                INSERT INTO normalized_financials
                (ticker, year, month, assets, liabilities, equity, revenue, net_income)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (TICKER, anno, 12, assets_clp, liab_clp, equity_clp, revenue_clp, ni_clp))

            con.commit()
            insertados += 1
            print(f"  [OK] Insertado")

        except Exception as e:
            con.rollback()
            errores += 1
            print(f"  [ERROR] {e}")

    con.close()

    print()
    print("=" * 100)
    print("RESUMEN")
    print("=" * 100)
    print(f"Años procesados: {len(datos_a_cargar)}")
    print(f"Registros insertados: {insertados}")
    print(f"Errores: {errores}")
    print()

    if insertados > 0:
        print("[OK] Datos de PEHUENCHE.SN insertados correctamente")
        print(f"Ticker: {TICKER}")
        print(f"Años disponibles: {sorted(datos_a_cargar.keys())}")
    else:
        print("[ERROR] No se insertaron datos")

if __name__ == '__main__':
    cargar_pehuenche()
