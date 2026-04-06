"""
extraer_chile_pdf_simple.py - Enfoque simple: buscar patrones numéricos grandes
"""

import pdfplumber
import re
import sqlite3

pdf_path = r'C:\Users\david\Downloads\Estado Resultados\Chile\EEFF_Banco_de_Chile_12-2024.pdf'
DB_PATH = 'output/warehouse.db'

print('=' * 100)
print('EXTRAYENDO DATOS DE PDF - BANCO DE CHILE 2024')
print('=' * 100)
print()

# Obtener datos actuales del warehouse (Excel)
con = sqlite3.connect(DB_PATH)
cursor = con.cursor()

cursor.execute('''
    SELECT assets, equity
    FROM normalized_financials
    WHERE ticker = 'CHILE.SN' AND year = 2024
''')

row = cursor.fetchone()
if row:
    assets_excel, equity_excel = row
    print(f'Datos actuales (Excel):')
    print(f'  Assets: {assets_excel:,.0f} CLP')
    print(f'  Equity: {equity_excel:,.0f} CLP')
    print()

con.close()

# Buscar en el PDF
print('Buscando en PDF...')
print('-' * 100)

with pdfplumber.open(pdf_path) as pdf:
    # Buscar en todas las páginas
    for page_num, page in enumerate(pdf.pages[:50], 1):
        text = page.extract_text()

        if not text:
            continue

        lines = text.split('\n')

        for i, line in enumerate(lines):
            # Buscar líneas con números muy grandes (formato chileno: puntos como separadores de miles)
            # Patrón: número con puntos (miles) y comas (decimales)
            matches = re.findall(r'(\d{1,3}\.\d{3}\.\d{3},\d{2})', line)

            if matches:
                # Limpiar y convertir a número
                for match in matches:
                    # Quitar puntos, mantener coma decimal
                    valor_str = match.replace('.', '')

                    # La coma es decimal, convertirla a punto
                    valor_str = valor_str.replace(',', '.')

                    try:
                        valor = float(valor_str)

                        # Solo valores muy grandes (> 1 billón CLP)
                        if valor > 1_000_000_000_000:
                            # Verificar si está cerca de los valores del Excel
                            if abs(valor - assets_excel) / assets_excel < 0.1:  # ±10%
                                print(f'[POSIBLE ASSETS] Página {page_num}: {valor:,.0f} (línea: {line.strip()[:80]})')

                            if abs(valor - equity_excel) / equity_excel < 0.1:
                                print(f'[POSIBLE EQUITY]  Página {page_num}: {valor:,.0f} (línea: {line.strip()[:80]})')
                    except:
                        pass

print()
print('=' * 100)
print('NOTA: Buscando valores que coincidan con el Excel (±10%)')
print('      Esto ayuda a identificar las filas correctas en el PDF')
print('=' * 100)
