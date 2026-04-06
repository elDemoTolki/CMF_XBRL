"""
analizar_pdf_chile.py - Analiza PDFs de Banco de Chile para extraer datos
Usa pdfplumber para extraer tablas de estados financieros
"""

import pdfplumber
import re
import os

# Ruta de Windows (ajustar según necesidad)
PDF_DIR = r"C:\Users\david\Downloads\Estado Resultados\Chile"

# Mapeo de términos a buscar (en español)
BUSQUEDA = {
    'assets': ['ACTIVO TOTAL', 'Activo Total', 'Total Activo', 'Total Activos'],
    'liabilities': ['PASIVO TOTAL', 'Pasivo Total', 'Total Pasivo'],
    'equity': ['PATRIMONIO TOTAL', 'Patrimonio Total', 'Total Patrimonio'],
    'revenue': ['INGRESOS POR INTERESES', 'Ingresos por Intereses', 'Intereses y similares'],
    'net_income': ['UTILIDAD NETA', 'Utilidad Neta', 'Resultado del Ejercicio'],
}

def limpiar_valor(valor_str):
    """Convierte string de valor a número"""
    if not valor_str:
        return None

    # Eliminar espacios, puntos de miles y paréntesis
    valor_str = valor_str.replace(' ', '').replace('.', '')
    valor_str = valor_str.replace('(', '-').replace(')', '')

    # Eliminar otros caracteres no numéricos excepto signo y números
    valor_str = re.sub(r'[^\d-]', '', valor_str)

    if not valor_str or valor_str == '-':
        return None

    try:
        return float(valor_str)
    except:
        return None

def analizar_pdf(pdf_path):
    """Analiza un PDF de Banco de Chile"""
    print(f"\nAnalizando: {os.path.basename(pdf_path)}")
    print("-" * 100)

    if not os.path.exists(pdf_path):
        print(f"  [ERROR] No existe: {pdf_path}")
        return None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"  Páginas: {len(pdf.pages)}")

            # Buscar en todas las páginas
            datos_encontrados = {}

            for page_num, page in enumerate(pdf.pages[:30], 1):  # Primeras 30 páginas
                text = page.extract_text()

                if not text:
                    continue

                # Buscar tabla de balance o estado de resultados
                lines = text.split('\n')

                for i, line in enumerate(lines):
                    # Buscar términos clave
                    for campo, terminos in BUSQUEDA.items():
                        if campo in datos_encontrados:
                            continue  # Ya encontrado

                        for termino in terminos:
                            if termino.upper() in line.upper():
                                # Buscar valor en las próximas líneas
                                for j in range(i+1, min(i+10, len(lines))):
                                    valor = limpiar_valor(lines[j].strip())
                                    if valor and abs(valor) > 1_000_000:  # Valor razonable
                                        datos_encontrados[campo] = valor
                                        print(f"  [OK] {campo:<20} = {valor:,.0f} (pág {page_num})")
                                        break
                                break

            return datos_encontrados

    except Exception as e:
        print(f"  [ERROR] Excepción: {e}")
        return None

# Analizar PDF de 2024
pdf_2024 = os.path.join(PDF_DIR, "EEFF_Banco_de_Chile_12-2024.pdf")

datos_2024 = analizar_pdf(pdf_2024)

print()
print("=" * 100)
print("RESULTADO 2024:")
print("=" * 100)

if datos_2024:
    for campo, valor in datos_2024.items():
        print(f"  {campo:<20} {valor:,.0f}")
else:
    print("  No se pudieron extraer datos")

print()
print("NOTA: Si los valores parecen pequeños, puede requerir ajuste de escala (miles, millones)")
