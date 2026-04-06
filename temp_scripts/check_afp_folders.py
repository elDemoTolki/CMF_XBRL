"""
Verifica los archivos PDF en cada carpeta de AFP
para detectar el origen del problema de duplicación.
"""
import os
from pathlib import Path

DEFAULT_PDF_DIR = r"C:\Users\david\Downloads\Estado Resultados"

AFP_FOLDERS = {
    "Capital": "AFPCAPITAL.SN",
    "Habitat": "HABITAT.SN",
    "Planvital": "PLANVITAL.SN",
    "Provida": "PROVIDA.SN",
}

def main():
    print("=" * 60)
    print("VERIFICACIÓN DE CARPETAS AFP")
    print("=" * 60)
    
    for folder, ticker in AFP_FOLDERS.items():
        folder_path = os.path.join(DEFAULT_PDF_DIR, folder)
        print(f"\n{folder} ({ticker}):")
        
        if not os.path.isdir(folder_path):
            print(f"  ⚠️  Carpeta NO EXISTE")
            continue
        
        pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
        print(f"  PDFs encontrados: {len(pdf_files)}")
        
        for pdf in sorted(pdf_files):
            full_path = os.path.join(folder_path, pdf)
            size_mb = os.path.getsize(full_path) / (1024 * 1024)
            print(f"    - {pdf} ({size_mb:.2f} MB)")
    
    # Verificar si hay archivos duplicados entre carpetas
    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE DUPLICADOS ENTRE CARPETAS")
    print("=" * 60)
    
    files_by_name = {}
    for folder, ticker in AFP_FOLDERS.items():
        folder_path = os.path.join(DEFAULT_PDF_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        
        for pdf in os.listdir(folder_path):
            if pdf.lower().endswith('.pdf'):
                if pdf not in files_by_name:
                    files_by_name[pdf] = []
                files_by_name[pdf].append(folder)
    
    duplicates = {k: v for k, v in files_by_name.items() if len(v) > 1}
    
    if duplicates:
        print("\n⚠️  Archivos con el mismo nombre en múltiples carpetas:")
        for filename, folders in duplicates.items():
            print(f"  {filename}:")
            for f in folders:
                print(f"    - {f}")
    else:
        print("\n✓ No hay archivos con el mismo nombre en múltiples carpetas")
    
    # Verificar contenido similar por tamaño
    print("\n" + "=" * 60)
    print("VERIFICACIÓN POR TAMAÑO DE ARCHIVO")
    print("=" * 60)
    
    files_by_size = {}
    for folder, ticker in AFP_FOLDERS.items():
        folder_path = os.path.join(DEFAULT_PDF_DIR, folder)
        if not os.path.isdir(folder_path):
            continue
        
        for pdf in os.listdir(folder_path):
            if pdf.lower().endswith('.pdf'):
                full_path = os.path.join(folder_path, pdf)
                size = os.path.getsize(full_path)
                if size not in files_by_size:
                    files_by_size[size] = []
                files_by_size[size].append((folder, pdf))
    
    size_duplicates = {k: v for k, v in files_by_size.items() if len(v) > 1}
    
    if size_duplicates:
        print("\n⚠️  Archivos con el mismo tamaño (posibles duplicados):")
        for size, files in size_duplicates.items():
            print(f"\n  Tamaño: {size:,} bytes")
            for folder, pdf in files:
                print(f"    - {folder}/{pdf}")
    else:
        print("\n✓ No hay archivos con el mismo tamaño")

if __name__ == '__main__':
    main()