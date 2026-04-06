"""
extraer_pdf_chile.py - Extrae datos financieros de PDFs de Banco de Chile
Versión mejorada que busca tablas estructuradas
"""

import pdfplumber
import re
import os

PDF_DIR = r"C:\Users\david\Downloads\Estado Resultados\Chile"

def extraer_tablas_balance(pdf_path):
    """Extrae tabla de balance general del PDF"""
    print(f"\nExtrayendo Balance: {os.path.basename(pdf_path)}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            datos = {}

            for page_num, page in enumerate(pdf.pages[:50], 1):
                # Extraer tablas de esta página
                tables = page.extract_tables()

                if not tables:
                    continue

                for table in tables:
                    # Buscar en cada tabla
                    for row in table:
                        if not row:
                            continue

                        # Unir todas las celdas de la fila en un solo string
                        row_text = ' '.join([cell or '' for cell in row])

                        # Buscar ACTIVO TOTAL
                        if any(keyword in row_text.upper() for keyword in ['ACTIVO TOTAL', 'TOTAL ACTIVO']):
                            # Buscar valor numérico más grande en la fila
                            for cell in row:
                                if cell:
                                    # Extraer número (manejando puntos y comas)
                                    match = re.search(r'[\d\.]+,\d+', cell.replace('.', 'X').replace('X', '.').replace(',', ''))
                                    if match:
                                        valor = re.sub(r'[^\d.]', '', match.group())
                                        try:
                                            valor_float = float(valor)
                                            # Solo guardar si es un valor razonable (entre 1 billón y 100 billones)
                                            if 1_000_000_000_000 < valor_float < 100_000_000_000_000:
                                                if 'assets' not in datos or valor_float > datos.get('assets', 0):
                                                    datos['assets'] = valor_float
                                        except:
                                            pass

                        # Buscar PASIVO TOTAL
                        if any(keyword in row_text.upper() for keyword in ['PASIVO TOTAL', 'TOTAL PASIVO']):
                            for cell in row:
                                if cell:
                                    match = re.search(r'[\d\.]+,\d+', cell.replace('.', 'X').replace('X', '.').replace(',', ''))
                                    if match:
                                        valor = re.sub(r'[^\d.]', '', match.group())
                                        try:
                                            valor_float = float(valor)
                                            if 1_000_000_000_000 < valor_float < 100_000_000_000_000:
                                                if 'liabilities' not in datos or valor_float > datos.get('liabilities', 0):
                                                    datos['liabilities'] = valor_float
                                        except:
                                            pass

                        # Buscar PATRIMONIO TOTAL
                        if any(keyword in row_text.upper() for keyword in ['PATRIMONIO TOTAL', 'TOTAL PATRIMONIO']):
                            for cell in row:
                                if cell:
                                    match = re.search(r'[\d\.]+,\d+', cell.replace('.', 'X').replace('X', '.').replace(',', ''))
                                    if match:
                                        valor = re.sub(r'[^\d.]', '', match.group())
                                        try:
                                            valor_float = float(valor)
                                            if 1_000_000_000_000 < valor_float < 100_000_000_000_000:
                                                if 'equity' not in datos or valor_float > datos.get('equity', 0):
                                                    datos['equity'] = valor_float
                                        except:
                                            pass

            return datos

    except Exception as e:
        print(f"  [ERROR] {e}")
        return None

def extraer_tablas_resultados(pdf_path):
    """Extrae tabla de estado de resultados del PDF"""
    print(f"\nExtrayendo Estado de Resultados: {os.path.basename(pdf_path)}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            datos = {}

            for page_num, page in enumerate(pdf.pages[:50], 1):
                tables = page.extract_tables()

                if not tables:
                    continue

                for table in tables:
                    for row in table:
                        if not row:
                            continue

                        row_text = ' '.join([cell or '' for cell in row])

                        # Buscar UTILIDAD NETA
                        if any(keyword in row_text.upper() for keyword in ['UTILIDAD NETA', 'UTILIDAD DEL EJERCICIO']):
                            for cell in row:
                                if cell:
                                    match = re.search(r'[\d\.]+,\d+', cell.replace('.', 'X').replace('X', '.').replace(',', ''))
                                    if match:
                                        valor = re.sub(r'[^\d.]', '', match.group())
                                        try:
                                            valor_float = float(valor)
                                            if 100_000_000_000 < valor_float < 100_000_000_000_000:
                                                if 'net_income' not in datos or valor_float > datos.get('net_income', 0):
                                                    datos['net_income'] = valor_float
                                        except:
                                            pass

                        # Buscar INGRESOS POR INTERESES
                        if any(keyword in row_text.upper() for keyword in ['INGRESOS POR INTERESES', 'INTERESES Y SIMILARES']):
                            for cell in row:
                                if cell:
                                    match = re.search(r'[\d\.]+,\d+', cell.replace('.', 'X').replace('X', '.').replace(',', ''))
                                    if match:
                                        valor = re.sub(r'[^\d.]', '', match.group())
                                        try:
                                            valor_float = float(valor)
                                            if 1_000_000_000_000 < valor_float < 100_000_000_000_000:
                                                if 'revenue' not in datos or valor_float > datos.get('revenue', 0):
                                                    datos['revenue'] = valor_float
                                        except:
                                            pass

            return datos

    except Exception as e:
        print(f"  [ERROR] {e}")
        return None

# Probar con 2024
pdf_2024 = os.path.join(PDF_DIR, "EEFF_Banco_de_Chile_12-2024.pdf")

print("=" * 100)
print("EXTRAYENDO DATOS DE PDF - BANCO DE CHILE 2024")
print("=" * 100)

datos_balance = extraer_tablas_balance(pdf_2024)
datos_resultados = extraer_tablas_resultados(pdf_2024)

# Combinar
todos_datos = {}
if datos_balance:
    todos_datos.update(datos_balance)
if datos_resultados:
    todos_datos.update(datos_resultados)

print()
print("=" * 100)
print("DATOS EXTRAÍDOS:")
print("=" * 100)

if todos_datos:
    for campo, valor in todos_datos.items():
        print(f"  {campo:<20} {valor:,.0f}")

    print()
    print("COMPARACIÓN CON WAREHOUSE (Excel):")
    print("-" * 100)

    import sqlite3
    con = sqlite3.connect('output/warehouse.db')
    cursor = con.cursor()

    cursor.execute('''
        SELECT assets, liabilities, equity
        FROM normalized_financials
        WHERE ticker = 'CHILE.SN' AND year = 2024
    ''')
    row = cursor.fetchone()

    if row:
        assets_w, liab_w, equity_w = row
        print(f"  Assets  (Warehouse): {assets_w:,.0f}")
        print(f"  Assets  (PDF):       {todos_datos.get('assets', 'NO ENCONTRADO'):,.0f if 'assets' in todos_datos else 'NO ENCONTRADO'}")
        print()
        print(f"  Liab    (Warehouse): {liab_w}")
        print(f"  Liab    (PDF):       {todos_datos.get('liabilities', 'NO ENCONTRADO'):,.0f if 'liabilities' in todos_datos else 'NO ENCONTRADO'}")
        print()
        print(f"  Equity  (Warehouse): {equity_w:,.0f}")
        print(f"  Equity  (PDF):       {todos_datos.get('equity', 'NO ENCONTRADO'):,.0f if 'equity' in todos_datos else 'NO ENCONTRADO'}")

    con.close()
else:
    print("  No se pudieron extraer datos")

print("=" * 100)
