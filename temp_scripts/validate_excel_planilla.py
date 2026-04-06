"""
Validación del warehouse contra PlanillaCursoDividendos.xlsx
Compara datos ingresados manualmente (confiables) con el warehouse
"""

import pandas as pd
import sqlite3
import os
from pathlib import Path

# Mapeo de métricas de Excel → warehouse
METRIC_MAP = {
    'Activos totales': 'assets',
    'Activos corrientes': 'current_assets',
    'Acitvos no corrientes (no circulantes o fijos)': 'non_current_assets',
    'Pasivos corrientes': 'current_liabilities',
    'Pasivos no corrientes': 'non_current_liabilities',
    'Total Pasivos': 'liabilities',
    'Patrimonio': 'equity',
    'Cuentas por cobrar': 'trade_receivables',
    'Inventario': 'inventories',
    'Ventas': 'revenue',
    'Costo de ventas': 'cost_of_sales',
    'Utilidad Bruta': 'gross_profit',
    'Utilidad Operativa': 'operating_income',
    'Utilidad Antes de Impuesto': 'profit_before_tax',
    'Impuesto a la renta': 'income_tax',
    'Utilidad Neta': 'net_income',
    'Depreciación': 'depreciation_amortization',
    'Flujo de caja operación': 'cfo',
    'CAPEX': 'capex',
    'Flujo de caja libre': 'fcf',
    'Dividendos pagados': 'dividends_paid',
}

# Mapeo de nombres de hojas Excel → ticker
EXCEL_TO_TICKER = {
    'AAISA': 'AAISA.SN',
    'AFPCAPITAL': 'AFPCAPITAL.SN',
    'AGUAS-A': 'AGUAS-A.SN',
    'AGUAS-B': 'AGUAS-B.SN',
    'ALMENDRAL': 'ALMENDRAL.SN',
    'ANDINA A': 'ANDINA-A.SN',
    'ANDINA B': 'ANDINA-B.SN',
    'BCI': 'BCI.SN',
    'BESALCO (TIKR)': 'BESALCO.SN',
    'COLBÚN': 'COLBUN.SN',
    'BOLSA STGO': 'BCH.SN',
    'CAP (TIKR)': 'CAP.SN',
    'CCU': 'CCU.SN',
    'CENCOMALLS': 'CENCOSUD.SN',
    'CGE': 'CGE.SN',
    'CHILE': 'CHILE.SN',
    'CONCHATORO': 'CONCHATORO.SN',
    'CMPC': 'CMPC.SN',
    'CUPRUM': 'CUPRUM.SN',
    'EDELMAG': 'EDELMAG.SN',
    'ELECMETAL': 'ELECMETAL.SN',
    'EMBONOR A': 'EMBONOR-A.SN',
    'EISA (TIKR)': 'EISA.SN',
    'EMBONOR B': 'EMBONOR-B.SN',
    'ENELAM': 'ENELAM.SN',
    'ENELCHILE': 'ENELCHILE.SN',
    'ENLASA': 'ENLASA.SN',
    'ENELGXCH': 'ENELGXCH.SN',
    'ENTEL': 'ENTEL.SN',
    'FORUS': 'FORUS.SN',
    'FOSFOROS': 'FOSFOROS.SN',
    'GASCO': 'GASCO.SN',
    'HABITAT': 'AFPHABITAT.SN',
    'IAM': 'IAM.SN',
    'ILC': 'ILC.SN',
    'ITAU': 'ITAUCL.SN',
    'LIPIGAS': 'LIPIGAS.SN',
    'MANQUEHUE': 'MANQUEHUE.SN',
    'MALLPLAZA': 'MALLPLAZA.SN',
    'NUAM': 'NUAM.SN',
    'OXIQUIM': 'OXIQUIM.SN',
    'PARAUCO': 'PARAUCO.SN',
    'PLANVITAL': 'AFPPLANVITAL.SN',
    'PROVIDA': 'AFPPROVIDA.SN',
    'SALFACORP (TIKR)': 'SALFACORP.SN',
    'SANTANDER': 'BSANTANDER.SN',
    'SECURITY': 'SECURITY.SN',
    'SONDA': 'SONDA.SN',
    'QUINENCO': 'QUINENCO.SN',
    'SMU': 'SMU.SN',
    'SOQUICOM': 'SOQUICOM.SN',
    'VOLCAN': 'VOLCAN.SN',
    'ZOFRI': 'ZOFRI.SN',
}

# Tickers bancarios - Excel tiene datos en MILLONES, need scale factor 1e6
BANK_TICKERS = {
    'BCI.SN', 'BSANTANDER.SN', 'ITAUCL.SN', 'CHILE.SN', 'BICE.SN'
}


def parse_excel_sheet(excel_path, sheet_name):
    """
    Parsea una hoja de empresa del Excel
    Retorna un dict {year: {metric: value}}
    """
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)

    # Estructura:
    # - Fila 5: Años (desde columna 2)
    # - Fila 6+: Métricas (columna 1 = nombre, columnas 2+ = valores)

    years_row = df.iloc[5]
    year_cols = {}  # {col_index: year}

    for col_idx in range(2, len(years_row)):  # Empezar desde columna 2
        try:
            year_val = years_row[col_idx]
            if pd.isna(year_val):
                continue

            year = int(float(str(year_val).replace('.0', '')))
            if 2010 <= year <= 2030:
                year_cols[col_idx] = year
        except (ValueError, TypeError):
            continue

    # Parsear métricas desde fila 6
    data = {}
    for row_idx in range(6, len(df)):
        metric_name = df.iloc[row_idx, 1]  # Columna 1 tiene el nombre

        if pd.isna(metric_name) or metric_name not in METRIC_MAP:
            continue

        warehouse_field = METRIC_MAP[metric_name]

        for col_idx, year in year_cols.items():
            value = df.iloc[row_idx, col_idx]

            if pd.isna(value) or value == 0:
                continue

            try:
                # Convertir a float (los datos vienen como float o scientific notation)
                value_float = float(value)

                if year not in data:
                    data[year] = {}

                data[year][warehouse_field] = value_float
            except (ValueError, TypeError):
                continue

    return data


def get_excel_scale(ticker):
    """
    Retorna el factor de escala para convertir datos del Excel a unidades completas.

    Bancos en Excel: datos en MILLONES (factor 1e6)
    Otros: datos en unidades completas (factor 1.0)
    """
    if ticker in BANK_TICKERS:
        return 1e6
    return 1.0


def get_warehouse_data(db_path):
    """Carga todos los datos del warehouse"""
    con = sqlite3.connect(db_path)

    # Cargar normalized_financials
    df_norm = pd.read_sql_query("SELECT * FROM normalized_financials", con)
    df_derived = pd.read_sql_query("SELECT * FROM derived_metrics", con)

    con.close()

    # Pivotear a formato {ticker: {year: {field: value}}}
    warehouse = {}

    for _, row in df_norm.iterrows():
        ticker = row['ticker']
        year = row['year']

        if ticker not in warehouse:
            warehouse[ticker] = {}

        if year not in warehouse[ticker]:
            warehouse[ticker][year] = {}

        # Agregar todos los campos numéricos
        for col in df_norm.columns:
            if col in ['ticker', 'year', 'month', 'industry', 'reporting_currency']:
                continue

            value = row[col]
            if pd.notna(value):
                warehouse[ticker][year][col] = value

    # Agregar derived_metrics
    for _, row in df_derived.iterrows():
        ticker = row['ticker']
        year = row['year']

        if ticker not in warehouse:
            warehouse[ticker] = {}

        if year not in warehouse[ticker]:
            warehouse[ticker][year] = {}

        for col in df_derived.columns:
            if col in ['ticker', 'year', 'month', 'industry']:
                continue

            if '_source' in col:  # Skip source fields
                continue

            value = row[col]
            if pd.notna(value):
                warehouse[ticker][year][col] = value

    return warehouse


def compare_data(excel_data, warehouse_data, ticker, sheet_name):
    """
    Compara datos de Excel vs Warehouse
    Retorna lista de discrepancias
    """
    discrepancies = []

    # Obtener factor de escala para este ticker
    scale = get_excel_scale(ticker)

    for year, excel_metrics in excel_data.items():
        if ticker not in warehouse_data:
            discrepancies.append({
                'ticker': ticker,
                'sheet': sheet_name,
                'year': year,
                'metric': 'ALL',
                'excel_value': 'N/A',
                'warehouse_value': 'MISSING',
                'diff_pct': 'N/A',
                'status': 'MISSING_IN_WAREHOUSE'
            })
            continue

        if year not in warehouse_data[ticker]:
            discrepancies.append({
                'ticker': ticker,
                'sheet': sheet_name,
                'year': year,
                'metric': 'ALL',
                'excel_value': 'N/A',
                'warehouse_value': 'MISSING',
                'diff_pct': 'N/A',
                'status': 'MISSING_YEAR'
            })
            continue

        warehouse_metrics = warehouse_data[ticker][year]

        for metric, excel_value in excel_metrics.items():
            # Aplicar factor de escala (para bancos: millones -> unidades)
            excel_value_scaled = excel_value * scale

            if metric not in warehouse_metrics:
                discrepancies.append({
                    'ticker': ticker,
                    'sheet': sheet_name,
                    'year': year,
                    'metric': metric,
                    'excel_value': excel_value_scaled,
                    'warehouse_value': 'NULL',
                    'diff_pct': 'N/A',
                    'status': 'MISSING_METRIC'
                })
                continue

            warehouse_value = warehouse_metrics[metric]

            # Calcular diferencia porcentual
            if warehouse_value != 0:
                diff_pct = abs((excel_value_scaled - warehouse_value) / warehouse_value) * 100
            else:
                diff_pct = float('inf') if excel_value_scaled != 0 else 0

            # Clasificar discrepancia
            if diff_pct < 1:
                status = 'MATCH'
            elif diff_pct < 5:
                status = 'GOOD'
            elif diff_pct < 15:
                status = 'REVIEW'
            else:
                status = 'ALERT'

            # Reportar si hay discrepancia significativa
            if status != 'MATCH':
                discrepancies.append({
                    'ticker': ticker,
                    'sheet': sheet_name,
                    'year': year,
                    'metric': metric,
                    'excel_value': excel_value_scaled,
                    'warehouse_value': warehouse_value,
                    'diff_pct': round(diff_pct, 2),
                    'status': status
                })

    return discrepancies


def main():
    excel_path = 'PlanillaCursoDividendos.xlsx'
    db_path = 'output/warehouse.db'

    if not os.path.exists(excel_path):
        print(f"[ERROR] No existe {excel_path}")
        return

    if not os.path.exists(db_path):
        print(f"[ERROR] No existe {db_path}")
        return

    print("Validando Warehouse vs Planilla Excel")
    print("=" * 60)
    print()

    # Cargar warehouse
    print("Cargando warehouse...")
    warehouse_data = get_warehouse_data(db_path)
    print(f"Warehouse cargado: {len(warehouse_data)} tickers")
    print()

    # Parsear Excel
    print("Parseando planilla Excel...")
    all_discrepancies = []
    validated_companies = 0

    for sheet_name, ticker in EXCEL_TO_TICKER.items():
        try:
            excel_data = parse_excel_sheet(excel_path, sheet_name)

            if not excel_data:
                continue

            discrepancies = compare_data(excel_data, warehouse_data, ticker, sheet_name)

            if discrepancies:
                all_discrepancies.extend(discrepancies)

            validated_companies += 1

            print(f"  [OK] {sheet_name} ({ticker}): {len(excel_data)} años, {len(discrepancies)} discrepancias")

        except Exception as e:
            print(f"  [ERROR] Error procesando {sheet_name}: {e}")

    print()
    print("=" * 60)
    print(f"[RESUMEN] RESUMEN")
    print(f"  * Empresas validadas: {validated_companies}")
    print(f"  * Discrepancias totales: {len(all_discrepancies)}")
    print()

    # Clasificar discrepancias
    alerts = [d for d in all_discrepancies if d['status'] == 'ALERT']
    reviews = [d for d in all_discrepancies if d['status'] == 'REVIEW']
    missing = [d for d in all_discrepancies if 'MISSING' in d['status']]

    print(f"  [!] ALERT (>15%): {len(alerts)}")
    print(f"  [?] REVIEW (5-15%): {len(reviews)}")
    print(f"  [-] MISSING: {len(missing)}")
    print()

    # Mostrar top alerts
    if alerts:
        print("=" * 60)
        print("[!] TOP 20 DISCREPANCIAS CRÍTICAS (>15%)")
        print("=" * 60)

        # Ordenar por diferencia porcentual
        alerts_sorted = sorted(alerts, key=lambda x: x['diff_pct'] if isinstance(x['diff_pct'], (int, float)) else 0, reverse=True)

        for i, disc in enumerate(alerts_sorted[:20], 1):
            print(f"\n{i}. {disc['ticker']} ({disc['year']}) - {disc['metric']}")
            print(f"   Excel:      {disc['excel_value']:,.0f}")
            print(f"   Warehouse:  {disc['warehouse_value']}")
            print(f"   Diferencia: {disc['diff_pct']}%")

    # Guardar reporte
    if all_discrepancies:
        output_path = 'output/validation_planilla.xlsx'
        df_report = pd.DataFrame(all_discrepancies)
        df_report.to_excel(output_path, index=False)
        print()
        print(f"[FILE] Reporte completo guardado en: {output_path}")

    print()
    print("=" * 60)
    print("[DONE] Validación completada")


if __name__ == '__main__':
    main()
