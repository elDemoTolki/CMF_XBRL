"""
afp_pipeline.py — AFP Financial Data Pipeline
==============================================

Parses FECU-IFRS PDF reports from Chilean AFPs and loads them into the warehouse.

AFP reports use a standardized format from Superintendencia de Pensiones with
numeric codes (XX.XX.XXX) for each line item.

Usage:
    python afp_pipeline.py
    python afp_pipeline.py --input "C:\\Users\\david\\Downloads\\Estado Resultados"
    python afp_pipeline.py --ticker AFPCAPITAL.SN
"""

import argparse
import json
import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
import pdfplumber
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_PDF_DIR = r"C:\Users\david\Downloads\Estado Resultados"
TICKERS_JSON = "tickers_chile.json"
CONCEPT_MAP_AFP = "concept_map_afp.yaml"
DB_PATH = os.path.join("output", "warehouse.db")
OUT_DIR = "output"

# AFP tickers in the system
AFP_TICKERS = {
    "AFPCAPITAL.SN": {"name": "AFP Capital", "folder": "Capital"},
    "HABITAT.SN": {"name": "AFP Habitat", "folder": "Habitat"},
    "PLANVITAL.SN": {"name": "AFP PlanVital", "folder": "Planvital"},
    "PROVIDA.SN": {"name": "AFP Provida", "folder": "Provida"},
}

# Mapping from folder names to tickers
FOLDER_TO_TICKER = {v["folder"]: k for k, v in AFP_TICKERS.items()}


# ── Parsers ──────────────────────────────────────────────────────────────────

def parse_number(value: str) -> Optional[float]:
    """
    Parse a number from FECU format (handles negatives in parentheses).
    
    Args:
        value: String value like "123.456.789" or "(123.456)" for negative.
        
    Returns:
        Float value or None if parsing fails.
    """
    if not value or value.strip() in ("-", "", "None"):
        return None
    
    value = value.strip()
    
    # Handle negative numbers in parentheses
    is_negative = value.startswith("(") and value.endswith(")")
    if is_negative:
        value = value[1:-1]
    
    # Remove thousand separators (dots in Chilean format)
    value = value.replace(".", "").replace(",", ".")
    
    try:
        num = float(value)
        return -num if is_negative else num
    except ValueError:
        return None


def extract_year_month_from_text(text: str) -> tuple[Optional[int], Optional[int]]:
    """
    Extract year and month from PDF text.
    
    Args:
        text: Text from PDF page.
        
    Returns:
        Tuple of (year, month). Month is typically 12 for annual reports.
    """
    # Look for patterns like "31 de diciembre de 2024" or "31/12/2024"
    year_patterns = [
        r"(\d{4})$",  # Year at end
        r"del?\s*(\d{4})",  # "de 2024" or "del 2024"
        r"diciembre\s*(?:de\s*)?(\d{4})",  # "diciembre de 2024"
    ]
    
    for pattern in year_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            year = int(match.group(1))
            # AFP reports are typically annual (December)
            return year, 12
    
    # Try to find any 4-digit year
    years = re.findall(r"\b(20\d{2})\b", text)
    if years:
        # Return the most recent year found
        return int(max(years)), 12
    
    return None, None


def parse_table_name(text: str) -> str:
    """
    Determine which FECU table this page belongs to.
    
    Args:
        text: Text from PDF page.
        
    Returns:
        Table name: 'balance', 'resultados', 'flujo_efectivo', or 'complementarios'.
    """
    text_lower = text.lower()
    
    if "estado de situación financiera" in text_lower or "activos" in text_lower and "pasivos" in text_lower:
        if "pasivos y patrimonio" in text_lower or "2.01" in text:
            return "balance"
    if "estado de resultados" in text_lower:
        return "resultados"
    if "flujo de efectivo" in text_lower or "2.04" in text:
        return "flujo_efectivo"
    if "estados complementarios" in text_lower or "2.05" in text:
        return "complementarios"
    
    return "unknown"


def parse_fecu_table(page, table_index: int = 0) -> list[dict]:
    """
    Parse a FECU table from a PDF page.
    
    Handles two common table structures:
    - ACTIVOS: [code, description, note, value_current, value_prev, ...]
    - PASIVOS/PATRIMONIO: [code, '', description, note, value_current, value_prev, ...]
    
    Args:
        page: pdfplumber page object.
        table_index: Which table to parse (default 0 = first table).
        
    Returns:
        List of dicts with code, description, value_current, value_prev.
    """
    tables = page.extract_tables()
    if not tables or table_index >= len(tables):
        return []
    
    table = tables[table_index]
    rows = []
    
    for row in table:
        if not row or len(row) < 3:
            continue
        
        code = str(row[0]).strip() if row[0] else ""
        
        # Skip header rows or empty codes
        if not code or code in ("", "ACTIVOS", "PASIVOS", "PATRIMONIO", "N° de", "Nota"):
            continue
        
        # Validate code format (XX.XX.XXX)
        if not re.match(r"\d{2}\.\d{2}\.\d{3}", code):
            # Could be a sub-code (XX.XX.XXX.XXX)
            if not re.match(r"\d{2}\.\d{2}\.\d{3}(\.\d{3})*", code):
                continue
        
        # Detect table structure based on second column
        # ACTIVOS: [code, description, note, value, ...]
        # PASIVOS/PATRIMONIO: [code, '', description, note, value, ...]
        
        second_col = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        
        if second_col == "":
            # PASIVOS/PATRIMONIO structure: second column is empty
            # Row: [code, '', description, note, value_current, value_prev, ...]
            description = str(row[2]).strip() if len(row) > 2 and row[2] else ""
            value_start_idx = 4  # Skip code, empty, description, note
        else:
            # ACTIVOS structure: second column is description
            # Row: [code, description, note, value_current, value_prev, ...]
            description = second_col
            value_start_idx = 3  # Skip code, description, note
        
        # Find value columns (look for numeric values)
        values = []
        for cell in row[value_start_idx:]:
            val = parse_number(str(cell)) if cell else None
            values.append(val)
        
        # Usually: [value_current, value_prev] or [value_current, value_prev, value_start]
        value_current = values[0] if len(values) > 0 else None
        value_prev = values[1] if len(values) > 1 else None
        
        rows.append({
            "code": code,
            "description": description,
            "value_current": value_current,
            "value_prev": value_prev,
        })
    
    return rows


def parse_pdf(pdf_path: str, ticker: str) -> dict:
    """
    Parse a complete AFP PDF file.
    
    Args:
        pdf_path: Path to PDF file.
        ticker: Ticker symbol.
        
    Returns:
        Dict with year, month, and extracted fields.
    """
    logger.info(f"Parsing {pdf_path} for {ticker}")
    
    # Extract year from filename first (more reliable)
    # Patterns in AFP filenames:
    # - _31122024.pdf (DDMMYYYY at end)
    # - _2024.pdf (year only)
    # - al_31-12-2022.pdf (DD-MM-YYYY)
    filename = os.path.basename(pdf_path)
    
    # Try DD-MM-YYYY pattern first (e.g., 31-12-2022)
    year_match = re.search(r"(\d{2})-(\d{2})-(\d{4})", filename)
    if year_match:
        filename_year = int(year_match.group(3))
    else:
        # Try DDMMYYYY pattern at end of filename (e.g., _31122024.pdf or _31122024R.pdf)
        # Match: 8 digits followed by optional R and .pdf
        year_match = re.search(r"(\d{2})(\d{2})(\d{4})(?:R)?(?:\.pdf)$", filename, re.IGNORECASE)
        if year_match:
            filename_year = int(year_match.group(3))
        else:
            # Fallback: find any 4-digit year starting with 20
            year_match = re.search(r"(20\d{2})", filename)
            filename_year = int(year_match.group(1)) if year_match else None
    
    all_data = {
        "ticker": ticker,
        "year": filename_year,
        "month": 12,  # Default to December
        "reporting_currency": "CLP",
        "fields": {},
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # First pass: find year/month from first pages
            for page in pdf.pages[:5]:
                text = page.extract_text() or ""
                year, month = extract_year_month_from_text(text)
                if year and not all_data["year"]:
                    all_data["year"] = year
                if month:
                    all_data["month"] = month
            
            # Second pass: extract all FECU tables (limit pages to avoid hanging)
            max_pages = min(len(pdf.pages), 30)  # Limit to first 30 pages
            for page in pdf.pages[:max_pages]:
                text = page.extract_text() or ""
                table_name = parse_table_name(text)
                
                if table_name == "unknown":
                    continue
                
                # Parse the main table on this page
                try:
                    rows = parse_fecu_table(page)
                except Exception as e:
                    logger.warning(f"Error parsing table on page: {e}")
                    continue
                
                for row in rows:
                    code = row["code"]
                    # Store with table context
                    all_data["fields"][code] = {
                        "value": row["value_current"],
                        "value_prev": row["value_prev"],
                        "description": row["description"],
                        "table": table_name,
                    }
    
    except Exception as e:
        logger.error(f"Error parsing {pdf_path}: {e}")
    
    return all_data


# ── Concept Map Loader ────────────────────────────────────────────────────────

def load_concept_map(path: str) -> dict:
    """
    Load AFP concept mapping from YAML file.
    
    Args:
        path: Path to concept_map_afp.yaml.
        
    Returns:
        Dictionary with field mappings.
    """
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["fields"]


# ── Data Processing ──────────────────────────────────────────────────────────

def map_fields(raw_data: dict, concept_map: dict) -> dict:
    """
    Map raw FECU codes to warehouse fields.
    
    Args:
        raw_data: Dict from parse_pdf with 'fields' key.
        concept_map: Dict from load_concept_map.
        
    Returns:
        Dict with mapped fields ready for warehouse.
    """
    result = {
        "ticker": raw_data["ticker"],
        "year": raw_data["year"],
        "month": raw_data["month"],
        "reporting_currency": raw_data["reporting_currency"],
        "industry": "financial",  # AFPs are financial institutions
    }
    
    fields = raw_data.get("fields", {})
    
    for field_name, spec in concept_map.items():
        code = spec.get("code", "")
        table = spec.get("table", "")
        negate = spec.get("negate", False)
        alternate_code = spec.get("alternate_code", "")
        
        # Try primary code
        value = None
        if code in fields:
            value = fields[code].get("value")
        
        # Try alternate code if primary not found
        if value is None and alternate_code and alternate_code in fields:
            value = fields[alternate_code].get("value")
        
        # Apply negate if needed
        if value is not None and negate:
            value = -value
        
        result[field_name] = value
    
    return result


def calculate_derived_metrics(record: dict) -> dict:
    """
    Calculate AFP-specific derived metrics.
    
    Args:
        record: Dict with mapped fields.
        
    Returns:
        Dict with derived metrics added.
    """
    derived = {
        "ticker": record["ticker"],
        "year": record["year"],
        "month": record["month"],
        "industry": record["industry"],
    }
    
    # Operating expenses = employee_benefits + other_operating_expenses
    emp_benefits = record.get("employee_benefits")
    other_opex = record.get("other_operating_expenses")
    
    if emp_benefits is not None or other_opex is not None:
        derived["operating_expenses"] = (emp_benefits or 0) + (other_opex or 0)
        derived["operating_expenses_source"] = "employee_benefits_plus_other"
    else:
        derived["operating_expenses"] = None
        derived["operating_expenses_source"] = "missing"
    
    # Fee margin = net_income / fee_income
    net_income = record.get("net_income")
    fee_income = record.get("fee_income")
    
    if fee_income and fee_income != 0 and net_income is not None:
        derived["fee_margin"] = net_income / fee_income
        derived["fee_margin_source"] = "calculated"
    else:
        derived["fee_margin"] = None
        derived["fee_margin_source"] = "missing_fee_income" if not fee_income else "missing_net_income"
    
    # Cost to income = operating_expenses / fee_income
    operating_exp = derived.get("operating_expenses")
    
    if fee_income and fee_income != 0 and operating_exp is not None:
        derived["cost_to_income"] = operating_exp / fee_income
        derived["cost_to_income_source"] = "calculated"
    else:
        derived["cost_to_income"] = None
        derived["cost_to_income_source"] = "missing"
    
    # ROE = net_income / equity
    equity = record.get("equity")
    
    if equity and equity != 0 and net_income is not None:
        derived["roe"] = net_income / equity
        derived["roe_source"] = "calculated"
    else:
        derived["roe"] = None
        derived["roe_source"] = "missing"
    
    return derived


def calculate_quality_flags(record: dict) -> dict:
    """
    Calculate quality flags for AFP data.
    
    Args:
        record: Dict with mapped fields.
        
    Returns:
        Dict with quality flags.
    """
    flags = {
        "ticker": record["ticker"],
        "year": record["year"],
        "month": record["month"],
        "industry": record["industry"],
    }
    
    # Fee income quality
    fee_income = record.get("fee_income")
    flags["fee_income_quality"] = "high" if fee_income is not None else "missing"
    
    # Operating expenses quality
    emp = record.get("employee_benefits")
    other = record.get("other_operating_expenses")
    if emp is not None and other is not None:
        flags["operating_expenses_quality"] = "full"
    elif emp is not None or other is not None:
        flags["operating_expenses_quality"] = "partial"
    else:
        flags["operating_expenses_quality"] = "missing"
    
    # Data completeness
    critical_fields = ["assets", "equity", "net_income", "fee_income", "cash"]
    present = sum(1 for f in critical_fields if record.get(f) is not None)
    flags["data_completeness_pct"] = round(present / len(critical_fields) * 100, 1)
    
    # Contributors quality
    contributors = record.get("contributors")
    flags["contributors_quality"] = "available" if contributors is not None else "missing"
    
    return flags


# ── File Discovery ────────────────────────────────────────────────────────────

def find_pdf_files(input_dir: str, ticker_filter: str = None) -> list[dict]:
    """
    Find all AFP PDF files in the input directory.
    
    Args:
        input_dir: Root directory with AFP subfolders.
        ticker_filter: Optional ticker to filter (e.g., "AFPCAPITAL.SN").
        
    Returns:
        List of dicts with ticker, pdf_path, folder.
    """
    pdf_files = []
    
    for folder_name, ticker in FOLDER_TO_TICKER.items():
        if ticker_filter and ticker != ticker_filter:
            continue
        
        folder_path = os.path.join(input_dir, folder_name)
        
        if not os.path.isdir(folder_path):
            logger.warning(f"Folder not found: {folder_path}")
            continue
        
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".pdf"):
                pdf_files.append({
                    "ticker": ticker,
                    "pdf_path": os.path.join(folder_path, filename),
                    "folder": folder_name,
                })
    
    return pdf_files


# ── Database Operations ────────────────────────────────────────────────────────

def get_existing_records(db_path: str, ticker: str) -> set:
    """
    Get existing (year, month) records for a ticker.
    
    Args:
        db_path: Path to SQLite database.
        ticker: Ticker symbol.
        
    Returns:
        Set of (year, month) tuples.
    """
    if not os.path.exists(db_path):
        return set()
    
    con = sqlite3.connect(db_path)
    try:
        cursor = con.execute(
            "SELECT year, month FROM normalized_financials WHERE ticker = ?",
            (ticker,)
        )
        return {(row[0], row[1]) for row in cursor.fetchall()}
    finally:
        con.close()


def upsert_record(db_path: str, record: dict, derived: dict, flags: dict) -> None:
    """
    Insert or update a record in the warehouse.
    
    Args:
        db_path: Path to SQLite database.
        record: Normalized financial record.
        derived: Derived metrics record.
        flags: Quality flags record.
    """
    con = sqlite3.connect(db_path)
    try:
        # Delete existing record if present
        con.execute(
            "DELETE FROM normalized_financials WHERE ticker = ? AND year = ? AND month = ?",
            (record["ticker"], record["year"], record["month"])
        )
        con.execute(
            "DELETE FROM derived_metrics WHERE ticker = ? AND year = ? AND month = ?",
            (record["ticker"], record["year"], record["month"])
        )
        con.execute(
            "DELETE FROM quality_flags WHERE ticker = ? AND year = ? AND month = ?",
            (record["ticker"], record["year"], record["month"])
        )
        
        # Insert normalized_financials
        columns = [k for k, v in record.items() if v is not None]
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO normalized_financials ({', '.join(columns)}) VALUES ({placeholders})"
        con.execute(sql, [record[c] for c in columns])
        
        # Insert derived_metrics
        columns = [k for k, v in derived.items() if v is not None]
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO derived_metrics ({', '.join(columns)}) VALUES ({placeholders})"
        con.execute(sql, [derived[c] for c in columns])
        
        # Insert quality_flags
        columns = [k for k, v in flags.items() if v is not None]
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO quality_flags ({', '.join(columns)}) VALUES ({placeholders})"
        con.execute(sql, [flags[c] for c in columns])
        
        con.commit()
        logger.info(f"  Upserted {record['ticker']} {record['year']}/{record['month']}")
        
    finally:
        con.close()


def ensure_afp_columns(db_path: str, record: dict, derived: dict) -> None:
    """
    Ensure database has columns for AFP-specific fields.
    
    Args:
        db_path: Path to SQLite database.
        record: Sample normalized record.
        derived: Sample derived metrics record.
    """
    con = sqlite3.connect(db_path)
    try:
        # Get existing columns
        cursor = con.execute("PRAGMA table_info(normalized_financials)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        
        # Add AFP-specific columns if missing
        afp_columns = [
            ("fee_income", "REAL"),
            ("encaje", "REAL"),
            ("encaje_return", "REAL"),
            ("contributors", "INTEGER"),
            ("regulated_equity", "REAL"),
            ("regulated_equity_uf", "REAL"),
            ("minimum_capital_uf", "REAL"),
        ]
        
        for col_name, col_type in afp_columns:
            if col_name not in existing_cols:
                con.execute(f"ALTER TABLE normalized_financials ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column {col_name} to normalized_financials")
        
        con.commit()
        
    except sqlite3.OperationalError as e:
        # Table might not exist yet - pipeline.py will create it
        logger.info(f"Database not initialized yet: {e}")
        
    finally:
        con.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Parse AFP PDF reports into warehouse")
    ap.add_argument("--input", default=DEFAULT_PDF_DIR, help="Directory with AFP PDF folders")
    ap.add_argument("--db", default=DB_PATH, help="SQLite warehouse path")
    ap.add_argument("--map", default=CONCEPT_MAP_AFP, help="AFP concept map YAML")
    ap.add_argument("--ticker", default=None, help="Process only this ticker")
    ap.add_argument("--dry-run", action="store_true", help="Parse but don't save to DB")
    ap.add_argument("--debug", action="store_true", help="Show all extracted FECU codes")
    args = ap.parse_args()
    
    logger.info(f"Loading concept map: {args.map}")
    concept_map = load_concept_map(args.map)
    print(f"  {len(concept_map)} field mappings loaded")
    
    logger.info(f"Finding PDF files in: {args.input}")
    pdf_files = find_pdf_files(args.input, args.ticker)
    print(f"  Found {len(pdf_files)} PDF files")
    
    if not pdf_files:
        print("No PDF files found. Exiting.")
        return
    
    if not args.dry_run:
        os.makedirs(os.path.dirname(args.db), exist_ok=True)
    
    results = []
    
    for pdf_info in pdf_files:
        ticker = pdf_info["ticker"]
        pdf_path = pdf_info["pdf_path"]
        
        print(f"\nProcessing {ticker}: {os.path.basename(pdf_path)}")
        
        # Parse PDF
        raw_data = parse_pdf(pdf_path, ticker)
        
        if not raw_data["year"]:
            logger.warning(f"Could not determine year for {pdf_path}")
            continue
        
        # Map fields
        record = map_fields(raw_data, concept_map)
        
        # Calculate derived metrics
        derived = calculate_derived_metrics(record)
        
        # Calculate quality flags
        flags = calculate_quality_flags(record)
        
        results.append({
            "raw": raw_data,
            "record": record,
            "derived": derived,
            "flags": flags,
        })
        
        if args.dry_run:
            print(f"  [DRY-RUN] Year: {record['year']}, Fields: {sum(1 for v in record.values() if v is not None and not isinstance(v, str))}")
            print(f"    Fee income: {record.get('fee_income'):,.0f}" if record.get('fee_income') else "    Fee income: N/A")
            print(f"    Net income: {record.get('net_income'):,.0f}" if record.get('net_income') else "    Net income: N/A")
            print(f"    Equity: {record.get('equity'):,.0f}" if record.get('equity') else "    Equity: N/A")
            print(f"    Contributors: {record.get('contributors'):,}" if record.get('contributors') else "    Contributors: N/A")
            
            # Debug: show all extracted FECU codes
            if args.debug:
                print(f"\n  [DEBUG] Extracted FECU codes ({len(raw_data['fields'])} total):")
                for code, data in sorted(raw_data['fields'].items()):
                    desc = data.get('description', '')[:40]
                    val = data.get('value')
                    table = data.get('table', '')
                    val_str = f"{val:,.0f}" if val else "N/A"
                    print(f"    {code}: {val_str} | {desc} | [{table}]")
        
        else:
            # Ensure columns exist
            ensure_afp_columns(args.db, record, derived)
            
            # Upsert to database
            upsert_record(args.db, record, derived, flags)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"AFP Pipeline Summary")
    print(f"{'='*60}")
    print(f"PDFs processed: {len(results)}")
    print(f"Tickers: {sorted(set(r['record']['ticker'] for r in results))}")
    
    by_ticker = {}
    for r in results:
        t = r['record']['ticker']
        by_ticker[t] = by_ticker.get(t, 0) + 1
    
    print(f"\nRecords per ticker:")
    for ticker, count in sorted(by_ticker.items()):
        print(f"  {ticker}: {count} records")
    
    if args.dry_run:
        print("\n[DRY-RUN] No data saved to database")
    else:
        print(f"\nData saved to: {args.db}")


if __name__ == "__main__":
    main()