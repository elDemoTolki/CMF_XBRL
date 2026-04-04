"""
cmf_api.py — Fetches bank financial data from CMF SBIF API v3
=============================================================
Popula normalized_financials para bancos que NO publican XBRL en CMF.

Bancos cubiertos (solo los que faltan en el warehouse):
  BCI.SN        (codigo CMF: 016)
  BSANTANDER.SN (codigo CMF: 037)
  ITAUCL.SN     (codigo CMF: 039)

Nota: AFPs (PLANVITAL, AFPCAPITAL, HABITAT, PROVIDA) no estan en la
      API bancaria de la CMF. Requieren fuente separada.

Uso:
  python cmf_api.py
  python cmf_api.py --years 2020,2021,2022,2023,2024
  python cmf_api.py --ticker BCI.SN
  python cmf_api.py --all-banks    # incluye CHILE.SN y BICE.SN (ya en XBRL)
"""

import argparse
import os
import sqlite3
import time
from typing import Optional

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

API_KEY  = os.getenv("CMF_API_KEY", "")
BASE_URL = "https://api.cmfchile.cl/api-sbifv3/recursos_api"
DB_PATH  = os.path.join("output", "warehouse.db")
YEARS    = list(range(2010, 2026))
MONTH    = 12          # diciembre = cierre anual
SLEEP_S  = 0.4        # pausa entre requests para no saturar la API

# Bank ticker → CMF institution code (solo los que faltan en XBRL)
BANK_CODES = {
    "BCI.SN":        "016",
    "BSANTANDER.SN": "037",
    "ITAUCL.SN":     "039",
}

# Incluye también los que YA están en XBRL (para enriquecer deposits/loans)
ALL_BANK_CODES = {
    "CHILE.SN":      "001",
    "BICE.SN":       "028",
    **BANK_CODES,
}

# ── Account mappings ──────────────────────────────────────────────────────────

# Balance sheet: cuenta CMF → columna warehouse
BALANCE_MAP: dict[str, str] = {
    "100000000": "assets",
    "200000000": "liabilities",
    "300000000": "equity",
    "380000000": "equity_parent",
    "105000000": "cash",
    "160000000": "intangibles",
    "170000000": "ppe",
    "144000000": "loans_to_customers",
    "310000000": "issued_capital",
    "340000000": "retained_earnings",
}
# Depósitos (vista + plazo) → suma a deposits_from_customers
DEPOSIT_CODES = {"241000000", "242000000"}

# Income statement: cuenta CMF → columna warehouse
INCOME_MAP: dict[str, str] = {
    "550000000": "revenue",             # Total ingresos operacionales
    "590000000": "net_income",          # Utilidad del ejercicio
    "594000000": "net_income_parent",   # Resultado propietarios
    "580000000": "ebit",                # Resultado operacional
    "570000000": "operating_income",    # Res. op. antes de pérdidas crediticias
    "585000000": "profit_before_tax",
    "480000000": "income_tax",
    "462000000": "employee_benefits",
    "466000000": "depreciation_amortization",
    "411000000": "finance_income",      # Ingresos por intereses (gross)
    "412000000": "finance_costs",       # Gastos por intereses
}
# These come in as negative from the API — store as positive in warehouse
# (matching XBRL convention where income_tax, costs are stored as their
# absolute value, sign applied by the callers)
NEGATE_INCOME = {"income_tax", "employee_benefits", "depreciation_amortization",
                 "finance_costs"}


# ── API helpers ───────────────────────────────────────────────────────────────

def _get(url: str, retries: int = 3) -> Optional[dict]:
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                text = r.text
                if "DOCTYPE" in text[:200]:
                    return None   # error page
                return r.json()
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"    ERROR: {e}")
                return None


def _parse_val(s: str) -> float:
    """Parses CMF number format '1234567,89' → float."""
    return float(s.replace(",", ".").replace(" ", ""))


def fetch_balance(code: str, year: int, month: int) -> dict:
    """Returns {warehouse_col: value} from CMF balance sheet."""
    url = (f"{BASE_URL}/balances/{year}/{month:02d}/instituciones/{code}"
           f"?apikey={API_KEY}&formato=json")
    data = _get(url)
    if not data:
        return {}

    accounts = data.get("CodigosBalances", [])
    result: dict[str, float] = {}
    deposits = 0.0
    has_deposits = False

    for a in accounts:
        cta = a.get("CodigoCuenta", "")
        raw = a.get("MonedaTotal", "0,00")
        try:
            val = _parse_val(raw)
        except ValueError:
            continue

        if cta in BALANCE_MAP:
            result[BALANCE_MAP[cta]] = val

        if cta in DEPOSIT_CODES:
            deposits += val
            has_deposits = True

    if has_deposits:
        result["deposits_from_customers"] = deposits

    # minority_interest = equity - equity_parent (if both available)
    eq  = result.get("equity")
    eqp = result.get("equity_parent")
    if eq is not None and eqp is not None:
        result["minority_interest"] = eq - eqp

    return result


def fetch_income(code: str, year: int, month: int) -> dict:
    """Returns {warehouse_col: value} from CMF income statement."""
    url = (f"{BASE_URL}/resultados/{year}/{month:02d}/instituciones/{code}"
           f"?apikey={API_KEY}&formato=json")
    data = _get(url)
    if not data:
        return {}

    accounts = data.get("CodigosEstadosDeResultado", [])
    result: dict[str, float] = {}

    for a in accounts:
        cta = a.get("CodigoCuenta", "")
        raw = a.get("MonedaTotal", "0,00")
        if cta not in INCOME_MAP:
            continue
        try:
            val = _parse_val(raw)
        except ValueError:
            continue

        col = INCOME_MAP[cta]
        # Store positive absolute values for cost/tax fields
        if col in NEGATE_INCOME:
            val = abs(val)
        result[col] = val

    return result


# ── Row builder ───────────────────────────────────────────────────────────────

def build_row(ticker: str, code: str, year: int) -> Optional[dict]:
    """Fetches balance + income for one (ticker, year) and returns a merged row."""
    bal = fetch_balance(code, year, MONTH)
    time.sleep(SLEEP_S)
    inc = fetch_income(code, year, MONTH)
    time.sleep(SLEEP_S)

    if not bal and not inc:
        return None

    row: dict = {
        "ticker":             ticker,
        "year":               year,
        "month":              MONTH,
        "industry":           "financial",
        "reporting_currency": "CLP",
    }
    row.update(bal)
    row.update(inc)

    # Fields not applicable to banks → explicit None
    for col in ("debt_short_term", "debt_long_term", "borrowings",
                "cost_of_sales", "gross_profit", "distribution_costs",
                "administrative_expense", "other_income", "other_expense",
                "cfo", "capex", "investing_cf", "dividends_paid",
                "proceeds_from_borrowings", "repayment_of_borrowings",
                "financing_cf", "net_change_cash",
                "trade_receivables", "inventories", "goodwill",
                "current_assets", "non_current_assets",
                "current_liabilities", "non_current_liabilities",
                "trade_payables", "eps_basic", "eps_diluted",
                "shares_outstanding"):
        row.setdefault(col, None)

    return row


# ── Warehouse upsert ──────────────────────────────────────────────────────────

def upsert_rows(rows: list[dict], db_path: str) -> None:
    """Inserts or replaces rows in normalized_financials."""
    if not rows:
        return
    df_new = pd.DataFrame(rows)

    con = sqlite3.connect(db_path)
    existing = pd.read_sql(
        "SELECT ticker, year, month FROM normalized_financials", con
    )
    con.close()

    # Identify truly new vs updates
    existing_keys = set(zip(existing["ticker"], existing["year"], existing["month"]))
    new_keys  = [(r["ticker"], r["year"], r["month"]) for r in rows]
    n_update  = sum(1 for k in new_keys if k in existing_keys)
    n_insert  = len(new_keys) - n_update

    con = sqlite3.connect(db_path)
    df_new.to_sql("normalized_financials", con,
                  if_exists="append", index=False,
                  method=_upsert_method)
    con.close()

    print(f"    Upserted {len(rows)} rows ({n_insert} new, {n_update} updated)")


def _upsert_method(table, conn, keys, data_iter):
    """Custom insert method: DELETE+INSERT for upsert semantics."""
    for row in data_iter:
        row_dict = dict(zip(keys, row))
        conn.execute(
            "DELETE FROM normalized_financials WHERE ticker=? AND year=? AND month=?",
            (row_dict["ticker"], row_dict["year"], row_dict["month"])
        )
        cols = ", ".join(row_dict.keys())
        placeholders = ", ".join("?" * len(row_dict))
        conn.execute(
            f"INSERT INTO normalized_financials ({cols}) VALUES ({placeholders})",
            list(row_dict.values())
        )


# ── Derived metrics / quality flags refresh ───────────────────────────────────

def refresh_derived(tickers: list[str], db_path: str) -> None:
    """Re-runs pipeline's derive_metrics and quality_flags for affected tickers."""
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("pipeline",
                                                   os.path.join(os.path.dirname(__file__), "pipeline.py"))
    pipeline = importlib.util.load_from_spec(spec)
    spec.loader.exec_module(pipeline)

    con = sqlite3.connect(db_path)
    placeholders = ",".join("?" * len(tickers))
    norm = pd.read_sql(
        f"SELECT * FROM normalized_financials WHERE ticker IN ({placeholders})",
        con, params=tickers
    )
    con.close()

    derived = pipeline.derive_metrics(norm)
    flags   = pipeline.quality_flags(norm)

    con = sqlite3.connect(db_path)
    # Delete old rows for these tickers then re-insert
    for tbl, df in [("derived_metrics", derived), ("quality_flags", flags)]:
        phs = ",".join("?" * len(tickers))
        con.execute(f"DELETE FROM {tbl} WHERE ticker IN ({phs})", tickers)
        df.to_sql(tbl, con, if_exists="append", index=False)
    con.commit()
    con.close()
    print(f"  Derived metrics + quality flags refreshed for {tickers}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="CMF API → Bank data → warehouse.db")
    ap.add_argument("--ticker",    default=None,
                    help="Solo un ticker: BCI.SN (default: todos los faltantes)")
    ap.add_argument("--years",     default=",".join(str(y) for y in YEARS),
                    help="Anos separados por coma")
    ap.add_argument("--all-banks", action="store_true",
                    help="Incluye CHILE.SN y BICE.SN (ya en XBRL)")
    ap.add_argument("--db",        default=DB_PATH)
    ap.add_argument("--no-refresh", action="store_true",
                    help="No refrescar derived_metrics / quality_flags")
    args = ap.parse_args()

    if not API_KEY:
        print("ERROR: CMF_API_KEY no encontrado en .env")
        return

    bank_map = ALL_BANK_CODES if args.all_banks else BANK_CODES
    if args.ticker:
        t = args.ticker.strip()
        if t not in bank_map:
            print(f"ERROR: {t} no encontrado. Disponibles: {list(bank_map.keys())}")
            return
        bank_map = {t: bank_map[t]}

    years = [int(y) for y in args.years.split(",")]

    print(f"CMF API fetch: {list(bank_map.keys())} | anos {years[0]}-{years[-1]}")
    print(f"Total requests: {len(bank_map) * len(years) * 2} (balance + resultados)")
    print()

    all_rows: list[dict] = []

    for ticker, code in bank_map.items():
        print(f"  {ticker} (codigo {code})")
        ticker_rows = []
        for year in years:
            print(f"    {year} ... ", end="", flush=True)
            row = build_row(ticker, code, year)
            if row:
                ticker_rows.append(row)
                assets_b = (row.get("assets") or 0) / 1e9
                rev_b    = (row.get("revenue") or 0) / 1e9
                ni_b     = (row.get("net_income") or 0) / 1e9
                print(f"OK  assets={assets_b:.0f}B  revenue={rev_b:.0f}B  net_income={ni_b:.0f}B")
            else:
                print("sin datos")
        print(f"    -> {len(ticker_rows)} anos con datos")
        all_rows.extend(ticker_rows)

    if not all_rows:
        print("No se obtuvieron datos.")
        return

    print(f"\nGuardando {len(all_rows)} filas en {args.db} ...")
    upsert_rows(all_rows, args.db)

    if not args.no_refresh:
        tickers_fetched = list({r["ticker"] for r in all_rows})
        print("\nRefrescando derived_metrics y quality_flags ...")
        refresh_derived(tickers_fetched, args.db)

    # Summary
    con = sqlite3.connect(args.db)
    tickers_fetched = list({r["ticker"] for r in all_rows})
    phs = ",".join("?" * len(tickers_fetched))
    summary = pd.read_sql(
        f"SELECT ticker, COUNT(*) as years, MIN(year) as desde, MAX(year) as hasta, "
        f"AVG(CASE WHEN assets IS NOT NULL THEN 1.0 ELSE 0 END)*100 as assets_pct, "
        f"AVG(CASE WHEN revenue IS NOT NULL THEN 1.0 ELSE 0 END)*100 as revenue_pct "
        f"FROM normalized_financials WHERE ticker IN ({phs}) GROUP BY ticker",
        con, params=tickers_fetched
    )
    con.close()
    print(f"\n{'='*65}")
    print("RESUMEN")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
