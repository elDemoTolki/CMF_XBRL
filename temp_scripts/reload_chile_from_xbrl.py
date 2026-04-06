"""
reload_chile_from_xbrl.py - Recarga CHILE.SN desde XBRLs (sin pandas)
Recupera datos faltantes (liabilities, revenue, net_income, etc.) de años 2018-2025
"""

import zipfile
import xml.etree.ElementTree as ET
import sqlite3
import os
from datetime import datetime

# Configuración
DB_PATH = os.path.join("output", "warehouse.db")
TICKER = "CHILE.SN"
ANNOS_A_RECARGAR = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

# Mapeo de conceptos en español (namespace cl-ci) a nombres estándar
MAPEO_CONCEPTOS = {
    # Balance - Activos
    'ActivoIndividualEntidad': 'assets',
    'Activos': 'assets',

    # Balance - Pasivos
    'Pasivos': 'liabilities',
    'PasivoIndividualEntidad': 'liabilities',

    # Balance - Patrimonio
    'Patrimonio': 'equity',
    'PatrimonioTotal': 'equity',

    # Estado de Resultados
    'UtilidadLiquida': 'net_income',
    'UtilidadLiquidaDistribuible': 'net_income',
    'ResultadoNeto': 'net_income',

    'IngresosOperacionales': 'revenue',
    'IngresosPorIntereses': 'revenue',  # Para bancos
    'InteresesYSimilares': 'operating_income',

    'ResultadoDelEjercicio': 'net_income',
    'UtilidadDelEjercicio': 'net_income',
}


def parse_xbrl_chile(year):
    """Parsea XBRL de CHILE.SN para un año específico"""
    zip_path = f"data/CHILE_SN_90331000/{year}/12/CHILE_SN_90331000_{year}_12.zip"

    if not os.path.exists(zip_path):
        print(f"  [AVISO] No existe: {zip_path}")
        return None

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Buscar archivo .xbrl
            xbrl_files = [f for f in zip_ref.namelist() if f.endswith('.xbrl')]

            if not xbrl_files:
                print(f"  [ERROR] No se encontró archivo .xbrl en {zip_path}")
                return None

            xbrl_content = zip_ref.read(xbrl_files[0])

        # Parsear XML
        root = ET.fromstring(xbrl_content)

        # Buscar conceptos relevantes
        datos = {}

        # Primero, buscar todos los contextos para identificar el periodo actual (diciembre del año)
        contextos_actuales = []
        for elem in root.iter():
            if elem.tag.endswith('}context') or elem.tag == 'context':
                context_id = elem.get('id', '')

                # Buscar periodo
                periodo = elem.find('.//{*}period')
                if periodo is not None:
                    instant_elem = periodo.find('.//{*}instant')
                    end_date_elem = periodo.find('.//{*}endDate')

                    fecha = None
                    if instant_elem is not None and instant_elem.text:
                        fecha = instant_elem.text
                    elif end_date_elem is not None and end_date_elem.text:
                        fecha = end_date_elem.text

                    if fecha and f"{year}-12-31" in fecha:
                        contextos_actuales.append(context_id)

        # Ahora buscar los facts (valores) para conceptos relevantes
        for elem in root.iter():
            if not elem.text:
                continue

            # Obtener nombre del concepto (quitar namespace)
            concepto_nombre = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            # Verificar si es un concepto que nos interesa
            if concepto_nombre not in MAPEO_CONCEPTOS:
                continue

            # Intentar convertir a número
            try:
                valor = float(elem.text)
                if valor == 0:
                    continue
            except (ValueError, TypeError):
                continue

            # Obtener contexto
            context_ref = elem.get('contextRef', '')

            # Solo usar valores del periodo actual
            if context_ref not in contextos_actuales:
                continue

            # Mapear al nombre estándar
            campo_estandar = MAPEO_CONCEPTOS[concepto_nombre]

            # Guardar el valor (usar el último encontrado si hay duplicados)
            datos[campo_estandar] = valor

        return datos if datos else None

    except Exception as e:
        print(f"  [ERROR] Excepción parseando {year}: {e}")
        return None


def main():
    print("=" * 100)
    print("RECARGANDO CHILE.SN DESDE XBRL (sin pandas)")
    print("=" * 100)
    print()
    print(fTicker: {TICKER}")
    print(f"Años a recargar: {ANNOS_A_RECARGAR}")
    print(f"Base de datos: {DB_PATH}")
    print()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe {DB_PATH}")
        return

    # Parsear XBRLs
    print("PASO 1: Parseando XBRLs...")
    print("-" * 100)

    datos_por_anno = {}

    for anno in ANNOS_A_RECARGAR:
        print(f"\nAño {anno}:")
        datos = parse_xbrl_chile(anno)

        if datos:
            datos_por_anno[anno] = datos
            print(f"  [OK] Datos extraídos:")
            for campo, valor in sorted(datos.items()):
                print(f"      {campo:<25} {valor:>20,.0f}")
        else:
            print(f"  [ERROR] No se pudieron extraer datos")

    print()
    print("=" * 100)
    print(f"PASO 2: Actualizando warehouse.db")
    print("=" * 100)
    print()

    # Conectar a la BD
    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    actualizados = 0
    errores = 0

    for anno, datos in datos_por_anno.items():
        try:
            # Verificar si existe el registro
            cursor.execute("""
                SELECT month FROM normalized_financials
                WHERE ticker = ? AND year = ?
            """, (TICKER, anno))

            existing = cursor.fetchone()

            if existing:
                month = existing[0]

                # Construir SET clause dinámica
                set_clauses = []
                values = []

                for campo, valor in datos.items():
                    set_clauses.append(f"{campo} = ?")
                    values.append(valor)

                if set_clauses:
                    values.extend([TICKER, anno, month])

                    sql = f"""
                        UPDATE normalized_financials
                        SET {', '.join(set_clauses)}
                        WHERE ticker = ? AND year = ? AND month = ?
                    """

                    cursor.execute(sql, values)
                    actualizados += 1
                    print(f"  [OK] {anno}: Actualizados {len(datos)} campos")
            else:
                print(f"  [AVISO] {anno}: No existe registro en warehouse (insertar primero)")

        except Exception as e:
            errores += 1
            print(f"  [ERROR] {anno}: {e}")

    con.commit()
    con.close()

    print()
    print("=" * 100)
    print("RESUMEN")
    print("=" * 100)
    print(f"Años procesados: {len(datos_por_anno)}/{len(ANNOS_A_RECARGAR)}")
    print(f"Registros actualizados: {actualizados}")
    print(f"Errores: {errores}")
    print()

    if actualizados > 0:
        print("[OK] Datos de CHILE.SN recargados desde XBRL")
        print()
        print("Verificar con:")
        print("  python -c \"import sqlite3; con = sqlite3.connect('output/warehouse.db'); cursor = con.cursor(); cursor.execute('SELECT year, assets, liabilities, equity, revenue, net_income FROM normalized_financials WHERE ticker = \\\"CHILE.SN\\\" AND year >= 2018 ORDER BY year'); [print(f'{r[0]}: Assets={r[1]:,.0f}, Liab={r[2]:,.0f}, Equity={r[3]:,.0f}, Revenue={r[4]:,.0f}, NetInc={r[5]:,.0f}') for r in cursor.fetchall()]\"")
    else:
        print("[AVISO] No se actualizaron registros. Verificar logs arriba.")

    print("=" * 100)


if __name__ == '__main__':
    main()
