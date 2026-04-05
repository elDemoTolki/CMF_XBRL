"""
cargar_zofri.py - Inserta datos de ZOFRI.SN (2024-2025)
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "ZOFRI.SN"

# Datos extraídos (en miles de pesos)
DATOS_ZOFRI = {
    2025: {
        'assets': 134620318,
        'liabilities': 75584890,
        'equity': 59035428,
        'revenue': 56982201,
        'net_income': 19956447,
    },
    2024: {
        'assets': 135796404,
        'liabilities': 80928814,
        'equity': 54867590,
        'revenue': 50465567,
        'net_income': 18505355,
    },
    2023: {
        'assets': 137698329,
        'liabilities': 83091522,
        'equity': 54606807,
        'revenue': 48224809,
        'net_income': 17734528,
    },
    2022: {
        'assets': 131433848,
        'liabilities': 80510273,
        'equity': 50923575,
        'revenue': 43026895,
        'net_income': 16572997,
    },
    2021: {
        'assets': 126543647,
        'liabilities': 70892108,
        'equity': 55651539,
        'revenue': 38907730,
        'net_income': 16050131,
    },
    2020: {
        'assets': 117891434,
        'liabilities': 70285395,
        'equity': 47606039,
        'revenue': 28763892,
        'net_income': 6305398,
    },
    2019: {
        'assets': 115132643,
        'liabilities': 65926714,
        'equity': 49205929,
        'revenue': 38514852,
        'net_income': 11974685,
    },
    2018: {
        'assets': 114542525,
        'liabilities': 65937567,
        'equity': 48604958,
        'revenue': 39471289,
        'net_income': 15562618,
    },
}

def cargar_zofri():
    """Inserta datos de ZOFRI.SN al warehouse"""

    print("=" * 100)
    print("CARGANDO DATOS DE ZOFRI.SN (2018-2025)")
    print("=" * 100)
    print()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe {DB_PATH}")
        return

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    # Verificar si ZOFRI ya existe
    cursor.execute("""
        SELECT COUNT(*)
        FROM normalized_financials
        WHERE ticker = ?
    """, (TICKER,))

    count = cursor.fetchone()[0]

    if count > 0:
        print(f"[INFO] ZOFRI.SN ya tiene {count} registros en el warehouse")

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
        years_to_insert = [y for y in DATOS_ZOFRI.keys() if y not in existing_years]

        if not years_to_insert:
            print("[AVISO] Todos los años ya existen en el warehouse")
            con.close()
            return
        else:
            print(f"Insertando años: {years_to_insert}")
            datos_a_cargar = {y: DATOS_ZOFRI[y] for y in years_to_insert}
    else:
        print("[INFO] ZOFRI.SN no existe en el warehouse")
        print("Insertando todos los años...")
        datos_a_cargar = DATOS_ZOFRI

    insertados = 0
    errores = 0

    for anno, datos in sorted(datos_a_cargar.items()):
        print(f"\nAño {anno}:")

        # Convertir de miles de pesos a CLP (multiplicar por 1,000 para warehouse en miles)
        assets_clp = datos['assets'] * 1_000
        liab_clp = datos['liabilities'] * 1_000
        equity_clp = datos['equity'] * 1_000
        revenue_clp = datos['revenue'] * 1_000
        ni_clp = datos['net_income'] * 1_000

        print(f"  Valores en miles: A={datos['assets']:,}, L={datos['liabilities']:,}, E={datos['equity']:,}, R={datos['revenue']:,}, NI={datos['net_income']:,}")

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
        print("[OK] Datos de ZOFRI.SN insertados correctamente")
        print(f"Ticker: {TICKER}")
        print(f"Años disponibles: {sorted(datos_a_cargar.keys())}")

if __name__ == '__main__':
    cargar_zofri()
