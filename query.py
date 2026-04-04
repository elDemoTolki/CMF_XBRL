"""
query.py — Consulta histórica por ticker desde warehouse.db
============================================================
Genera una tabla wide con todo el historial disponible de un ticker,
combinando normalized_financials + derived_metrics + ratios.

Uso:
  python query.py --ticker FALABELLA.SN
  python query.py --ticker FALABELLA.SN --format excel
  python query.py --ticker FALABELLA.SN --section ratios
  python query.py --tickers FALABELLA.SN,CENCOSUD.SN --section balance

Secciones disponibles (--section):
  all        → todo (default)
  balance    → activos, pasivos, patrimonio
  income     → P&L completo
  cashflow   → flujo de caja
  debt       → métricas de deuda
  ratios     → todos los ratios computados
  summary    → vista ejecutiva (métricas clave solamente)
"""

import argparse
import os
import sqlite3
from typing import Optional

import pandas as pd

DB_PATH = os.path.join("output", "warehouse.db")
OUT_DIR = "output"

# ── Column groups ─────────────────────────────────────────────────────────────

SECTIONS: dict[str, list[str]] = {
    "balance": [
        "assets", "current_assets", "non_current_assets",
        "cash",
        "trade_receivables", "inventories", "ppe", "intangibles", "goodwill",
        "liabilities", "current_liabilities", "non_current_liabilities",
        "debt_short_term", "debt_long_term", "borrowings",
        "trade_payables",
        "equity", "equity_parent", "minority_interest",
        "issued_capital", "retained_earnings",
        # Bank-specific balance fields
        "financial_assets", "loans_to_customers", "deposits_from_customers",
    ],
    "income": [
        "revenue", "cost_of_sales", "gross_profit",
        "distribution_costs", "administrative_expense",
        "other_income", "other_expense", "employee_benefits",
        "operating_income", "ebit",
        "finance_income", "finance_costs",
        "profit_before_tax", "income_tax",
        "net_income", "net_income_parent",
        "depreciation_amortization",
        # Bank-specific income fields
        "interest_income", "interest_expense", "net_interest_income",
        "net_fee_income", "credit_loss_expense",
    ],
    "cashflow": [
        "cfo", "capex", "investing_cf",
        "dividends_paid", "proceeds_from_borrowings", "repayment_of_borrowings",
        "financing_cf", "net_change_cash",
        # derived
        "fcf",
    ],
    "debt": [
        "cash",
        "debt_short_term", "debt_long_term", "borrowings",
        "debt_total", "net_debt",
        "ebitda_calc",
        "finance_costs",
        # Bank funding structure
        "deposits_from_customers", "loans_to_customers", "loan_to_deposit",
    ],
    "ratios": [
        "roe", "roe_parent", "roa",
        "gross_margin", "ebit_margin", "net_margin", "ebitda_margin",
        "debt_to_equity", "debt_to_assets", "net_debt_to_ebitda",
        "interest_coverage", "equity_multiplier",
        "current_ratio", "cash_ratio",
        "asset_turnover", "receivables_turnover", "inventory_turnover",
        "capex_intensity",
        "fcf_margin", "fcf_payout_ratio", "cfo_to_net_income", "capex_to_da",
        # Bank-specific ratios
        "nim", "cost_to_income", "credit_loss_ratio", "loan_to_deposit",
    ],
    "summary": [
        # P&L (universal)
        "revenue", "ebit", "net_income",
        # P&L (non-financial)
        "ebitda_calc",
        # P&L (banks)
        "net_interest_income", "credit_loss_expense",
        # Balance (universal)
        "assets", "cash", "equity",
        # Balance (non-financial)
        "debt_total", "net_debt",
        # Balance (banks)
        "loans_to_customers", "deposits_from_customers",
        # Cash flow (non-financial)
        "cfo", "capex", "fcf",
        # Ratios (universal)
        "roe", "ebit_margin", "net_margin",
        # Ratios (non-financial)
        "ebitda_margin", "debt_to_equity", "net_debt_to_ebitda",
        "current_ratio", "fcf_margin",
        # Ratios (banks)
        "nim", "cost_to_income", "credit_loss_ratio",
    ],
}

SECTION_SOURCES: dict[str, list[str]] = {
    "balance":  ["normalized_financials"],
    "income":   ["normalized_financials"],
    "cashflow": ["normalized_financials", "derived_metrics"],
    "debt":     ["normalized_financials", "derived_metrics"],
    "ratios":   ["ratios"],
    "summary":  ["normalized_financials", "derived_metrics", "ratios"],
    "all":      ["normalized_financials", "derived_metrics", "ratios"],
}

# ── Loader ────────────────────────────────────────────────────────────────────

def load_ticker(db_path: str, tickers: list[str]) -> pd.DataFrame:
    """
    Joins all relevant tables for the given tickers.
    Returns a wide DataFrame sorted by (ticker, year, month).
    """
    placeholders = ",".join("?" * len(tickers))
    con = sqlite3.connect(db_path)

    norm = pd.read_sql(
        f"SELECT * FROM normalized_financials WHERE ticker IN ({placeholders})",
        con, params=tickers
    )
    derived = pd.read_sql(
        f"SELECT * FROM derived_metrics WHERE ticker IN ({placeholders})",
        con, params=tickers
    )
    rat = pd.read_sql(
        f"SELECT * FROM ratios WHERE ticker IN ({placeholders})",
        con, params=tickers
    )
    flags = pd.read_sql(
        f"SELECT ticker, year, month, data_completeness_pct FROM quality_flags "
        f"WHERE ticker IN ({placeholders})",
        con, params=tickers
    )
    con.close()

    keys = ["ticker", "year", "month"]

    # Drop overlapping non-key cols from derived and ratios before merge
    derived_cols = [c for c in derived.columns if c not in norm.columns or c in keys]
    rat_cols     = [c for c in rat.columns     if c not in norm.columns or c in keys]

    df = (
        norm
        .merge(derived[derived_cols], on=keys, how="left")
        .merge(rat[rat_cols],         on=keys, how="left")
        .merge(flags,                 on=keys, how="left")
        .sort_values(["ticker", "year", "month"])
        .reset_index(drop=True)
    )
    return df


def select_columns(df: pd.DataFrame, section: str) -> pd.DataFrame:
    """Filters to relevant columns for the requested section."""
    base = ["ticker", "year", "month", "industry"]
    if section == "all":
        return df
    wanted = SECTIONS.get(section, [])
    available = [c for c in wanted if c in df.columns]
    missing   = [c for c in wanted if c not in df.columns]
    if missing:
        print(f"  Note: columns not available in this dataset: {missing}")
    return df[base + available]


# ── Formatting ────────────────────────────────────────────────────────────────

# Columns to format as billions (CLP)
BILLIONS_COLS = {
    "assets", "current_assets", "non_current_assets",
    "cash", "trade_receivables", "inventories", "ppe", "intangibles", "goodwill",
    "liabilities", "current_liabilities", "non_current_liabilities",
    "debt_short_term", "debt_long_term", "borrowings", "trade_payables",
    "equity", "equity_parent", "minority_interest", "issued_capital", "retained_earnings",
    "revenue", "cost_of_sales", "gross_profit",
    "distribution_costs", "administrative_expense",
    "other_income", "other_expense", "employee_benefits",
    "operating_income", "ebit", "finance_income", "finance_costs",
    "profit_before_tax", "income_tax", "net_income", "net_income_parent",
    "depreciation_amortization",
    "cfo", "capex", "investing_cf",
    "dividends_paid", "proceeds_from_borrowings", "repayment_of_borrowings",
    "financing_cf", "net_change_cash",
    "fcf", "debt_total", "net_debt", "ebitda_calc", "financing_liabilities",
    # Bank-specific monetary fields
    "financial_assets", "loans_to_customers", "deposits_from_customers",
    "interest_income", "interest_expense", "net_interest_income",
    "net_fee_income", "credit_loss_expense",
}

# Columns to format as percentages
PCT_COLS = {
    "gross_margin", "ebit_margin", "net_margin", "ebitda_margin",
    "roe", "roe_parent", "roa",
    "debt_to_assets", "capex_intensity", "fcf_margin",
    # Bank-specific ratios (expressed as %)
    "nim", "cost_to_income", "credit_loss_ratio",
}

# Columns to show as plain ratios (2 decimals)
RATIO_COLS = {
    "debt_to_equity", "net_debt_to_ebitda", "interest_coverage",
    "equity_multiplier", "current_ratio", "cash_ratio",
    "asset_turnover", "receivables_turnover", "inventory_turnover",
    "fcf_payout_ratio", "cfo_to_net_income", "capex_to_da",
    "pe_ratio", "pb_ratio", "ev_to_ebitda",
    # Bank-specific ratios (displayed as x)
    "loan_to_deposit",
}


def _fmt_val(col: str, val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    v = float(val)
    if col in BILLIONS_COLS:
        b = v / 1e9
        return f"{b:>10.1f}"
    if col in PCT_COLS:
        return f"{v * 100:>8.1f}%"
    if col in RATIO_COLS:
        return f"{v:>8.2f}x"
    if col == "shares_outstanding":
        return f"{v/1e6:>8.1f}M"
    if col in ("eps_basic", "eps_diluted"):
        return f"{v:>10.4f}"
    if col == "data_completeness_pct":
        return f"{v:>6.1f}%"
    return f"{v:>12.2f}"


def print_table(df: pd.DataFrame, section: str, scale_note: bool = True) -> None:
    """Pretty-prints the historical table to console."""
    numeric_cols = [c for c in df.columns
                    if c not in ("ticker", "year", "month", "industry",
                                 "fcf_source", "debt_total_source",
                                 "ebitda_source", "industry")]
    if not numeric_cols:
        print(df.to_string(index=False))
        return

    tickers = df["ticker"].unique()
    for ticker in tickers:
        sub = df[df["ticker"] == ticker].copy()
        industry = sub["industry"].iloc[0] if "industry" in sub.columns else "?"

        print(f"\n{'='*70}")
        print(f"  {ticker}  |  Industry: {industry}  |  "
              f"{len(sub)} anios ({int(sub['year'].min())}-{int(sub['year'].max())})")
        if scale_note and any(c in BILLIONS_COLS for c in numeric_cols):
            print(f"  Monetario en miles de millones CLP (MM$)")
        print(f"{'='*70}")

        # Header row
        header = f"{'Métrica':<32}"
        for _, row in sub.iterrows():
            header += f"  {int(row['year']):>6}"
        print(header)
        print("-" * len(header))

        for col in numeric_cols:
            if col in ("year", "month"):
                continue
            label = col.replace("_", " ").title()
            line  = f"  {label:<30}"
            for _, row in sub.iterrows():
                line += f"  {_fmt_val(col, row.get(col)):>6}"
            print(line)

        print()


# ── Export ────────────────────────────────────────────────────────────────────

def export(df: pd.DataFrame, ticker_str: str, section: str, fmt: str) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    safe = ticker_str.replace(",", "_").replace(".", "").replace(" ", "")
    base = os.path.join(OUT_DIR, f"{safe}_{section}")

    if fmt in ("csv", "both"):
        path = base + ".csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  Guardado: {path}")

    if fmt in ("excel", "both"):
        path = base + ".xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=section[:31], index=False)
            # Auto-width columns
            ws = writer.sheets[section[:31]]
            for col in ws.columns:
                max_len = max(len(str(cell.value or "")) for cell in col) + 2
                ws.column_dimensions[col[0].column_letter].width = min(max_len, 30)
        print(f"  Guardado: {path}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Historial financiero por ticker")
    ap.add_argument("--ticker",  default=None,
                    help="Ticker o lista separada por comas: FALABELLA.SN,CENCOSUD.SN")
    ap.add_argument("--tickers", default=None,
                    help="Alias de --ticker")
    ap.add_argument("--section", default="summary",
                    choices=["all", "balance", "income", "cashflow",
                             "debt", "ratios", "summary"],
                    help="Sección a mostrar (default: summary)")
    ap.add_argument("--format",  default="console",
                    choices=["console", "csv", "excel", "both"],
                    help="Formato de salida")
    ap.add_argument("--db",      default=DB_PATH)
    ap.add_argument("--list",    action="store_true",
                    help="Listar tickers disponibles y salir")
    args = ap.parse_args()

    # List available tickers
    if args.list:
        con = sqlite3.connect(args.db)
        tickers = pd.read_sql(
            "SELECT ticker, industry, COUNT(*) as years, MIN(year) as desde, MAX(year) as hasta "
            "FROM normalized_financials GROUP BY ticker, industry ORDER BY ticker",
            con
        )
        con.close()
        print(tickers.to_string(index=False))
        return

    ticker_str = args.ticker or args.tickers
    if not ticker_str:
        ap.error("Especifica --ticker FALABELLA.SN  (o --list para ver disponibles)")

    tickers = [t.strip() for t in ticker_str.split(",")]
    print(f"Cargando: {tickers}  |  sección: {args.section}")

    df_full = load_ticker(args.db, tickers)
    if df_full.empty:
        print(f"  No se encontraron datos para: {tickers}")
        print(f"  Usa --list para ver los tickers disponibles.")
        return

    df = select_columns(df_full, args.section)

    if args.format == "console":
        print_table(df, args.section)
    else:
        export(df, ticker_str, args.section, args.format)
        if args.format in ("csv", "both", "excel"):
            print_table(df, args.section)


if __name__ == "__main__":
    main()
