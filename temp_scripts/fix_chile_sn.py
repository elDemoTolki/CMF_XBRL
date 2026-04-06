"""
fix_chile_sn.py - Corrige CHILE.SN usando datos de API CMF (sin pandas)
Solución temporal al problema de DLLs de pandas
"""

import os
import sqlite3
import requests
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

API_KEY = os.getenv("CMF_API_KEY")
BASE_URL = "https://api.cmfchile.cl/api-sbifv3/recursos_api"
DB_PATH = os.path.join("output", "warehouse.db")

# Banco de Chile código en CMF
CHILE_CODE = "001"


def get_json(url):
    """Hace request a API CMF con manejo de errores."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def parse_clp(s):
    """Parsea número chileno con separadores de miles."""
    if not s or s == "":
        return 0.0
    return float(str(s).replace(".", "").replace(",", "."))


def fetch_chile_data(year, month=12):
    """Obtiene datos de Banco de Chile desde API CMF."""
    print(f"  Fetching CHILE.SN {year}-{month:02d}...")

    # Fetch balance
    balance_url = f"{BASE_URL}/banca/balance/{year}/{month:02d}/instituciones/{CHILE_CODE}?apikey={API_KEY}&formato=json"
    balance_data = get_json(balance_url)

    # Fetch income statement
    income_url = f"{BASE_URL}/banca/resultados/{year}/{month:02d}/instituciones/{CHILE_CODE}?apikey={API_KEY}&formato=json"
    income_data = get_json(income_url)

    if not balance_data or not income_data:
        print(f"    ERROR: No se pudieron obtener datos para {year}")
        return None

    # Parsear balance (diccionario de codigo_cuenta -> valor)
    balance = {}
    for item in balance_data.get("BancaBalances", []):
        code = item.get("CodigoCuenta")
        value = parse_clp(item.get("MonedaTotal", "0"))
        balance[code] = value

    # Parsear income statement
    income = {}
    for item in income_data.get("BancaResultados", []):
        code = item.get("CodigoCuenta")
        value = parse_clp(item.get("MonedaTotal", "0"))
        income[code] = value

    # Detectar esquema (nuevo 9 digitos vs legacy 7 digitos)
    scheme = "new" if any(len(c) == 9 for c in balance.keys()) else "legacy"
    scale = 1.0 if scheme == "new" else 1e6

    print(f"    Esquema: {scheme}, Scale: {scale}")

    # Mapeo de cuentas CMF → campos warehouse
    # Basado en concept_map_banks.yaml
    row = {
        'ticker': 'CHILE.SN',
        'year': year,
        'month': month,
        'industry': 'financial',
        'reporting_currency': 'CLP',
    }

    # Balance sheet mapping (codigos para esquema nuevo/legacy)
    balance_map = {
        'assets': ['101000000', '1010000'],  # Activos totales
        'current_assets': ['101010000', '1010100'],
        'non_current_assets': ['101020000', '1010200'],
        'liabilities': ['102000000', '1020000'],  # Pasivos totales
        'current_liabilities': ['102010000', '1020100'],
        'non_current_liabilities': ['102020000', '1020200'],
        'equity': ['103000000', '1030000'],  # Patrimonio
        'cash': ['101010100', '1010101'],  # Efectivo
        'trade_receivables': ['101010200', '1010102'],
        'loans_to_customers': ['101010300', '1010103'],  # Créditos clientes
        'deposits_from_customers': ['102010100', '1020101'],  # Depósitos clientes
    }

    # Income statement mapping
    income_map = {
        'revenue': ['301000000', '3010000'],  # Intereses y reajustes
        'interest_income': ['301010000', '3010100'],  # Ingresos intereses
        'interest_expense': ['301020000', '3010200'],  # Gastos intereses
        'net_interest_income': ['301030000', '3010300'],  # Margen intermediación
        'net_fee_income': ['302000000', '3020000'],  # Ingresos comisiones netos
        'employee_benefits': ['303000000', '3030000'],  # Gastos personal
        'operating_income': ['304000000', '3040000'],  # Resultado operacional
        'profit_before_tax': ['305000000', '3050000'],  # Resultado antes impuesto
        'income_tax': ['306000000', '3060000'],  # Impuesto a la renta
        'net_income': ['307000000', '3070000'],  # Ganancia pérdida
    }

    # Parse balance fields
    for field, codes in balance_map.items():
        value = None
        for code in codes:
            if code in balance and balance[code] != 0:
                value = balance[code] * scale
                break

        if value is not None and value != 0:
            row[field] = value

    # Parse income fields
    for field, codes in income_map.items():
        value = None
        for code in codes:
            if code in income and income[code] != 0:
                value = income[code] * scale
                break

        if value is not None and value != 0:
            row[field] = value

    return row


def upsert_chile_data(con, row):
    """Hace upert de datos de CHILE.SN al warehouse."""
    ticker = row['ticker']
    year = row['year']
    month = row['month']

    # Primero eliminar si existe
    cursor = con.cursor()
    cursor.execute(
        "DELETE FROM normalized_financials WHERE ticker = ? AND year = ? AND month = ?",
        (ticker, year, month)
    )

    # Construir INSERT dinámico
    fields = list(row.keys())
    values = [row[f] for f in fields]
    placeholders = ', '.join(['?' for _ in fields])
    field_names = ', '.join(fields)

    insert_sql = f"""
        INSERT INTO normalized_financials ({field_names})
        VALUES ({placeholders})
    """

    cursor.execute(insert_sql, values)
    con.commit()

    print(f"    Upserted: {len(fields)} fields for {ticker} {year}")


def main():
    """Función principal."""
    print("=" * 60)
    print("Corrigiendo CHILE.SN con datos de API CMF")
    print("=" * 60)
    print()

    if not API_KEY:
        print("ERROR: CMF_API_KEY no encontrada en .env")
        return

    if not os.path.exists(DB_PATH):
        print(f"ERROR: No existe {DB_PATH}")
        return

    # Conectar a database
    con = sqlite3.connect(DB_PATH)

    # Años a actualizar (2018-2025 según el Excel)
    years = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

    updated = 0
    for year in years:
        row = fetch_chile_data(year)
        if row:
            try:
                upsert_chile_data(con, row)
                updated += 1
            except Exception as e:
                print(f"    ERROR upserting {year}: {e}")

    con.close()

    print()
    print("=" * 60)
    print(f"✅ Actualizados {updated} años de CHILE.SN")
    print()
    print("Ahora recalcular ratios:")
    print("  python ratios.py")
    print("=" * 60)


if __name__ == '__main__':
    main()
