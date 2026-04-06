"""
Valida los datos del warehouse contra la planilla Excel manual (PlanillaCursoDividendos.xlsx)
Compara empresas non-financial, bancos y AFPs.
"""
import pandas as pd
import sqlite3
from pathlib import Path

# Mapeo de nombres de hoja Excel a tickers del warehouse
TICKER_MAP = {
    'AFPCAPITAL': 'AFPCAPITAL.SN',
    'PLANVITAL': 'PLANVITAL.SN',  
    'PROVIDA': 'PROVIDA.SN',
    'CUPRUM': 'CUPRUM.SN',
    'AAISA': 'AAISA.SN',
    'ANDINA A': 'ANDINA-A.SN',
    'ANDINA B': 'ANDINA-B.SN',
    'AGUAS-A': 'AGUAS-A.SN',
    'AGUAS-B': 'AGUAS-B.SN',
    'BANVIDA': 'BANVIDA.SN',
    'BESALCO (TIKR)': 'BESALCO.SN',
    'BOLSA STGO': 'BOLSASTGO.SN',
    'CAP (TIKR)': 'CAP.SN',
    'CCU': 'CCU.SN',
    'CENCOMALLS': 'CENCOMALLS.SN',
    'CGE': 'CGE.SN',
    'CHILE': 'CHILE.SN',
    'CMPC': 'CMPC.SN',
    'COLBÚN': 'COLBUN.SN',
    'CONCHATORO': 'CONCHATORO.SN',
    'EDELMAG': 'EDELMAG.SN',
    'EISA (TIKR)': 'EISA.SN',
    'EMBONOR A': 'EMBONOR-A.SN',
    'EMBONOR B': 'EMBONOR-B.SN',
    'ENELAM': 'ENELAM.SN',
    # Bancos
    'BCI': 'BCI.SN',
    'BSANTANDER': 'BSANTANDER.SN',
}

# Mapeo de conceptos Excel -> conceptos warehouse
CONCEPT_MAP = {
    'Activos corrientes': 'AssetsCurrent',
    'Activos totales': 'Assets',
    'Pasivos corrientes': 'LiabilitiesCurrent',
    'Total Pasivos': 'Liabilities',
    'Patrimonio': 'Equity',
    'Patrimonio CONTROLADORA': 'Equity',
    'Patrimonio Controladora': 'Equity',
    'Ingresos': 'Revenues',
    'Ingresos totales': 'Revenues',
    'Utilidad neta': 'NetIncome',
    'EBIT': 'OperatingIncome',
    'EBITDA': 'EBITDA',
    'FCF': 'FreeCashFlow',
}

def load_excel_data(excel_path):
    """Carga datos del Excel manual"""
    print(f"Cargando Excel: {excel_path}")
    xl = pd.ExcelFile(excel_path)
    
    data = []
    for sheet in xl.sheet_names:
        if sheet in ['Responsables empresas', 'Cuidados a tener en la planilla', 
                     'Actualización de POWER BI', 'Como llenar dividendos', 
                     'Empresas Power BI', 'INDICE']:
            continue
            
        ticker = TICKER_MAP.get(sheet)
        if not ticker:
            continue
            
        df = pd.read_excel(xl, sheet_name=sheet, header=None)
        
        # Buscar fila de años (normalmente fila 3 o 4)
        year_row = None
        for idx, row in df.iterrows():
            years = [y for y in row if pd.notna(y) and isinstance(y, (int, float)) and 2015 <= y <= 2030]
            if len(years) >= 3:
                year_row = idx
                break
        
        if year_row is None:
            continue
            
        years = df.iloc[year_row].tolist()
        
        # Buscar conceptos en columna B (índice 1)
        for idx in range(year_row + 1, min(year_row + 100, len(df))):
            row = df.iloc[idx]
            concept_name = row.iloc[1] if len(row) > 1 else None
            
            if pd.isna(concept_name) or not isinstance(concept_name, str):
                continue
                
            concept_name = concept_name.strip()
            
            # Buscar mapeo
            warehouse_concept = None
            for excel_concept, wh_concept in CONCEPT_MAP.items():
                if excel_concept.lower() in concept_name.lower():
                    warehouse_concept = wh_concept
                    break
            
            if not warehouse_concept:
                continue
            
            # Extraer valores por año
            for col_idx, year in enumerate(years):
                if pd.isna(year) or not isinstance(year, (int, float)):
                    continue
                if int(year) < 2015 or int(year) > 2030:
                    continue
                    
                if col_idx >= len(row):
                    continue
                    
                value = row.iloc[col_idx]
                if pd.notna(value) and isinstance(value, (int, float)):
                    data.append({
                        'ticker': ticker,
                        'year': int(year),
                        'concept': warehouse_concept,
                        'value_excel': value
                    })
    
    return pd.DataFrame(data)

def load_warehouse_data(db_path):
    """Carga datos del warehouse"""
    print(f"Cargando warehouse: {db_path}")
    conn = sqlite3.connect(db_path)
    
    # Cargar financials
    df = pd.read_sql_query("""
        SELECT ticker, year, 
               revenue as Revenues,
               net_income as NetIncome,
               total_assets as Assets,
               total_equity as Equity
        FROM financials
        WHERE ticker IS NOT NULL
    """, conn)
    
    conn.close()
    
    # Melt para formato largo
    data = []
    for _, row in df.iterrows():
        for concept in ['Revenues', 'NetIncome', 'Assets', 'Equity']:
            if pd.notna(row[concept]):
                data.append({
                    'ticker': row['ticker'],
                    'year': int(row['year']),
                    'concept': concept,
                    'value_warehouse': row[concept]
                })
    
    return pd.DataFrame(data)

def compare_data(excel_df, warehouse_df):
    """Compara datos Excel vs Warehouse"""
    # Merge
    merged = pd.merge(excel_df, warehouse_df, 
                      on=['ticker', 'year', 'concept'], 
                      how='outer')
    
    # Calcular diferencia
    merged['value_excel'] = merged['value_excel'].fillna(0)
    merged['value_warehouse'] = merged['value_warehouse'].fillna(0)
    merged['diff'] = merged['value_excel'] - merged['value_warehouse']
    merged['diff_pct'] = merged.apply(
        lambda r: (r['diff'] / r['value_excel'] * 100) if r['value_excel'] != 0 else 0, axis=1
    )
    
    return merged

def validate_afp_pipeline(db_path):
    """Valida específicamente los datos del AFP pipeline"""
    print("\n=== Validación AFP Pipeline ===")
    conn = sqlite3.connect(db_path)
    
    # Verificar si hay tabla de AFPs
    tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)
    print(f"Tablas en warehouse: {tables['name'].tolist()}")
    
    # Cargar datos de AFPs
    try:
        afp = pd.read_sql_query("""
            SELECT * FROM financials 
            WHERE ticker LIKE '%AFP%' OR ticker LIKE '%PROVIDA%' OR ticker LIKE '%CUPRUM%'
            ORDER BY ticker, year
        """, conn)
        print(f"\nRegistros AFP en warehouse: {len(afp)}")
        if len(afp) > 0:
            print(afp[['ticker', 'year', 'revenue', 'net_income', 'total_assets', 'total_equity']].to_string())
    except Exception as e:
        print(f"Error cargando AFP: {e}")
    
    conn.close()

def main():
    excel_path = Path('g:/Code/PlanillaCursoDividendos.xlsx')
    db_path = Path('output/warehouse.db')
    
    if not excel_path.exists():
        print(f"ERROR: No existe {excel_path}")
        return
    
    if not db_path.exists():
        print(f"ERROR: No existe {db_path}")
        return
    
    print("=" * 60)
    print("VALIDACIÓN WAREHOUSE vs EXCEL MANUAL")
    print("=" * 60)
    
    # Cargar datos
    excel_df = load_excel_data(excel_path)
    print(f"\nDatos Excel: {len(excel_df)} registros")
    print(f"Tickers Excel: {excel_df['ticker'].nunique()}")
    
    warehouse_df = load_warehouse_data(db_path)
    print(f"\nDatos Warehouse: {len(warehouse_df)} registros")
    print(f"Tickers Warehouse: {warehouse_df['ticker'].nunique()}")
    
    # Validar AFP pipeline
    validate_afp_pipeline(db_path)
    
    # Comparar
    print("\n" + "=" * 60)
    print("COMPARACIÓN")
    print("=" * 60)
    
    comparison = compare_data(excel_df, warehouse_df)
    
    # Mostrar diferencias significativas
    significant_diff = comparison[abs(comparison['diff_pct']) > 1]
    
    if len(significant_diff) > 0:
        print(f"\nDiferencias significativas (>1%): {len(significant_diff)}")
        print(significant_diff.sort_values('diff_pct', key=abs, ascending=False).head(20).to_string())
    else:
        print("\n✓ No hay diferencias significativas")
    
    # Mostrar coincidencias
    matches = comparison[abs(comparison['diff_pct']) <= 1]
    print(f"\nCoincidencias (≤1% diff): {len(matches)}")
    
    # Mostrar datos solo en Excel
    only_excel = comparison[comparison['value_warehouse'] == 0]
    print(f"\nDatos solo en Excel: {len(only_excel)}")
    
    # Mostrar datos solo en Warehouse
    only_wh = comparison[comparison['value_excel'] == 0]
    print(f"Datos solo en Warehouse: {len(only_wh)}")
    
    # Guardar reporte
    comparison.to_csv('output/validation_vs_excel.csv', index=False)
    print(f"\nReporte guardado: output/validation_vs_excel.csv")

if __name__ == '__main__':
    main()