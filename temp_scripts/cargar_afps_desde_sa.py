"""
cargar_afps_desde_sa.py - Carga datos de AFPs desde StockAnalysis (sin pandas)
Carga net_income y dividends_paid para las 4 AFPs desde datos de StockAnalysis
"""
import sqlite3
import os

DB_PATH = os.path.join("output", "warehouse.db")

# Datos de StockAnalysis para AFPs (en MILLONES de CLP)
# Datos extraídos manualmente de las tablas financieras
afps_data = {
    'HABITAT.SN': {
        'name': 'AFP Habitat',
        'shares': 1000,  # millones de acciones
        'data': {
            2024: {'ni': 140146, 'div_ps': 110.000},
            2023: {'ni': 131600, 'div_ps': 115.000},
            2022: {'ni': 108847, 'div_ps': 108.000},
            2021: {'ni': 129863, 'div_ps': 115.000},
            2020: {'ni': 128629, 'div_ps': 100.000}
        }
    },
    'PLANVITAL.SN': {
        'name': 'AFP PlanVital',
        'shares': 2037,  # millones de acciones
        'data': {
            2024: {'ni': 53180, 'div_ps': 13.224},
            2023: {'ni': 48227, 'div_ps': 0},  # Sin dividend en StockAnalysis para 2023
            2022: {'ni': 36924, 'div_ps': 5.439},
            2021: {'ni': 25686, 'div_ps': 8.272},
            2020: {'ni': 21888, 'div_ps': 3.224}
        }
    },
    'PROVIDA.SN': {
        'name': 'AFP Provida',
        'shares': 328,  # millones de acciones
        'data': {
            2024: {'ni': 129398, 'div_ps': 394.000},
            2023: {'ni': 126481, 'div_ps': 345.000},
            2022: {'ni': 124478, 'div_ps': 335.000},
            2021: {'ni': 101017, 'div_ps': 455.500},
            2020: {'ni': 77373, 'div_ps': 235.800}
        }
    },
    'AFPCAPITAL.SN': {
        'name': 'AFP Capital',
        'shares': 3124,  # millones de acciones
        'data': {
            2024: {'ni': 102713, 'div_ps': 10.245},
            2023: {'ni': 106632, 'div_ps': 6.627},
            2022: {'ni': 88295, 'div_ps': 8.480},
            2021: {'ni': 73164, 'div_ps': 7.027},
            2020: {'ni': 55744, 'div_ps': 0}  # No hay dato de div para 2020
        }
    }
}

def cargar_afps():
    """Carga datos de AFPs al warehouse"""

    print('=' * 100)
    print('CARGANDO DATOS DE AFPs DESDE STOCKANALYSIS')
    print('=' * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    total_insertados = 0
    total_actualizados = 0
    total_errores = 0

    for ticker, afp_info in afps_data.items():
        print(f'{ticker} ({afp_info['name']}):')
        print('-' * 80)

        shares = afp_info['shares']

        for year, data in afp_info['data'].items():
            ni = data['ni']
            div_ps = data['div_ps']

            # Calcular dividends totales (en millones de CLP)
            div_total = div_ps * shares if div_ps and div_ps > 0 else None

            payout = (div_total / ni * 100) if div_total and ni else None

            print(f'  {year}:')
            print(f'    Net Income: {ni:,.0f}M CLP')
            print(f'    Dividend per Share: {div_ps:,.3f} CLP' if div_ps else '    Dividend per Share: N/A')
            print(f'    Shares: {shares:,}M')

            if div_total:
                print(f'    Dividendos Total: {div_total:,.0f}M CLP')
                print(f'    Payout Ratio: {payout:.2f}%')

            # Insertar o actualizar en warehouse
            try:
                # Verificar si ya existe
                cursor.execute('SELECT year FROM normalized_financials WHERE ticker = ? AND year = ?', (ticker, year))
                existe = cursor.fetchone()

                if existe:
                    # Actualizar
                    cursor.execute('''
                        UPDATE normalized_financials
                        SET net_income = ?, dividends_paid = ?
                        WHERE ticker = ? AND year = ?
                    ''', (ni, div_total, ticker, year))
                    print(f'    [OK] Actualizado')
                    total_actualizados += 1
                else:
                    # Insertar nuevo (mes=12 para anual)
                    cursor.execute('''
                        INSERT INTO normalized_financials
                        (ticker, year, month, net_income, dividends_paid)
                        VALUES (?, ?, 12, ?, ?)
                    ''', (ticker, year, ni, div_total))
                    print(f'    [OK] Insertado')
                    total_insertados += 1

                con.commit()

            except Exception as e:
                con.rollback()
                total_errores += 1
                print(f'    [ERROR] {e}')

            print()

    con.close()

    print('=' * 100)
    print('RESUMEN')
    print('=' * 100)
    print(f'Registros insertados: {total_insertados}')
    print(f'Registros actualizados: {total_actualizados}')
    print(f'Errores: {total_errores}')
    print()

    if total_insertados > 0 or total_actualizados > 0:
        print('[OK] Datos de AFPs cargados exitosamente')
        verificar_afps()

def verificar_afps():
    """Verifica que los datos de AFPs se hayan cargado correctamente"""

    print()
    print('=' * 100)
    print('VERIFICACION DE DATOS DE AFPs')
    print('=' * 100)
    print()

    con = sqlite3.connect(DB_PATH)
    cursor = con.cursor()

    for ticker in afps_data.keys():
        print(f'{ticker}:')

        cursor.execute('''
            SELECT year, net_income, dividends_paid
            FROM normalized_financials
            WHERE ticker = ? AND year BETWEEN 2020 AND 2024
            ORDER BY year DESC
        ''', (ticker,))

        rows = cursor.fetchall()

        if rows:
            for year, ni, div in rows:
                if ni:
                    payout = (div / ni * 100) if div and ni else 0
                    ni_b = ni / 1000
                    div_b = div / 1000 if div else 0
                    print(f'  {year}: NI={ni:>10,.0f}M CLP ({ni_b:>7.1f}B) | Div={div:>10,.0f}M CLP ({div_b:>7.1f}B) | Payout={payout:6.2f}%')
                else:
                    print(f'  {year}: [Sin datos]')
        else:
            print(f'  [Sin datos]')

        print()

    # Estadísticas finales
    print('ESTADISTICAS FINALES:')
    print('-' * 80)

    cursor.execute('''
        SELECT
            COUNT(DISTINCT ticker) as afps,
            SUM(CASE WHEN dividends_paid IS NOT NULL AND dividends_paid > 0 THEN 1 ELSE 0 END) as con_div
        FROM normalized_financials
        WHERE ticker IN ('HABITAT.SN', 'PLANVITAL.SN', 'PROVIDA.SN', 'AFPCAPITAL.SN')
    ''')

    afps_total, con_div = cursor.fetchone()

    print(f'AFPs en warehouse: {afps_total}/4')
    print(f'AFPs con dividends: {con_div}/4')
    print()

    con.close()

if __name__ == '__main__':
    cargar_afps()
