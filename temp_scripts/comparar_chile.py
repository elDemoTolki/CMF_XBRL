"""
comparar_chile.py - Comparar datos completos vs incompletos de CHILE.SN
"""

import sqlite3

con = sqlite3.connect('output/warehouse.db')
cursor = con.cursor()

print('CHILE.SN - Datos de años COMPLETOS (2010-2017 desde XBRL):')
print('=' * 80)
cursor.execute('''
    SELECT year, month,
           assets, liabilities, equity,
           revenue, net_income, operating_income,
           loans_to_customers, deposits_from_customers
    FROM normalized_financials
    WHERE ticker = 'CHILE.SN' AND year <= 2017
    ORDER BY year DESC
    LIMIT 3
''')

for row in cursor.fetchall():
    year, month, assets, liab, equity, rev, net_inc, op_inc, loans, deposits = row
    print(f'\nAño {year}-{month}:')
    print(f'  Assets:      {assets:,.0f if assets else "NULL"}')
    print(f'  Liabilities: {liab:,.0f if liab else "NULL"}')
    print(f'  Equity:      {equity:,.0f if equity else "NULL"}')
    print(f'  Revenue:     {rev:,.0f if rev else "NULL"}')
    print(f'  Net Income:  {net_inc:,.0f if net_inc else "NULL"}')
    print(f'  Op Income:   {op_inc:,.0f if op_inc else "NULL"}')
    print(f'  Loans:       {loans:,.0f if loans else "NULL"}')
    print(f'  Deposits:    {deposits:,.0f if deposits else "NULL"}')

print()
print('=' * 80)
print('CHILE.SN - Datos de años INCOMPLETOS (2018-2025 desde Excel):')
print('=' * 80)
cursor.execute('''
    SELECT year, month,
           assets, liabilities, equity,
           revenue, net_income, operating_income,
           loans_to_customers, deposits_from_customers
    FROM normalized_financials
    WHERE ticker = 'CHILE.SN' AND year >= 2018
    ORDER BY year DESC
    LIMIT 3
''')

for row in cursor.fetchall():
    year, month, assets, liab, equity, rev, net_inc, op_inc, loans, deposits = row
    print(f'\nAño {year}-{month}:')
    print(f'  Assets:      {assets:,.0f if assets else "NULL"}')
    print(f'  Liabilities: {liab:,.0f if liab else "NULL"}')
    print(f'  Equity:      {equity:,.0f if equity else "NULL"}')
    print(f'  Revenue:     {rev:,.0f if rev else "NULL"}')
    print(f'  Net Income:  {net_inc:,.0f if net_inc else "NULL"}')
    print(f'  Op Income:   {op_inc:,.0f if op_inc else "NULL"}')
    print(f'  Loans:       {loans:,.0f if loans else "NULL"}')
    print(f'  Deposits:    {deposits:,.0f if deposits else "NULL"}')

con.close()
