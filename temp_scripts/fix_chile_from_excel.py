"""
fix_chile_from_excel.py - Carga datos de CHILE.SN desde el Excel manualmente
Solución alternativa cuando la API CMF no funciona
"""

import sqlite3
import pandas as pd
import os

DB_PATH = os.path.join("output", "warehouse.db")
EXCEL_PATH = "PlanillaCursoDividendos.xlsx"


def get_chile_data_from_excel():
    """
    Extrae datos de CHILE.SN desde el Excel.
    Retorna dict {year: {field: value}}
    """
    df = pd.read_excel(EXCEL_PATH, sheet_name='CHILE', header=None)

    # Estructura del Excel ya conocida:
    # - Fila 5: Años (desde columna 2)
    # - Fila 6+: Métricas (columna 1 = nombre, columnas 2+ = valores)

    years_row = df.iloc[5]
    year_cols = {}

    for col_idx in range(2, len(years_row)):
        try:
            year_val = years_row[col_idx]
            if pd.isna(year_val):
                continue

            year = int(float(str(year_val).replace('.0', '')))
            if 2010 <= year <= 2030:
                year_cols[col_idx] = year
        except (ValueError, TypeError):
            continue

    # Métricas a extraer del Excel
    metric_map = {
        'Activos totales': 'assets',
        'Activos corrientes': 'current_assets',
        'Acitvos no corrientes (no circulantes o fijos)': 'non_current_assets',
        'Pasivos corrientes': 'current_liabilities',
        'Pasivos no corrientes': 'non_current_liabilities',
        'Total Pasivos': 'liabilities',
        'Patrimonio': 'equity',
        'Cuentas por cobrar': 'trade_receivables',
        'Inventario': 'inventories',
    }

    # Extraer datos
    data = {}
    for row_idx in range(6, len(df)):
        metric_name = df.iloc[row_idx, 1]

        if pd.isna(metric_name) or metric_name not in metric_map:
            continue

        warehouse_field = metric_map[metric_name]

        for col_idx, year in year_cols.items():
            value = df.iloc[row_idx, col_idx]

            if pd.isna(value) or value == 0:
                continue

            try:
                # El Excel tiene datos en MILLONES para bancos
                value_float = float(value) * 1e6

                if year not in data:
                    data[year] = {}

                data[year][warehouse_field] = value_float
            except (ValueError, TypeError):
                continue

    return data


def upsert_chile_to_db(con, excel_data):
    """
    Hace upsert de datos de CHILE.SN al warehouse.
    """
    cursor = con.cursor()

    updated_years = []

    for year, metrics in excel_data.items():
        ticker = 'CHILE.SN'
        month = 12  # Diciembre

        # Primero verificar si ya existe
        cursor.execute(
            "SELECT COUNT(*) FROM normalized_financials WHERE ticker = ? AND year = ? AND month = ?",
            (ticker, year, month)
        )
        exists = cursor.fetchone()[0] > 0

        if exists:
            # Eliminar fila existente
            cursor.execute(
                "DELETE FROM normalized_financials WHERE ticker = ? AND year = ? AND month = ?",
                (ticker, year, month)
            )

        # Crear nueva fila con campos mínimos
        row = {
            'ticker': ticker,
            'year': year,
            'month': month,
            'industry': 'financial',
            'reporting_currency': 'CLP',
        }

        # Agregar métricas
        row.update(metrics)

        # Construir INSERT dinámico
        fields = list(row.keys())
        values = [row[f] for f in fields]
        placeholders = ', '.join(['?' for _ in fields])
        field_names = ', '.join(fields)

        insert_sql = f"""
            INSERT INTO normalized_financials ({field_names})
            VALUES ({placeholders})
        """

        try:
            cursor.execute(insert_sql, values)
            con.commit()
            updated_years.append(year)
            print(f"  ✓ {year}: {len(metrics)} campos actualizados")
        except Exception as e:
            print(f"  ✗ {year}: ERROR - {e}")
            con.rollback()

    return updated_years


def main():
    """Función principal."""
    print("=" * 60)
    print("Cargando datos de CHILE.SN desde Excel")
    print("(Solución alternativa - API CMF no funciona)")
    print("=" * 60)
    print()

    if not os.path.exists(EXCEL_PATH):
        print(f"ERROR: No existe {EXCEL_PATH}")
        return

    if not os.path.exists(DB_PATH):
        print(f"ERROR: No existe {DB_PATH}")
        return

    # Extraer datos del Excel
    print("Extrayendo datos del Excel...")
    excel_data = get_chile_data_from_excel()

    if not excel_data:
        print("ERROR: No se pudieron extraer datos de CHILE.SN del Excel")
        return

    print(f"Datos extraídos: {len(excel_data)} años")
    print(f"Años: {sorted(excel_data.keys())}")
    print()

    # Conectar a database
    print("Actualizando warehouse...")
    con = sqlite3.connect(DB_PATH)

    try:
        updated_years = upsert_chile_to_db(con, excel_data)

        con.close()

        print()
        print("=" * 60)
        print(f"✅ CHILE.SN actualizado correctamente")
        print(f"   Años actualizados: {len(updated_years)}")
        print()
        print("Ahora recalcular ratios:")
        print("  python ratios.py")
        print("=" * 60)

    except Exception as e:
        print(f"ERROR: {e}")
        con.close()


if __name__ == '__main__':
    main()
