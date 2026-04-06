"""
verificar_yahoo_chile.py - Obtiene datos de CHILE.SN desde Yahoo Finance API
"""

import requests
import json

print('=' * 100)
print('BANCO DE CHILE (CHILE.SN) - DATOS DESDE YAHOO FINANCE API')
print('=' * 100)
print()

ticker = 'CHILE.SN'

try:
    url = f'https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}?modules=summaryProfile,incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code == 200:
        data = response.json()

        # Info básica
        print('1. INFORMACIÓN DE MERCADO:')
        print('-' * 100)
        try:
            price = data['quoteSummary']['result'][0]['price']
            market_cap = price.get('marketCap', {}).get('raw', 0)
            if market_cap:
                print(f'  Market Cap:              {market_cap:,.0f}')
            else:
                print(f'  Market Cap:              N/A')
            print(f'  Moneda:                  {price.get("currency", "N/A")}')
        except:
            print('  [AVISO] No disponible')

        print()

        # Balance Sheet
        print('2. BALANCE SHEET (más reciente):')
        print('-' * 100)
        try:
            bs = data['quoteSummary']['result'][0]['balanceSheetHistory']['balanceSheetStatements']
            if bs and len(bs) > 0:
                latest = bs[0]
                fecha = latest.get('endDate', {})
                print(f'  Fecha reporte:           {fecha.get("fmt", "N/A")}')
                print(f'  Total Assets:           {latest.get("totalAssets", {}).get("raw", 0):>20,.0f}')
                print(f'  Total Liabilities:      {latest.get("totalLiab", {}).get("raw", 0):>20,.0f}')
                print(f'  Total Equity:           {latest.get("totalStockholderEquity", {}).get("raw", 0):>20,.0f}')
            else:
                print('  [AVISO] No disponible')
        except Exception as e:
            print(f'  [ERROR] {e}')

        print()

        # Income Statement
        print('3. INCOME STATEMENT (más reciente):')
        print('-' * 100)
        try:
            is_data = data['quoteSummary']['result'][0]['incomeStatementHistory']['incomeStatementHistory']
            if is_data and len(is_data) > 0:
                latest = is_data[0]
                fecha = latest.get('endDate', {})
                print(f'  Fecha reporte:           {fecha.get("fmt", "N/A")}')
                print(f'  Total Revenue:           {latest.get("totalRevenue", {}).get("raw", 0):>20,.0f}')
                print(f'  Net Income:              {latest.get("netIncome", {}).get("raw", 0):>20,.0f}')
            else:
                print('  [AVISO] No disponible')
        except Exception as e:
            print(f'  [ERROR] {e}')

    else:
        print(f'[ERROR] Status code: {response.status_code}')

except Exception as e:
    print(f'[ERROR] Excepción: {e}')

print()
print('=' * 100)
print('COMPARACIÓN CON DATOS ACTUALES:')
print('=' * 100)
print('  Warehouse (Excel - datos CORRECTOS según validación):')
print('    Assets 2024:  52,095,441,000,000 CLP')
print('    Equity 2024:   5,622,999,000,000 CLP')
print()
print('  XBRL (incorrecto - subvaluado por ~100x):')
print('    Assets 2024:     801,845,962,000 CLP')
print()
print('  Yahoo Finance (si está disponible arriba):')
print('    Comparar escala y moneda')
print()
print('  CONCLUSIÓN:')
print('    - Si Yahoo Finance ≈ 52 billones CLP → Excel CORRECTO, XBRL incorrecto')
print('    - Si Yahoo Finance ≈ 801 billones CLP → XBRL correcto, Excel incorrecto')
print('=' * 100)
