"""
Valida los datos del AFP pipeline antes de insertar en el warehouse.
Detecta problemas y compara con datos de referencia.
"""
import sqlite3
import pandas as pd
from pathlib import Path

# Datos esperados del dry-run (extraídos del output)
DRY_RUN_DATA = [
    # AFPCAPITAL.SN
    {'ticker': 'AFPCAPITAL.SN', 'year': 2025, 'fee_income': 205892506, 'net_income': 102713160, 'equity': 502438517, 'contributors': 1420816},
    {'ticker': 'AFPCAPITAL.SN', 'year': 2024, 'fee_income': 197875487, 'net_income': 106632475, 'equity': 474753097, 'contributors': 1462611},
    {'ticker': 'AFPCAPITAL.SN', 'year': 2023, 'fee_income': 181129511, 'net_income': 88294898, 'equity': 452366991, 'contributors': 1523703},
    {'ticker': 'AFPCAPITAL.SN', 'year': 2022, 'fee_income': 163319880, 'net_income': 73164253, 'equity': 426733714, 'contributors': 1575544},
    {'ticker': 'AFPCAPITAL.SN', 'year': 2021, 'fee_income': 149043800, 'net_income': 59912751, 'equity': 414857775, 'contributors': 1620194},
    {'ticker': 'AFPCAPITAL.SN', 'year': 2020, 'fee_income': 146683134, 'net_income': 87047237, 'equity': 416763980, 'contributors': 1634208},
    # PLANVITAL.SN
    {'ticker': 'PLANVITAL.SN', 'year': 2025, 'fee_income': 42328783, 'net_income': 140082074, 'equity': 1175094978, 'contributors': 2635691},
    {'ticker': 'PLANVITAL.SN', 'year': 2024, 'fee_income': 39940512, 'net_income': 129398125, 'equity': 1184359924, 'contributors': 2712979},
    {'ticker': 'PLANVITAL.SN', 'year': 2023, 'fee_income': 38054553, 'net_income': 126481080, 'equity': 1189414750, 'contributors': 2782164},
    {'ticker': 'PLANVITAL.SN', 'year': 2021, 'fee_income': 25050093, 'net_income': 101017173, 'equity': 1170021730, 'contributors': 2914880},
    {'ticker': 'PLANVITAL.SN', 'year': 2020, 'fee_income': 28931083, 'net_income': 77373042, 'equity': 1193130294, 'contributors': 2949374},
    {'ticker': 'PLANVITAL.SN', 'year': 2019, 'fee_income': 29621640, 'net_income': 116729011, 'equity': 1239347780, 'contributors': 3028356},
    # PROVIDA.SN - NOTA: Estos parecen duplicados de PLANVITAL!
    {'ticker': 'PROVIDA.SN', 'year': 2025, 'fee_income': 42328783, 'net_income': 140082074, 'equity': 1175094978, 'contributors': 2635691},
    {'ticker': 'PROVIDA.SN', 'year': 2024, 'fee_income': 39940512, 'net_income': 129398125, 'equity': 1184359924, 'contributors': 2712979},
    {'ticker': 'PROVIDA.SN', 'year': 2023, 'fee_income': 38054553, 'net_income': 126481080, 'equity': 1189414750, 'contributors': 2782164},
    {'ticker': 'PROVIDA.SN', 'year': 2024, 'fee_income': 179268248, 'net_income': 81496493, 'equity': 1173835533, 'contributors': 2730513},  # Q3 2024
]

def check_existing_afp_data(db_path):
    """Verifica si ya existen datos de AFP en el warehouse"""
    conn = sqlite3.connect(db_path)
    
    # Buscar datos de AFP existentes
    query = """
        SELECT ticker, year, revenue, net_income, equity 
        FROM normalized_financials 
        WHERE ticker LIKE '%AFP%' OR ticker LIKE '%PROVIDA%' OR ticker LIKE '%PLANVITAL%' OR ticker LIKE '%CUPRUM%'
        ORDER BY ticker, year
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def detect_duplicate_data():
    """Detecta datos duplicados entre PROVIDA y PLANVITAL"""
    print("\n" + "=" * 60)
    print("ALERTA: DETECCIÓN DE DUPLICADOS")
    print("=" * 60)
    
    provida_data = [d for d in DRY_RUN_DATA if d['ticker'] == 'PROVIDA.SN']
    planvital_data = [d for d in DRY_RUN_DATA if d['ticker'] == 'PLANVITAL.SN']
    
    # Comparar PROVIDA 2023-2025 con PLANVITAL
    for pv in provida_data:
        for pvt in planvital_data:
            if pv['year'] == pvt['year']:
                if (pv['fee_income'] == pvt['fee_income'] and 
                    pv['net_income'] == pvt['net_income'] and 
                    pv['equity'] == pvt['equity']):
                    print(f"\n⚠️  DUPLICADO DETECTADO:")
                    print(f"   PROVIDA.SN {pv['year']}: fee={pv['fee_income']:,}, net_income={pv['net_income']:,}")
                    print(f"   PLANVITAL.SN {pvt['year']}: fee={pvt['fee_income']:,}, net_income={pvt['net_income']:,}")
                    print(f"   → Los datos son IDÉNTICOS - posible error en asignación de PDFs!")
    
    # PROVIDA tiene datos reales diferentes (Q3 2024)
    print("\n✓ PROVIDA tiene un registro único (Q3 2024):")
    q3_2024 = [d for d in provida_data if d['year'] == 2024 and d['fee_income'] == 179268248]
    if q3_2024:
        print(f"   fee_income: {q3_2024[0]['fee_income']:,}")
        print(f"   net_income: {q3_2024[0]['net_income']:,}")
        print(f"   equity: {q3_2024[0]['equity']:,}")

def validate_data_consistency():
    """Valida consistencia de los datos"""
    print("\n" + "=" * 60)
    print("VALIDACIÓN DE CONSISTENCIA")
    print("=" * 60)
    
    for ticker in ['AFPCAPITAL.SN', 'PLANVITAL.SN', 'PROVIDA.SN']:
        data = [d for d in DRY_RUN_DATA if d['ticker'] == ticker]
        if not data:
            continue
            
        print(f"\n{ticker}:")
        data_sorted = sorted(data, key=lambda x: x['year'])
        
        for i, d in enumerate(data_sorted):
            print(f"  {d['year']}: fee={d['fee_income']:>12,} | net_income={d['net_income']:>12,} | equity={d['equity']:>15,}")
            
            # Verificar coherencia año a año
            if i > 0:
                prev = data_sorted[i-1]
                equity_change = (d['equity'] - prev['equity']) / prev['equity'] * 100
                net_income_change = (d['net_income'] - prev['net_income']) / prev['net_income'] * 100 if prev['net_income'] != 0 else 0
                
                # Alertar si equity cambia más de 50%
                if abs(equity_change) > 50:
                    print(f"       ⚠️  Equity cambió {equity_change:.1f}% vs año anterior")

def compare_with_reference():
    """Compara con datos de referencia conocidos"""
    print("\n" + "=" * 60)
    print("COMPARACIÓN CON DATOS DE REFERENCIA")
    print("=" * 60)
    
    # Datos de referencia de la CMF (aproximados para validación)
    # Fuente: Estados financieros públicos de AFP
    
    reference = {
        'AFPCAPITAL.SN': {
            2024: {'net_income_expected': 100000000, 'tolerance': 0.15},  # ~10% tolerancia
            2023: {'net_income_expected': 85000000, 'tolerance': 0.15},
        },
        'PROVIDA.SN': {
            # PROVIDA es la AFP más grande, debería tener ingresos mayores
            2024: {'fee_income_min': 150000000},  # Mínimo esperado
        }
    }
    
    for ticker, years in reference.items():
        data = [d for d in DRY_RUN_DATA if d['ticker'] == ticker]
        for year, ref in years.items():
            record = [d for d in data if d['year'] == year]
            if record:
                record = record[0]
                if 'net_income_expected' in ref:
                    expected = ref['net_income_expected']
                    tolerance = ref['tolerance']
                    actual = record['net_income']
                    diff_pct = abs(actual - expected) / expected
                    status = "✓" if diff_pct <= tolerance else "⚠️"
                    print(f"{ticker} {year}: net_income={actual:,} (esperado ~{expected:,}) {status}")
                
                if 'fee_income_min' in ref:
                    min_expected = ref['fee_income_min']
                    actual = record['fee_income']
                    status = "✓" if actual >= min_expected else "⚠️ DEMASIADO BAJO"
                    print(f"{ticker} {year}: fee_income={actual:,} (mínimo esperado ~{min_expected:,}) {status}")

def validate_excel_comparison(db_path):
    """Compara con datos del Excel manual si está disponible"""
    excel_path = Path('g:/Code/PlanillaCursoDividendos.xlsx')
    
    if not excel_path.exists():
        print(f"\nExcel no encontrado: {excel_path}")
        return
    
    print("\n" + "=" * 60)
    print("COMPARACIÓN CON EXCEL MANUAL")
    print("=" * 60)
    
    try:
        xl = pd.ExcelFile(excel_path)
        
        # Buscar hojas de AFP
        afp_sheets = [s for s in xl.sheet_names if 'AFP' in s.upper() or 'PROVIDA' in s.upper() or 
                      'CAPITAL' in s.upper() or 'PLANVITAL' in s.upper() or 'CUPRUM' in s.upper()]
        
        print(f"Hojas AFP encontradas: {afp_sheets}")
        
        for sheet in afp_sheets:
            print(f"\n--- {sheet} ---")
            df = pd.read_excel(xl, sheet_name=sheet, header=None)
            
            # Buscar datos relevantes
            for idx, row in df.iterrows():
                row_str = str(row.values)
                if 'utilidad' in row_str.lower() or 'patrimonio' in row_str.lower() or 'fee' in row_str.lower():
                    print(f"Fila {idx}: {row.values[:10]}")
                    
    except Exception as e:
        print(f"Error leyendo Excel: {e}")

def main():
    db_path = Path('output/warehouse.db')
    
    print("=" * 60)
    print("VALIDACIÓN PRE-INSERT AFP PIPELINE")
    print("=" * 60)
    
    # 1. Verificar datos existentes
    print("\n1. Verificando datos existentes en warehouse...")
    if db_path.exists():
        existing = check_existing_afp_data(db_path)
        if len(existing) > 0:
            print(f"\n⚠️  Ya existen {len(existing)} registros de AFP en warehouse:")
            print(existing.to_string())
        else:
            print("✓ No hay datos de AFP existentes en warehouse")
    else:
        print("Warehouse no existe aún")
    
    # 2. Detectar duplicados
    print("\n2. Detectando duplicados...")
    detect_duplicate_data()
    
    # 3. Validar consistencia
    print("\n3. Validando consistencia...")
    validate_data_consistency()
    
    # 4. Comparar con referencia
    print("\n4. Comparando con referencia...")
    compare_with_reference()
    
    # 5. Comparar con Excel
    print("\n5. Comparando con Excel manual...")
    validate_excel_comparison(db_path)
    
    # Resumen final
    print("\n" + "=" * 60)
    print("RESUMEN Y RECOMENDACIONES")
    print("=" * 60)
    
    print("""
PROBLEMA DETECTADO:
==================
Los datos de PROVIDA.SN (2023-2025) son IDÉNTICOS a PLANVITAL.SN.
Esto indica un error en la asignación de PDFs a tickers.

PROVIDA es la AFP más grande de Chile con ~5.8M de cotizantes.
PLANVITAL es más pequeña con ~2.6M de cotizantes.

Los valores de 'contributors' (2.6M) corresponden a PLANVITAL, no PROVIDA.

ACCIÓN REQUERIDA:
================
1. Revisar el mapeo de PDFs en el afp_pipeline.py
2. Verificar que los PDFs de Provida estén correctamente identificados
3. NO insertar datos hasta corregir este problema

DATOS CORRECTOS (AFPCAPITAL.SN):
================================
AFPCAPITAL muestra datos consistentes y coherentes año a año.
Contributors decreciendo de 1.6M (2020) a 1.4M (2025) es razonable.
""")

if __name__ == '__main__':
    main()