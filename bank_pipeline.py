"""
bank_pipeline.py — Pipeline para datos financieros bancarios via CMF API
=========================================================================
Obtiene estados financieros de bancos desde la API SBIF v3 de la CMF y
los integra al warehouse (misma tabla normalized_financials).

Diferencias vs pipeline.py (XBRL no-financiero):
  - Fuente: API REST CMF (no XBRL)
  - Campos propios: interest_income/expense, net_interest_income,
    financial_assets, credit_loss_expense, net_fee_income
  - Derivados: NIM, cost_to_income, credit_loss_ratio, loan_to_deposit
  - Excluye: EBITDA, CAPEX, FCF, debt_total, net_debt, ratios de deuda

Bancos cubiertos (los que NO publican XBRL):
  BCI.SN        → CMF codigo 016
  BSANTANDER.SN → CMF codigo 037
  ITAUCL.SN     → CMF codigo 039

Uso:
  python bank_pipeline.py
  python bank_pipeline.py --years 2020,2021,2022,2023,2024
  python bank_pipeline.py --ticker BCI.SN
  python bank_pipeline.py --all-banks   # incluye CHILE.SN y BICE.SN
"""

import argparse
import os
import sqlite3
import time
from typing import Optional

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

API_KEY       = os.getenv("CMF_API_KEY", "")
BASE_URL      = "https://api.cmfchile.cl/api-sbifv3/recursos_api"
DB_PATH       = os.path.join("output", "warehouse.db")
CONCEPT_MAP   = "concept_map_banks.yaml"
YEARS         = list(range(2010, 2026))
MONTH         = 12      # diciembre = cierre anual
SLEEP_S       = 0.4     # pausa entre requests

# Tickers faltantes en XBRL → solo estos por default
BANK_CODES: dict[str, str] = {
    "BCI.SN":        "016",
    "BSANTANDER.SN": "037",
    "ITAUCL.SN":     "039",
}

# Todos los bancos (incluye los que ya tienen XBRL)
ALL_BANK_CODES: dict[str, str] = {
    "CHILE.SN":      "001",
    "BICE.SN":       "028",
    **BANK_CODES,
}

# Columnas bank-specific que deben existir en normalized_financials
BANK_EXTRA_COLS = [
    "net_interest_income",
    "financial_assets",
    "credit_loss_expense",
    "net_fee_income",
    "interest_income",
    "interest_expense",
]


# ── Schema migration ──────────────────────────────────────────────────────────

DERIVED_EXTRA_COLS = [
    "nim", "nim_source",
    "cost_to_income", "cost_to_income_source",
    "credit_loss_ratio", "credit_loss_ratio_source",
    "loan_to_deposit", "loan_to_deposit_source",
]

QUALITY_EXTRA_COLS = [
    "bank_data_quality",
    "interest_data_completeness",
]


def ensure_bank_columns(db_path: str) -> None:
    """Agrega columnas bank-specific a las tablas del warehouse si no existen."""
    con = sqlite3.connect(db_path)

    schema = {
        "normalized_financials": BANK_EXTRA_COLS,
        "derived_metrics":       DERIVED_EXTRA_COLS,
        "quality_flags":         QUALITY_EXTRA_COLS,
    }
    for table, cols in schema.items():
        existing = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
        for col in cols:
            if col not in existing:
                # Source columns are TEXT, numeric columns are REAL
                col_type = "TEXT" if col.endswith("_source") else "REAL"
                if col in ("bank_data_quality", "interest_data_completeness"):
                    col_type = "TEXT" if col == "bank_data_quality" else "REAL"
                con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                print(f"  + {table}.{col}")
    con.commit()
    con.close()


# ── Concept map loader ────────────────────────────────────────────────────────

def load_concept_map(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── API helpers ───────────────────────────────────────────────────────────────

def _get_json(url: str, retries: int = 3) -> Optional[dict]:
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and "DOCTYPE" not in r.text[:200]:
                return r.json()
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"    WARN: {e}")
                return None


def _parse_clp(s: str) -> float:
    """Convierte '1234567,89' → float."""
    try:
        return float(str(s).replace(",", ".").replace(" ", ""))
    except (ValueError, AttributeError):
        return 0.0


def _fetch_accounts(endpoint: str, code: str, year: int, month: int,
                    account_key: str) -> dict[str, float]:
    """Devuelve {CodigoCuenta: MonedaTotal} para un banco/año/mes."""
    url = (f"{BASE_URL}/{endpoint}/{year}/{month:02d}/instituciones/{code}"
           f"?apikey={API_KEY}&formato=json")
    data = _get_json(url)
    if not data:
        return {}
    accounts = data.get(account_key, [])
    return {a["CodigoCuenta"]: _parse_clp(a.get("MonedaTotal", "0,00"))
            for a in accounts if "CodigoCuenta" in a}


# ── Mapper ────────────────────────────────────────────────────────────────────

def _detect_scheme(raw: dict[str, float]) -> str:
    """
    Detecta si los datos son del esquema nuevo (2022+, codigos 9 digitos)
    o del esquema legado (pre-2022, codigos 7 digitos, valores en MM CLP).
    """
    # If we see 9-digit codes, it's the new scheme
    for code in raw:
        if len(code) == 9:
            return "new"
    return "legacy"


def _apply_map(raw: dict[str, float], field_map: dict,
               scale: float = 1.0) -> dict:
    """
    Mapea cuentas CMF → campos warehouse.
    scale: factor de escala para convertir a CLP raw (1.0 nuevo, 1e6 legado).
    """
    result: dict = {}
    negate_fields = {field for field, spec in field_map.items()
                     if spec.get("negate", False)}

    for field, spec in field_map.items():
        if "account" in spec:
            val = raw.get(spec["account"])
            if val is not None:
                val *= scale
                result[field] = abs(val) if field in negate_fields else val
        elif "sum_accounts" in spec:
            vals = [raw.get(a, 0.0) for a in spec["sum_accounts"]]
            if any(v != 0.0 for v in vals):
                total = sum(vals) * scale
                result[field] = total  # sum accounts are never negated

    return result


def map_balance(raw: dict[str, float], cmap: dict) -> dict:
    """Aplica el mapeo de balance correcto segun el esquema detectado."""
    scheme = _detect_scheme(raw)
    if scheme == "new":
        bal_map = cmap.get("balance", {})
        scale   = 1.0
    else:
        bal_map = cmap.get("balance_legacy", {})
        scale   = 1e6   # valores en millones CLP

    result = _apply_map(raw, bal_map, scale)

    # equity = equity_parent + minority_interest (en esquema legado no hay cuenta directa)
    if scheme == "legacy":
        eqp = result.get("equity_parent")
        mi_raw = raw.get("3200000")
        if eqp is not None:
            mi = (mi_raw or 0.0) * scale
            result["equity"]           = eqp + mi
            result["minority_interest"] = mi
    else:
        eq  = result.get("equity")
        eqp = result.get("equity_parent")
        if eq is not None and eqp is not None:
            result["minority_interest"] = eq - eqp

    return result


def map_income(raw: dict[str, float], cmap: dict) -> dict:
    """Aplica el mapeo de estado de resultados correcto segun el esquema detectado."""
    scheme = _detect_scheme(raw)
    if scheme == "new":
        inc_map = cmap.get("income", {})
        scale   = 1.0
    else:
        inc_map = cmap.get("income_legacy", {})
        scale   = 1e6

    return _apply_map(raw, inc_map, scale)


# ── Row builder ───────────────────────────────────────────────────────────────

def build_row(ticker: str, code: str, year: int, cmap: dict) -> Optional[dict]:
    """Obtiene balance + resultados y construye una fila del warehouse."""
    bal_raw = _fetch_accounts("balances", code, year, MONTH,
                              "CodigosBalances")
    time.sleep(SLEEP_S)
    inc_raw = _fetch_accounts("resultados", code, year, MONTH,
                              "CodigosEstadosDeResultado")
    time.sleep(SLEEP_S)

    if not bal_raw and not inc_raw:
        return None

    bal = map_balance(bal_raw, cmap)
    inc = map_income(inc_raw, cmap)

    if not bal and not inc:
        return None

    # Campos no aplicables → None explícito
    na_fields = cmap.get("not_applicable", [])

    row: dict = {
        "ticker":             ticker,
        "year":               year,
        "month":              MONTH,
        "industry":           "financial",
        "reporting_currency": "CLP",
    }
    row.update(bal)
    row.update(inc)
    for col in na_fields:
        row.setdefault(col, None)

    return row


# ── Derived metrics for banks ─────────────────────────────────────────────────

def _v(row: dict, col: str) -> Optional[float]:
    v = row.get(col)
    return None if (v is None or (isinstance(v, float) and pd.isna(v))) else float(v)


def derive_bank_metrics(rows: list[dict]) -> pd.DataFrame:
    """
    Metricas derivadas especificas de bancos:
      nim              = net_interest_income / (loans_to_customers + financial_assets)
      cost_to_income   = (employee_benefits + depreciation_amortization) / revenue
      credit_loss_ratio= credit_loss_expense / loans_to_customers
      loan_to_deposit  = loans_to_customers / deposits_from_customers

    Solo para industry=financial. Columns not applicable for non-financial
    ya se manejan en pipeline.py.
    """
    derived_rows = []
    for row in rows:
        r: dict = {
            "ticker":   row["ticker"],
            "year":     row["year"],
            "month":    row["month"],
            "industry": "financial",
        }

        # NIM
        nii    = _v(row, "net_interest_income")
        loans  = _v(row, "loans_to_customers")
        fin_a  = _v(row, "financial_assets")
        earning = None
        if loans is not None or fin_a is not None:
            earning = (loans or 0.0) + (fin_a or 0.0)
        if nii is not None and earning and earning > 0:
            r["nim"]        = nii / earning
            r["nim_source"] = "nii_over_earning_assets"
        else:
            r["nim"]        = None
            r["nim_source"] = "missing" if nii is None else "missing_earning_assets"

        # Cost-to-income
        emp   = _v(row, "employee_benefits")
        da    = _v(row, "depreciation_amortization")
        rev   = _v(row, "revenue")
        if emp is not None and rev and abs(rev) > 0:
            opex = (emp or 0.0) + (da or 0.0)
            r["cost_to_income"]        = opex / abs(rev)
            r["cost_to_income_source"] = "emp_plus_da_over_revenue"
        else:
            r["cost_to_income"]        = None
            r["cost_to_income_source"] = "missing"

        # Credit loss ratio
        cle = _v(row, "credit_loss_expense")
        if cle is not None and loans and loans > 0:
            r["credit_loss_ratio"]        = cle / loans
            r["credit_loss_ratio_source"] = "credit_loss_over_loans"
        else:
            r["credit_loss_ratio"]        = None
            r["credit_loss_ratio_source"] = "missing"

        # Loan-to-deposit
        dep = _v(row, "deposits_from_customers")
        if loans is not None and dep and dep > 0:
            r["loan_to_deposit"]        = loans / dep
            r["loan_to_deposit_source"] = "loans_over_deposits"
        else:
            r["loan_to_deposit"]        = None
            r["loan_to_deposit_source"] = "missing"

        # FCF / EBITDA / debt_total → not_applicable para bancos
        r["fcf"]                = None
        r["fcf_source"]         = "not_applicable"
        r["debt_total"]         = None
        r["debt_total_source"]  = "not_applicable"
        r["net_debt"]           = None
        r["ebitda_calc"]        = None
        r["ebitda_source"]      = "not_applicable"
        r["financing_liabilities"] = _v(row, "deposits_from_customers")

        derived_rows.append(r)

    return pd.DataFrame(derived_rows)


# ── Quality flags for banks ───────────────────────────────────────────────────

def bank_quality_flags(rows: list[dict]) -> pd.DataFrame:
    """
    Quality flags especificos para bancos:
      bank_data_quality        — high / medium / poor
      interest_data_completeness — pct de campos de interes disponibles
      data_completeness_pct   — criticos generales
    """
    critical = ["assets", "liabilities", "equity", "cash",
                "revenue", "net_income", "loans_to_customers",
                "deposits_from_customers"]
    interest_fields = ["interest_income", "interest_expense",
                       "net_interest_income"]

    flag_rows = []
    for row in rows:
        # General completeness
        critical_present = sum(1 for f in critical if _v(row, f) is not None)
        completeness = round(critical_present / len(critical) * 100, 1)

        # Interest data
        int_present = sum(1 for f in interest_fields if _v(row, f) is not None)
        int_completeness = round(int_present / len(interest_fields) * 100, 1)

        # Bank data quality
        has_loans    = _v(row, "loans_to_customers") is not None
        has_deposits = _v(row, "deposits_from_customers") is not None
        has_nii      = _v(row, "net_interest_income") is not None
        has_rev      = _v(row, "revenue") is not None

        if has_loans and has_deposits and has_nii and has_rev:
            bq = "high"
        elif has_rev and (has_loans or has_deposits):
            bq = "medium"
        else:
            bq = "poor"

        flag_rows.append({
            "ticker":                     row["ticker"],
            "year":                       row["year"],
            "month":                      row["month"],
            "industry":                   "financial",
            "bank_data_quality":          bq,
            "interest_data_completeness": int_completeness,
            "data_completeness_pct":      completeness,
            # Mantener campos generales para compatibilidad
            "operating_expenses_quality": "not_applicable",
            "debt_quality":               "not_applicable",
            "fcf_quality":                "not_applicable",
            "has_revenue":                has_rev,
            "has_assets":                 _v(row, "assets") is not None,
            "has_equity":                 _v(row, "equity") is not None,
            "has_operating_cf":           False,
        })

    return pd.DataFrame(flag_rows)


# ── Warehouse upsert ──────────────────────────────────────────────────────────

def _upsert_df(df: pd.DataFrame, table: str, con: sqlite3.Connection,
               key_cols: list[str]) -> None:
    """DELETE+INSERT para upsert semantics."""
    for _, row in df.iterrows():
        where = " AND ".join(f"{k}=?" for k in key_cols)
        vals  = [row[k] for k in key_cols]
        con.execute(f"DELETE FROM {table} WHERE {where}", vals)
    df.to_sql(table, con, if_exists="append", index=False)


def save_to_warehouse(rows: list[dict], derived: pd.DataFrame,
                      flags: pd.DataFrame, db_path: str) -> None:
    """Guarda las 3 tablas en el warehouse."""
    keys = ["ticker", "year", "month"]
    df_norm = pd.DataFrame(rows)

    con = sqlite3.connect(db_path)
    _upsert_df(df_norm, "normalized_financials", con, keys)
    _upsert_df(derived, "derived_metrics",       con, keys)
    _upsert_df(flags,   "quality_flags",          con, keys)
    con.commit()
    con.close()

    print(f"  normalized_financials : {len(df_norm)} filas")
    print(f"  derived_metrics       : {len(derived)} filas")
    print(f"  quality_flags         : {len(flags)} filas")


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(rows: list[dict], derived: pd.DataFrame) -> None:
    print(f"\n{'='*65}")
    print("RESUMEN BANCOS")
    for ticker in sorted({r["ticker"] for r in rows}):
        t_rows   = [r for r in rows if r["ticker"] == ticker]
        t_der    = derived[derived["ticker"] == ticker]
        years_ok = sorted(r["year"] for r in t_rows)
        nim_vals = t_der["nim"].dropna()
        cti_vals = t_der["cost_to_income"].dropna()

        print(f"\n  {ticker}  ({years_ok[0]}-{years_ok[-1]}, {len(years_ok)} anos)")
        # Show key metrics for most recent year
        last = t_rows[-1]
        assets_b = (last.get("assets") or 0) / 1e9
        rev_b    = (last.get("revenue") or 0) / 1e9
        ni_b     = (last.get("net_income") or 0) / 1e9
        nii_b    = (last.get("net_interest_income") or 0) / 1e9
        loans_b  = (last.get("loans_to_customers") or 0) / 1e9
        dep_b    = (last.get("deposits_from_customers") or 0) / 1e9
        print(f"    {last['year']}: assets={assets_b:.0f}B  revenue={rev_b:.0f}B  "
              f"net_income={ni_b:.0f}B")
        print(f"          nii={nii_b:.0f}B  loans={loans_b:.0f}B  deposits={dep_b:.0f}B")
        if not nim_vals.empty:
            print(f"    NIM (avg): {nim_vals.mean()*100:.2f}%  "
                  f"CTI (avg): {cti_vals.mean()*100:.1f}%")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="CMF API → Bank Financial Data → warehouse.db")
    ap.add_argument("--ticker",     default=None,
                    help="Solo un ticker: BCI.SN")
    ap.add_argument("--years",      default=",".join(str(y) for y in YEARS),
                    help="Anos separados por coma (default: 2010-2025)")
    ap.add_argument("--all-banks",  action="store_true",
                    help="Incluye CHILE.SN y BICE.SN (ya en XBRL)")
    ap.add_argument("--db",         default=DB_PATH)
    ap.add_argument("--map",        default=CONCEPT_MAP)
    args = ap.parse_args()

    if not API_KEY:
        print("ERROR: CMF_API_KEY no encontrado en .env")
        return

    cmap  = load_concept_map(args.map)
    years = [int(y) for y in args.years.split(",")]

    bank_map = ALL_BANK_CODES if args.all_banks else BANK_CODES
    if args.ticker:
        t = args.ticker.strip()
        if t not in ALL_BANK_CODES:
            print(f"ERROR: {t} no conocido. Disponibles: {list(ALL_BANK_CODES.keys())}")
            return
        bank_map = {t: ALL_BANK_CODES[t]}

    print(f"Bancos: {list(bank_map.keys())}")
    print(f"Anos:   {years[0]}-{years[-1]} ({len(years)} periodos)")
    print(f"Total requests: {len(bank_map) * len(years) * 2}")
    print()

    # Ensure bank-specific columns exist
    ensure_bank_columns(args.db)

    all_rows: list[dict] = []

    for ticker, code in bank_map.items():
        print(f"  {ticker} (codigo CMF: {code})")
        for year in years:
            print(f"    {year} ... ", end="", flush=True)
            row = build_row(ticker, code, year, cmap)
            if row:
                all_rows.append(row)
                assets_b = (row.get("assets") or 0) / 1e9
                rev_b    = (row.get("revenue") or 0) / 1e9
                ni_b     = (row.get("net_income") or 0) / 1e9
                print(f"OK  assets={assets_b:,.0f}B  rev={rev_b:,.0f}B  ni={ni_b:,.0f}B")
            else:
                print("sin datos")

    if not all_rows:
        print("No se obtuvieron datos.")
        return

    print(f"\nComputando metricas derivadas bancarias ...")
    derived = derive_bank_metrics(all_rows)

    print(f"Computando quality flags ...")
    flags   = bank_quality_flags(all_rows)

    print(f"\nGuardando en {args.db} ...")
    save_to_warehouse(all_rows, derived, flags, args.db)

    print_summary(all_rows, derived)


if __name__ == "__main__":
    main()
