"""
reparsear_chile_sn.py - Reparsa XBRLs de CHILE.SN años 2018-2025
Verifica si los datos faltantes están en los XBRLs originales
"""

import sys
import os
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict

NAMESPACES = {
    'xbrli': 'http://www.xbrl.org/2003/instance',
    'ifrs-full': 'http://xbrl.ifrs.org/taxonomy/2023-03-24/ifrs-full',
}

def parse_chile_year(year):
    """Parsea un archivo XBRL de CHILE.SN para un año específico"""
    zip_path = f"data/CHILE_SN_90331000/{year}/12/CHILE_SN_90331000_{year}_12.zip"

    if not os.path.exists(zip_path):
        return None

    print(f"\n{'='*100}")
    print(f"AÑO {year} - {zip_path}")
    print('='*100)

    # Extraer y leer el XBRL
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        xml_files = [f for f in zip_ref.namelist() if f.endswith('.xml') and 'xsd' not in f]

        if not xml_files:
            print(f"[ERROR] No se encontró archivo XML en {zip_path}")
            return None

        xml_content = zip_ref.read(xml_files[0])

    # Parsear XML
    root = ET.fromstring(xml_content)

    # Buscar conceptos relevantes (buscando en todos los namespaces)
    datos_encontrados = {}

    # Conceptos bancarios que buscamos
    conceptos_buscar = [
        ('Assets', 'ifrs-full'),
        ('Liabilities', 'ifrs-full'),
        ('Equity', 'ifrs-full'),
        ('Revenue', 'ifrs-full'),
        ('ProfitLoss', 'ifrs-full'),  # net_income
        ('ProfitLossFromOperatingActivities', 'ifrs-full'),
    ]

    # Buscar todos los elementos para encontrar conceptos
    all_elements = {}
    for elem in root.iter():
        if elem.text and elem.text.strip():
            # Extraer el nombre del concepto
            concept_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            # Solo guardar si parece un concepto financiero (empieza con mayúscula)
            if concept_name[0].isupper():
                # Intentar convertir a número
                try:
                    valor = float(elem.text)
                    if valor != 0:
                        if concept_name not in all_elements:
                            all_elements[concept_name] = []

                        context_ref = elem.get('contextRef', '')

                        # Obtener fecha del contexto
                        contexto = root.find(f".//*[@id='{context_ref}']")
                        fecha = context_ref
                        if contexto is not None:
                            periodo = contexto.find('.//{*}period/{*}endDate')
                            if periodo is not None and periodo.text:
                                fecha = periodo.text

                        all_elements[concept_name].append({
                            'valor': valor,
                            'contexto': context_ref,
                            'fecha': fecha,
                            'decimals': elem.get('decimals', '')
                        })
                except (ValueError, TypeError):
                    pass

    # Buscar conceptos específicos
    for concepto_buscado, namespace in conceptos_buscar:
        # Búsqueda exacta
        if concepto_buscado in all_elements:
            datos_encontrados[concepto_buscado] = all_elements[concepto_buscado][-1]  # Último valor
        else:
            # Búsqueda parcial (contiene el nombre)
            for key in all_elements.keys():
                if concepto_buscado.lower() in key.lower():
                    datos_encontrados[concepto_buscado] = all_elements[key][-1]
                    break

    # Imprimir resultados
    print("\nConceptos encontrados:")
    for concepto_buscado, _ in conceptos_buscar:
        if concepto_buscado in datos_encontrados:
            info = datos_encontrados[concepto_buscado]
            val = info['valor']
            print(f"  [OK] {concepto_buscado:<45} {val:>20,.0f}  (contexto: {info['contexto']}, fecha: {info['fecha']})")
        else:
            print(f"  [X]  {concepto_buscado:<45} NO ENCONTRADO")

    # Mostrar algunos conceptos disponibles
    print(f"\nTotal conceptos únicos con valores: {len(all_elements)}")
    print("\nPrimeros 20 conceptos disponibles:")
    for i, key in enumerate(sorted(all_elements.keys())[:20]):
        valores = all_elements[key]
        print(f"  {i+1:2d}. {key:<45} ({len(valores)} ocurrencias)")

    if len(all_elements) > 20:
        print(f"  ... y {len(all_elements) - 20} más")

    return datos_encontrados

print("="*100)
print("REPARSEANDO XBRLs - BANCO DE CHILE (CHILE.SN)")
print("Años 2018-2025")
print("="*100)

annos_a_revisar = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

resumen = {}

for anno in annos_a_revisar:
    datos = parse_chile_year(anno)
    resumen[anno] = datos is not None

print()
print("="*100)
print("RESUMEN")
print("="*100)

print("\nAños con datos parseados:")
for anno, exito in resumen.items():
    estado = "[OK]" if exito else "[ERROR]"
    print(f"  {estado} {anno}")

print()
print("CONCLUSION:")
print("  Si los conceptos [Assets, Liabilities, Equity, Revenue, ProfitLoss] aparecen como [OK] arriba,")
print("  entonces es POSIBLE recuperar los datos faltantes reparsando los XBRLs de CHILE.SN")
print()
print("ACCION RECOMENDADA:")
print("  1. Hacer backup de warehouse.db actual")
print("  2. Eliminar datos de CHILE.SN años 2018-2025 del warehouse")
print("  3. Ejecutar: python xbrl_parser.py --ticker CHILE.SN --years 2018,2019,2020,2021,2022,2023,2024,2025")
print("  4. Verificar que los datos se hayan cargado correctamente")
print("="*100)
