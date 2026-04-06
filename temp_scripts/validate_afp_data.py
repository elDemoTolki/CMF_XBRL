"""
validate_afp_data.py — Validación de datos AFP contra fuentes externas
======================================================================

Valida los datos extraídos de los PDFs de AFPs contra:
1. Detección de duplicados entre tickers
2. Coherencia interna (accounting identity)
3. Comparación con datos públicos de Superintendencia de Pensiones
4. Rangos razonables para métricas financieras

Uso:
    python validate_afp_data.py
    python validate_afp_data.py --input "C:\\Users\\david\\Downloads\\Estado Resultados"
"""

import argparse
import logging
import os
import re
from collections import defaultdict
from typing import Optional

import pandas as pd
import pdfplumber
import yaml

# Importar funciones del pipeline
from afp_pipeline import (
    AFP_TICKERS,
    FOLDER_TO_TICKER,
    load_concept_map,
    parse_pdf,
    map_fields,
    find_pdf_files,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ── Datos de referencia de Superintendencia de Pensiones ───────────────────────
# Fuente: Memorias y Estados Financieros públicos de cada AFP
# Actualizado: Datos históricos conocidos para validación

REFERENCE_DATA = {
    "AFPCAPITAL.SN": {
        # Datos de memorias anuales y sitios públicos
        # Valores en millones de CLP
        # NOTA: fee_income usa código 85.70.010 (Ingresos ordinarios) que es más amplio que comisiones
        2020: {"net_income": 87_047_237, "equity": 416_763_980, "fee_income": 146_683_134, "contributors": 1_634_208},
        2021: {"net_income": 59_912_751, "equity": 414_857_775, "fee_income": 149_043_800, "contributors": 1_620_194},
        2022: {"net_income": 73_164_253, "equity": 426_733_714, "fee_income": 163_319_880, "contributors": 1_575_544},
        2023: {"net_income": 88_294_898, "equity": 452_366_991, "fee_income": 181_129_511, "contributors": 1_523_703},
        2024: {"net_income": 106_632_475, "equity": 474_753_097, "fee_income": 197_875_487, "contributors": 1_462_611},
        2025: {"net_income": 102_713_160, "equity": 502_438_517, "fee_income": 205_892_506, "contributors": 1_420_816},
    },
    "PROVIDA.SN": {
        # AFP Provida - Valores en millones de CLP
        # Provida es la AFP más grande de Chile por número de afiliados
        # NOTA: Los PDFs nuevos tienen datos diferentes, actualizar después de validar
        2019: {"fee_income": 29_621_640, "contributors": 3_028_356},  # Pendiente verificar con PDFs correctos
        2020: {"fee_income": 28_931_083, "contributors": 2_949_374},
        2021: {"fee_income": 25_050_093, "contributors": 2_914_880},
        2023: {"fee_income": 38_054_553, "contributors": 2_782_164},
        2024: {"fee_income": 39_940_512, "contributors": 2_712_979},
        2025: {"fee_income": 42_328_783, "contributors": 2_635_691},
    },
    "PLANVITAL.SN": {
        # AFP PlanVital - Valores usando código 85.70.010 (Ingresos ordinarios)
        # PlanVital tiene TAMBIÉN código 71.00.000 (solo comisiones) pero es más pequeño
        # NOTA: Equity de PlanVital es menor porque es administrada por el Estado
        2020: {"fee_income": 66_534_334, "contributors": 1_714_579},  # 85.70.010
        2021: {"fee_income": 65_478_505, "contributors": 1_677_911},  # 85.70.010
        2022: {"fee_income": 77_015_876, "contributors": 1_663_543},  # 85.70.010
        2023: {"fee_income": 93_371_411, "contributors": 1_647_606},  # 85.70.010
        2024: {"fee_income": 107_781_770, "contributors": 1_631_866}, # 85.70.010
        2025: {"fee_income": 119_823_071, "contributors": 1_607_685}, # 85.70.010
    },
    "HABITAT.SN": {
        # AFP Habitat - Valores de referencia
        # Habitat es la segunda AFP más grande
        2020: {"contributors": 2_800_000},  # Aproximado
        2023: {"contributors": 2_500_000},  # Aproximado
        2024: {"contributors": 2_400_000},  # Aproximado
    },
}

# Rangos esperados para validación (en millones CLP, excepto ratios)
EXPECTED_RANGES = {
    "net_income": (0, 300_000_000),  # 0 a 300 mil millones
    "equity": (50_000_000, 2_000_000_000),  # 50MM a 2 billones (ajustado para AFPs más pequeñas)
    "fee_income": (3_000_000, 300_000_000),  # 3MM a 300 mil millones (ajustado mínimo)
    "contributors": (1_000_000, 4_000_000),  # 1 a 4 millones de afiliados
    "fee_margin": (0.2, 5.0),  # 20% a 500% (AFPs tienen ingresos no operacionales)
    "roe": (0.05, 0.50),  # 5% a 50% (algunas AFPs tienen ROE alto)
}

# Número de afiliados típicos por AFP (para detectar errores de asignación)
TYPICAL_CONTRIBUTORS = {
    "PROVIDA.SN": (2_500_000, 3_600_000),  # La más grande
    "HABITAT.SN": (2_200_000, 3_000_000),  # Segunda
    "AFPCAPITAL.SN": (1_200_000, 1_800_000),  # Mediana
    "PLANVITAL.SN": (1_500_000, 2_000_000),  # Pequeña (administrada por Estado)
}


def validate_duplicate_detection(records: list[dict]) -> dict:
    """
    Detecta registros duplicados entre tickers (mismo año, mismos valores).
    
    Esto detecta el problema observado: PROVIDA y PLANVITAL con datos idénticos.
    """
    issues = []
    
    # Agrupar por año
    by_year = defaultdict(list)
    for r in records:
        by_year[r["year"]].append(r)
    
    # Comparar pares de tickers por año
    for year, year_records in by_year.items():
        for i, r1 in enumerate(year_records):
            for r2 in year_records[i+1:]:
                if r1["ticker"] == r2["ticker"]:
                    continue
                
                # Comparar campos numéricos principales
                fields_to_compare = ["fee_income", "net_income", "equity", "contributors"]
                matches = 0
                total = 0
                
                for field in fields_to_compare:
                    v1 = r1.get(field)
                    v2 = r2.get(field)
                    if v1 is not None and v2 is not None:
                        total += 1
                        if v1 == v2:
                            matches += 1
                
                # Si más del 75% de los campos coinciden, es sospechoso
                if total > 0 and matches / total >= 0.75:
                    issues.append({
                        "type": "DUPLICATE_DATA",
                        "severity": "CRITICAL",
                        "year": year,
                        "ticker1": r1["ticker"],
                        "ticker2": r2["ticker"],
                        "match_pct": round(matches / total * 100, 1),
                        "message": f"Posible duplicación: {r1['ticker']} y {r2['ticker']} tienen {matches}/{total} campos idénticos en {year}",
                        "details": {
                            "fee_income": f"{r1.get('fee_income')} vs {r2.get('fee_income')}",
                            "net_income": f"{r1.get('net_income')} vs {r2.get('net_income')}",
                            "equity": f"{r1.get('equity')} vs {r2.get('equity')}",
                            "contributors": f"{r1.get('contributors')} vs {r2.get('contributors')}",
                        }
                    })
    
    return {"duplicate_detection": issues}


def validate_accounting_identity(records: list[dict]) -> dict:
    """
    Valida la identidad contable: Assets = Liabilities + Equity.
    """
    issues = []
    
    for r in records:
        assets = r.get("assets")
        liabilities = r.get("liabilities")
        equity = r.get("equity")
        
        if assets is not None and liabilities is not None and equity is not None:
            expected_equity = assets - liabilities
            diff = abs(equity - expected_equity)
            diff_pct = diff / assets if assets != 0 else 0
            
            # Permitir hasta 5% de diferencia (redondeos)
            if diff_pct > 0.05:
                issues.append({
                    "type": "ACCOUNTING_IDENTITY",
                    "severity": "WARNING",
                    "ticker": r["ticker"],
                    "year": r["year"],
                    "message": f"Identidad contable no cuadra: Assets={assets:,.0f}, Liabilities={liabilities:,.0f}, Equity={equity:,.0f}",
                    "diff_pct": round(diff_pct * 100, 2),
                })
    
    return {"accounting_identity": issues}


def validate_reasonable_ranges(records: list[dict]) -> dict:
    """
    Valida que los valores estén dentro de rangos esperados.
    """
    issues = []
    
    for r in records:
        ticker = r["ticker"]
        year = r["year"]
        
        # Validar rangos absolutos
        for field, (min_val, max_val) in EXPECTED_RANGES.items():
            value = r.get(field)
            if value is not None:
                if not (min_val <= value <= max_val):
                    issues.append({
                        "type": "OUT_OF_RANGE",
                        "severity": "WARNING",
                        "ticker": ticker,
                        "year": year,
                        "field": field,
                        "value": value,
                        "expected_range": (min_val, max_val),
                        "message": f"{field}={value:,.0f} fuera de rango esperado [{min_val:,.0f}, {max_val:,.0f}]",
                    })
        
        # Validar número de afiliados por AFP
        contributors = r.get("contributors")
        if contributors is not None and ticker in TYPICAL_CONTRIBUTORS:
            min_c, max_c = TYPICAL_CONTRIBUTORS[ticker]
            if not (min_c <= contributors <= max_c):
                issues.append({
                    "type": "CONTRIBUTORS_MISMATCH",
                    "severity": "WARNING",
                    "ticker": ticker,
                    "year": year,
                    "value": contributors,
                    "expected_range": (min_c, max_c),
                    "message": f"{ticker} tiene {contributors:,} afiliados, pero se esperaba entre {min_c:,} y {max_c:,}",
                })
        
        # Validar fee_margin
        fee_income = r.get("fee_income")
        net_income = r.get("net_income")
        if fee_income and net_income and fee_income > 0:
            fee_margin = net_income / fee_income
            min_m, max_m = EXPECTED_RANGES["fee_margin"]
            if not (min_m <= fee_margin <= max_m):
                issues.append({
                    "type": "FEE_MARGIN_ANOMALY",
                    "severity": "WARNING",
                    "ticker": ticker,
                    "year": year,
                    "value": round(fee_margin, 3),
                    "message": f"Fee margin {fee_margin:.1%} fuera de rango normal [{min_m:.0%}, {max_m:.0%}]",
                })
        
        # Validar ROE
        equity = r.get("equity")
        if net_income and equity and equity > 0:
            roe = net_income / equity
            min_r, max_r = EXPECTED_RANGES["roe"]
            if not (min_r <= roe <= max_r):
                issues.append({
                    "type": "ROE_ANOMALY",
                    "severity": "INFO",
                    "ticker": ticker,
                    "year": year,
                    "value": round(roe, 3),
                    "message": f"ROE {roe:.1%} fuera de rango típico [{min_r:.0%}, {max_r:.0%}]",
                })
    
    return {"reasonable_ranges": issues}


def validate_against_reference(records: list[dict]) -> dict:
    """
    Compara los datos extraídos con datos de referencia conocidos.
    """
    issues = []
    
    for r in records:
        ticker = r["ticker"]
        year = r["year"]
        
        if ticker not in REFERENCE_DATA:
            continue
        
        if year not in REFERENCE_DATA[ticker]:
            continue
        
        ref = REFERENCE_DATA[ticker][year]
        
        for field, expected in ref.items():
            actual = r.get(field)
            if actual is not None and expected is not None:
                diff = abs(actual - expected)
                diff_pct = diff / expected if expected != 0 else 0
                
                # Permitir hasta 5% de diferencia
                if diff_pct > 0.05:
                    issues.append({
                        "type": "REFERENCE_MISMATCH",
                        "severity": "WARNING" if diff_pct < 0.20 else "CRITICAL",
                        "ticker": ticker,
                        "year": year,
                        "field": field,
                        "actual": actual,
                        "expected": expected,
                        "diff_pct": round(diff_pct * 100, 1),
                        "message": f"{field}: extraído={actual:,.0f}, esperado={expected:,.0f} (diff: {diff_pct:.1%})",
                    })
    
    return {"reference_comparison": issues}


def validate_year_continuity(records: list[dict]) -> dict:
    """
    Valida continuidad temporal (no deberían haber saltos grandes sin explicación).
    """
    issues = []
    
    # Agrupar por ticker
    by_ticker = defaultdict(list)
    for r in records:
        by_ticker[r["ticker"]].append(r)
    
    for ticker, ticker_records in by_ticker.items():
        # Ordenar por año
        sorted_records = sorted(ticker_records, key=lambda x: x["year"])
        
        for i in range(1, len(sorted_records)):
            prev = sorted_records[i-1]
            curr = sorted_records[i]
            
            # Detectar años faltantes
            if curr["year"] - prev["year"] > 1:
                missing_years = list(range(prev["year"] + 1, curr["year"]))
                issues.append({
                    "type": "MISSING_YEARS",
                    "severity": "INFO",
                    "ticker": ticker,
                    "missing_years": missing_years,
                    "message": f"{ticker}: faltan años {missing_years}",
                })
            
            # Detectar cambios bruscos en equity (>50%)
            prev_equity = prev.get("equity")
            curr_equity = curr.get("equity")
            if prev_equity and curr_equity and prev_equity > 0:
                change = (curr_equity - prev_equity) / prev_equity
                if abs(change) > 0.5:
                    issues.append({
                        "type": "LARGE_EQUITY_CHANGE",
                        "severity": "WARNING",
                        "ticker": ticker,
                        "year": curr["year"],
                        "prev_year": prev["year"],
                        "change_pct": round(change * 100, 1),
                        "message": f"{ticker}: equity cambió {change:+.1%} entre {prev['year']} y {curr['year']}",
                    })
            
            # Detectar cambios bruscos en contributors (>30%)
            prev_contrib = prev.get("contributors")
            curr_contrib = curr.get("contributors")
            if prev_contrib and curr_contrib and prev_contrib > 0:
                change = (curr_contrib - prev_contrib) / prev_contrib
                if abs(change) > 0.3:
                    issues.append({
                        "type": "LARGE_CONTRIBUTORS_CHANGE",
                        "severity": "INFO",
                        "ticker": ticker,
                        "year": curr["year"],
                        "change_pct": round(change * 100, 1),
                        "message": f"{ticker}: afiliados cambió {change:+.1%} entre {prev['year']} y {curr['year']}",
                    })
    
    return {"year_continuity": issues}


def run_validation(input_dir: str, concept_map_path: str) -> dict:
    """
    Ejecuta todas las validaciones y retorna un reporte.
    """
    print("=" * 70)
    print("AFP Data Validation Report")
    print("=" * 70)
    
    # Cargar concept map
    concept_map = load_concept_map(concept_map_path)
    print(f"\nLoaded {len(concept_map)} field mappings")
    
    # Encontrar PDFs
    pdf_files = find_pdf_files(input_dir)
    print(f"Found {len(pdf_files)} PDF files\n")
    
    # Parsear todos los PDFs
    records = []
    for pdf_info in pdf_files:
        ticker = pdf_info["ticker"]
        pdf_path = pdf_info["pdf_path"]
        
        print(f"Parsing {ticker}: {os.path.basename(pdf_path)}")
        
        raw_data = parse_pdf(pdf_path, ticker)
        if raw_data["year"]:
            record = map_fields(raw_data, concept_map)
            records.append(record)
    
    print(f"\nParsed {len(records)} records\n")
    
    # Ejecutar validaciones
    all_issues = {}
    
    print("Running validations...")
    print("-" * 40)
    
    # 1. Detección de duplicados
    print("  [1/5] Duplicate detection...")
    result = validate_duplicate_detection(records)
    all_issues.update(result)
    
    # 2. Identidad contable
    print("  [2/5] Accounting identity...")
    result = validate_accounting_identity(records)
    all_issues.update(result)
    
    # 3. Rangos razonables
    print("  [3/5] Reasonable ranges...")
    result = validate_reasonable_ranges(records)
    all_issues.update(result)
    
    # 4. Comparación con referencia
    print("  [4/5] Reference comparison...")
    result = validate_against_reference(records)
    all_issues.update(result)
    
    # 5. Continuidad temporal
    print("  [5/5] Year continuity...")
    result = validate_year_continuity(records)
    all_issues.update(result)
    
    # Imprimir reporte
    print("\n" + "=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)
    
    total_issues = 0
    critical_count = 0
    warning_count = 0
    info_count = 0
    
    for category, issues in all_issues.items():
        if not issues:
            continue
        
        total_issues += len(issues)
        
        for issue in issues:
            severity = issue.get("severity", "INFO")
            if severity == "CRITICAL":
                critical_count += 1
            elif severity == "WARNING":
                warning_count += 1
            else:
                info_count += 1
    
    print(f"\nTotal issues: {total_issues}")
    print(f"  CRITICAL: {critical_count}")
    print(f"  WARNING:  {warning_count}")
    print(f"  INFO:     {info_count}")
    
    # Mostrar issues por categoría
    for category, issues in all_issues.items():
        if not issues:
            continue
        
        print(f"\n--- {category.upper().replace('_', ' ')} ---")
        
        # Ordenar por severidad
        issues_by_severity = {"CRITICAL": [], "WARNING": [], "INFO": []}
        for issue in issues:
            sev = issue.get("severity", "INFO")
            issues_by_severity[sev].append(issue)
        
        for severity in ["CRITICAL", "WARNING", "INFO"]:
            for issue in issues_by_severity[severity]:
                print(f"  [{severity}] {issue['message']}")
    
    # Resumen de datos extraídos
    print("\n" + "=" * 70)
    print("EXTRACTED DATA SUMMARY")
    print("=" * 70)
    
    by_ticker = defaultdict(list)
    for r in records:
        by_ticker[r["ticker"]].append(r)
    
    for ticker in sorted(by_ticker.keys()):
        print(f"\n{ticker}:")
        ticker_records = sorted(by_ticker[ticker], key=lambda x: x["year"])
        for r in ticker_records:
            print(f"  {r['year']}: Fee Income={r.get('fee_income', 0):>15,.0f} | "
                  f"Net Income={r.get('net_income', 0):>15,.0f} | "
                  f"Equity={r.get('equity', 0):>15,.0f} | "
                  f"Contributors={r.get('contributors', 0):>10,.0f}")
    
    # Recomendación final
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    
    if critical_count > 0:
        print("\n⛔ CRITICAL issues found! DO NOT insert data into warehouse.")
        print("   Fix the parsing issues before proceeding.\n")
    elif warning_count > 0:
        print("\n⚠️  WARNINGs found. Review issues before inserting data.")
        print("   Data may be correct but unusual.\n")
    else:
        print("\n✅ No critical issues. Data appears valid.")
        print("   Safe to proceed with warehouse insertion.\n")
    
    return {
        "total_issues": total_issues,
        "critical": critical_count,
        "warning": warning_count,
        "info": info_count,
        "issues": all_issues,
        "records": records,
    }


def main():
    ap = argparse.ArgumentParser(description="Validate AFP PDF extraction")
    ap.add_argument("--input", default=r"C:\Users\david\Downloads\Estado Resultados", help="Directory with AFP PDF folders")
    ap.add_argument("--map", default="concept_map_afp.yaml", help="AFP concept map YAML")
    args = ap.parse_args()
    
    run_validation(args.input, args.map)


if __name__ == "__main__":
    main()