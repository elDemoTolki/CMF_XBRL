"""
analizar_xbrl_chile.py - Analiza datos de XBRL de Banco de Chile
Revisa qué campos están disponibles para completar los datos faltantes
"""

import zipfile
import xml.etree.ElementTree as ET
import os

NAMESPACE = {'xbrli': 'http://www.xbrl.org/2003/instance'}

# Campos que faltan en el warehouse para CHILE.SN
CAMPOS_FALTANTES = [
    'Liabilities',
    'Revenue',
    'ProfitLoss',  # net_income
    'ProfitLossFromOperatingActivities',  # operating_income
    'DepositsFromCustomers',
    'LoansToCustomers',
]

def analizar_xbrl(anno):
    """Analiza un archivo XBRL de un año específico"""
    zip_path = f"data/CHILE_SN_90331000/{anno}/12/CHILE_SN_90331000_{anno}_12.zip"

    if not os.path.exists(zip_path):
        return None

    # Extraer y leer el XBRL
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Buscar el archivo .xml principal
        xml_files = [f for f in zip_ref.namelist() if f.endswith('.xml') and 'xsd' not in f]

        if not xml_files:
            return None

        xml_content = zip_ref.read(xml_files[0])

    # Parsear XML
    root = ET.fromstring(xml_content)

    # Buscar los campos faltantes
    encontrados = {}

    for campo in CAMPOS_FALTANTES:
        # Buscar cualquier elemento que contenga el nombre del campo
        # Los nombres en XBRL pueden tener prefijos de esquema
        for elem in root.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            if campo.lower() in tag_name.lower():
                # Obtener el contexto (fecha)
                context_ref = elem.get('contextRef', '')
                # Buscar el elemento de contexto para obtener la fecha
                contexto = root.find(f".//*[@id='{context_ref}']")

                if contexto is not None:
                    # Buscar periodo
                    periodo = contexto.find('.//{*}period')
                    if periodo is not None:
                        fecha_elem = periodo.find('.//{*}endDate')
                        if fecha_elem is not None:
                            fecha = fecha_elem.text
                        else:
                            fecha = context_ref
                    else:
                        fecha = context_ref
                else:
                    fecha = context_ref

                # Obtener el valor
                valor = elem.text
                if valor and valor.replace('.', '').replace('-', '').replace('e', '').replace('E', '').replace('+', '').isdigit():
                    valor_num = float(valor)
                    if abs(valor_num) > 0:
                        if campo not in encontrados:
                            encontrados[campo] = {'valor': valor_num, 'contexto': fecha, 'tag': tag_name}

    return encontrados

print("=" * 100)
print("ANALISIS DE XBRL - BANCO DE CHILE (CHILE.SN)")
print("=" * 100)
print()
print("Buscando campos faltantes en warehouse:")
for campo in CAMPOS_FALTANTES:
    print(f"  - {campo}")
print()
print("=" * 100)
print()

# Analizar algunos años clave
annos_clave = [2024, 2023, 2020, 2018, 2015]

for anno in annos_clave:
    print(f"\nAÑO {anno}:")
    print("-" * 100)

    encontrados = analizar_xbrl(anno)

    if encontrados is None:
        print("  [ERROR] No se pudo leer el archivo XBRL")
        continue

    if not encontrados:
        print("  [AVISO] No se encontraron los campos buscados")
        print("  Nota: Puede ser que los nombres de los tags sean diferentes")
        continue

    for campo, info in encontrados.items():
        print(f"  [OK] {campo:<50} {info['valor']:>20,.0f}  ({info['contexto']})")

print()
print("=" * 100)
print()
print("CONCLUSION:")
print("  Si los campos aparecen como [OK] arriba, es POSIBLE completar desde XBRL")
print("  Si no aparecen, puede ser:")
print("    1. El XBRL usa nombres diferentes para los conceptos")
print("    2. Los datos están en un formato diferente (unidades, contexto)")
print("    3. El banco no reporta esos campos en XBRL")
print()
print("RECOMENDACION:")
print("  Ejecutar: python xbrl_parser.py (para re-parsear todos los XBRLs)")
print("  Luego verificar: SELECT * FROM normalized_financials WHERE ticker = 'CHILE.SN' AND year >= 2018")
print("=" * 100)
