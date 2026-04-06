"""
Analiza el contenido real de los PDFs de PROVIDA vs PLANVITAL
para detectar por qué se extraen los mismos datos.
"""
import pdfplumber
import os
import re

DEFAULT_PDF_DIR = r"C:\Users\david\Downloads\Estado Resultados"

def extract_text_sample(pdf_path, max_pages=3):
    """Extrae una muestra de texto del PDF"""
    samples = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages[:max_pages]):
                text = page.extract_text() or ""
                # Primeros 500 caracteres
                samples.append(f"--- Página {i+1} ---\n{text[:800]}")
    except Exception as e:
        samples.append(f"Error: {e}")
    return samples

def extract_first_table(pdf_path):
    """Extrae la primera tabla encontrada"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages[:5]):
                tables = page.extract_tables()
                if tables:
                    return f"Página {i+1}, Tabla 1:\n{tables[0][:10]}"  # Primeras 10 filas
    except Exception as e:
        return f"Error: {e}"
    return "No se encontraron tablas"

def find_company_name(pdf_path):
    """Busca el nombre de la empresa en el PDF"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:3]:
                text = page.extract_text() or ""
                # Buscar nombres de AFP
                if "PROVIDA" in text.upper():
                    return "PROVIDA"
                if "PLANVITAL" in text.upper():
                    return "PLANVITAL"
                if "CAPITAL" in text.upper():
                    return "CAPITAL"
                if "HABITAT" in text.upper():
                    return "HABITAT"
    except:
        pass
    return "Desconocido"

def main():
    print("=" * 70)
    print("ANÁLISIS DE CONTENIDO PDF - PROVIDA vs PLANVITAL")
    print("=" * 70)
    
    # Comparar archivos 2023
    planvital_2023 = os.path.join(DEFAULT_PDF_DIR, "Planvital", "31 de diciembre 2023.pdf")
    provida_2023 = os.path.join(DEFAULT_PDF_DIR, "Provida", "Dic2023.pdf")
    
    print("\n" + "=" * 70)
    print("PLANVITAL 2023: 31 de diciembre 2023.pdf")
    print("=" * 70)
    
    company = find_company_name(planvital_2023)
    print(f"\nNombre de empresa detectado: {company}")
    
    print("\nMuestra de texto:")
    for sample in extract_text_sample(planvital_2023):
        print(sample)
        print()
    
    print("\n" + "=" * 70)
    print("PROVIDA 2023: Dic2023.pdf")
    print("=" * 70)
    
    company = find_company_name(provida_2023)
    print(f"\nNombre de empresa detectado: {company}")
    
    print("\nMuestra de texto:")
    for sample in extract_text_sample(provida_2023):
        print(sample)
        print()
    
    # Comparar archivo grande de PROVIDA 2025
    print("\n" + "=" * 70)
    print("PROVIDA 2025 (44 MB): Dic2025.pdf")
    print("=" * 70)
    
    provida_2025 = os.path.join(DEFAULT_PDF_DIR, "Provida", "Dic2025.pdf")
    company = find_company_name(provida_2025)
    print(f"\nNombre de empresa detectado: {company}")
    
    print("\nMuestra de texto (primeras 3 páginas):")
    for sample in extract_text_sample(provida_2025):
        print(sample)
        print()
    
    # Verificar si Dic2023.pdf en PROVIDA es realmente de PROVIDA
    print("\n" + "=" * 70)
    print("VERIFICACIÓN CRUZADA")
    print("=" * 70)
    
    # Leer el nombre del archivo y ver si coincide con el contenido
    for folder in ["Planvital", "Provida"]:
        folder_path = os.path.join(DEFAULT_PDF_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        
        print(f"\n{folder}:")
        for pdf in sorted(os.listdir(folder_path)):
            if pdf.lower().endswith('.pdf'):
                full_path = os.path.join(folder_path, pdf)
                company = find_company_name(full_path)
                match = "✓" if company.upper() in folder.upper() or company == "Desconocido" else "⚠️ NO COINCIDE"
                print(f"  {pdf}: contenido={company} {match}")

if __name__ == '__main__':
    main()