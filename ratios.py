"""
ratios.py — Financial Ratio Computation Engine
===============================================
Reads normalized_financials + derived_metrics from warehouse.db.
Produces 3 tables saved back to the same database:

  ratios              — wide format, one row per (ticker, year, month)
  ratio_components    — long format, numerator + denominator per ratio per row
  ratio_quality_flags — long format, quality grade per ratio per row

Industry rules:
  non_financial  → full ratio set (debt, EBITDA, efficiency, etc.)
  financial      → restricted set; EBITDA/debt ratios marked not_applicable

Valuation ratios (P/E, P/B, EV/EBITDA) require external price data.
Pass --prices prices.csv  (columns: ticker, year, price)

Usage:
  python ratios.py
  python ratios.py --prices prices.csv
  python ratios.py --no-csv
"""

import argparse
import math
import os
import sqlite3
from dataclasses import dataclass, field as dc_field
from typing import Optional

import pandas as pd


# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = os.path.join("output", "warehouse.db")
OUT_DIR = "output"

# Fields sourced from derived_metrics (vs normalized_financials)
DERIVED_FIELDS = frozenset({
    "fcf", "net_debt", "debt_total", "ebitda_calc", "financing_liabilities",
    # Bank-specific derived fields
    "nim", "cost_to_income", "credit_loss_ratio", "loan_to_deposit",
})

# Fields that are themselves estimates/derived (lower quality grade)
ESTIMATED_FIELDS = frozenset({
    "ebitda_calc", "net_debt", "debt_total", "fcf"
})


# ── Ratio Specifications ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class RatioSpec:
    name:         str
    label:        str
    numerator:    str
    denominator:  str
    category:     str
    industries:   frozenset = frozenset({"financial", "non_financial"})
    abs_denom:    bool      = False   # use |denominator| to protect sign-flip
    multiply:     float     = 1.0     # scale factor (e.g. 100 for %)


RATIO_SPECS: list[RatioSpec] = [

    # ── Profitability ────────────────────────────────────────────────────────
    RatioSpec("roe",              "Return on Equity",
              "net_income",       "equity",              "profitability"),

    RatioSpec("roe_parent",       "ROE (Parent Shareholders)",
              "net_income_parent","equity_parent",        "profitability"),

    RatioSpec("roa",              "Return on Assets",
              "net_income",       "assets",              "profitability"),

    RatioSpec("gross_margin",     "Gross Margin",
              "gross_profit",     "revenue",             "profitability",
              industries=frozenset({"non_financial"})),

    RatioSpec("ebit_margin",      "EBIT Margin",
              "ebit",             "revenue",             "profitability"),

    RatioSpec("net_margin",       "Net Profit Margin",
              "net_income",       "revenue",             "profitability"),

    RatioSpec("ebitda_margin",    "EBITDA Margin",
              "ebitda_calc",      "revenue",             "profitability",
              industries=frozenset({"non_financial"})),

    # ── Leverage ─────────────────────────────────────────────────────────────
    RatioSpec("debt_to_equity",   "Debt / Equity",
              "debt_total",       "equity",              "leverage",
              industries=frozenset({"non_financial"})),

    RatioSpec("debt_to_assets",   "Debt / Assets",
              "debt_total",       "assets",              "leverage",
              industries=frozenset({"non_financial"})),

    RatioSpec("net_debt_to_ebitda", "Net Debt / EBITDA",
              "net_debt",         "ebitda_calc",         "leverage",
              industries=frozenset({"non_financial"})),

    RatioSpec("interest_coverage","Interest Coverage (EBIT / Finance Costs)",
              "ebit",             "finance_costs",       "leverage",
              abs_denom=True),

    RatioSpec("equity_multiplier","Equity Multiplier (Assets / Equity)",
              "assets",           "equity",              "leverage"),

    # ── Liquidity (current_ratio / cash_ratio only for non-financial) ─────────
    RatioSpec("current_ratio",    "Current Ratio",
              "current_assets",   "current_liabilities", "liquidity",
              industries=frozenset({"non_financial"})),

    RatioSpec("cash_ratio",       "Cash Ratio",
              "cash",             "current_liabilities", "liquidity",
              industries=frozenset({"non_financial"})),

    # ── Efficiency ────────────────────────────────────────────────────────────
    RatioSpec("asset_turnover",   "Asset Turnover",
              "revenue",          "assets",              "efficiency",
              industries=frozenset({"non_financial"})),

    RatioSpec("receivables_turnover", "Receivables Turnover",
              "revenue",          "trade_receivables",   "efficiency",
              industries=frozenset({"non_financial"})),

    RatioSpec("inventory_turnover","Inventory Turnover",
              "cost_of_sales",    "inventories",         "efficiency",
              industries=frozenset({"non_financial"})),

    RatioSpec("capex_intensity",  "CAPEX Intensity",
              "capex",            "revenue",             "efficiency",
              industries=frozenset({"non_financial"})),

    # ── Cash Flow (non-financial only; banks have no CFO/FCF) ────────────────
    RatioSpec("fcf_margin",       "FCF Margin",
              "fcf",              "revenue",             "cashflow",
              industries=frozenset({"non_financial"})),

    RatioSpec("fcf_payout_ratio", "FCF Payout Ratio",
              "dividends_paid",   "fcf",                 "cashflow",
              abs_denom=True,
              industries=frozenset({"non_financial"})),

    RatioSpec("cfo_to_net_income","CFO / Net Income (Cash Quality)",
              "cfo",              "net_income",          "cashflow",
              industries=frozenset({"non_financial"})),

    RatioSpec("capex_to_da",      "CAPEX / Depreciation",
              "capex",            "depreciation_amortization", "cashflow",
              industries=frozenset({"non_financial"})),

    # ── Valuation (requires external price data) ──────────────────────────────
    # Computed separately in _compute_valuation()
]

# Bank-specific ratios — pre-computed by bank_pipeline.py, stored in
# derived_metrics. Passed through directly to the ratios table.
# Format: (ratio_name, label, category)
BANK_PASSTHROUGH_RATIOS: list[tuple[str, str, str]] = [
    ("nim",               "Net Interest Margin",                    "profitability"),
    ("cost_to_income",    "Cost-to-Income Ratio",                   "efficiency"),
    ("credit_loss_ratio", "Credit Loss Ratio (Prov. / Loans)",      "leverage"),
    ("loan_to_deposit",   "Loan-to-Deposit Ratio",                  "liquidity"),
]

# Valuation ratio specs (need market_cap; built inline)
VALUATION_SPECS: list[RatioSpec] = [
    RatioSpec("pe_ratio",         "P/E Ratio",
              "market_cap",       "net_income",          "valuation"),

    RatioSpec("pb_ratio",         "P/B Ratio",
              "market_cap",       "equity",              "valuation"),

    RatioSpec("ev_to_ebitda",     "EV / EBITDA",
              "ev",               "ebitda_calc",         "valuation",
              industries=frozenset({"non_financial"})),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _v(row: pd.Series, field: str) -> Optional[float]:
    """Safe float extraction; returns None on NaN/None/non-finite."""
    val = row.get(field)
    if val is None:
        return None
    try:
        f = float(val)
        return None if not math.isfinite(f) else f
    except (TypeError, ValueError):
        return None


def _source(field: str) -> str:
    return "derived_metrics" if field in DERIVED_FIELDS else "normalized_financials"


def _quality(num_field: str, den_field: str) -> tuple[str, str]:
    """Grade and reason when ratio computed successfully."""
    if num_field in ESTIMATED_FIELDS or den_field in ESTIMATED_FIELDS:
        return "medium", "estimated_component"
    return "high", "all_direct_xbrl"


# ── Core Computation ──────────────────────────────────────────────────────────

def _compute_spec(
    row: pd.Series,
    spec: RatioSpec,
    override_num: Optional[float] = None,
    override_den: Optional[float] = None,
) -> tuple[Optional[float], str, str, Optional[float], Optional[float]]:
    """
    Returns (ratio_value, quality, reason, num_val, den_val).
    override_* used for valuation ratios (market_cap, ev).
    """
    num_val = override_num if override_num is not None else _v(row, spec.numerator)
    den_val = override_den if override_den is not None else _v(row, spec.denominator)

    if num_val is None or den_val is None:
        missing = [f for f, v in [(spec.numerator, num_val), (spec.denominator, den_val)]
                   if v is None]
        return None, "low", f"missing:{','.join(missing)}", num_val, den_val

    den_eff = abs(den_val) if spec.abs_denom else den_val

    if den_eff == 0:
        return None, "invalid", "division_by_zero", num_val, den_val

    result = (num_val / den_eff) * spec.multiply

    if not math.isfinite(result):
        return None, "invalid", "non_finite_result", num_val, den_val

    quality, reason = _quality(spec.numerator, spec.denominator)
    return result, quality, reason, num_val, den_val


def compute_row(
    row: pd.Series,
    price_row: Optional[pd.Series] = None,
) -> tuple[dict, list[dict], list[dict]]:
    """
    Processes one (ticker, year, month) row.
    Returns (ratio_values, component_rows, flag_rows).
    """
    industry = row.get("industry", "non_financial")
    key = {
        "ticker": row["ticker"],
        "year":   int(row["year"]),
        "month":  int(row["month"]),
    }

    ratio_vals: dict      = {**key, "industry": industry}
    comp_rows:  list[dict] = []
    flag_rows:  list[dict] = []

    all_specs = list(RATIO_SPECS)

    # Valuation — only if price data available
    market_cap: Optional[float] = None
    ev:         Optional[float] = None
    if price_row is not None:
        price  = _v(price_row, "price")
        shares = _v(row, "shares_outstanding")
        if price is not None and shares is not None:
            market_cap = price * shares
            net_debt   = _v(row, "net_debt")
            ev = (market_cap + net_debt) if net_debt is not None else None
    all_specs += VALUATION_SPECS

    # Bank-specific pass-through ratios (pre-computed in derived_metrics)
    for rname, label, category in BANK_PASSTHROUGH_RATIOS:
        val = _v(row, rname)
        if industry == "financial":
            ratio_vals[rname] = val
            quality  = "medium" if val is not None else "low"
            reason   = "bank_pipeline_derived" if val is not None else "missing:bank_derived"
            flag_rows.append({**key, "ratio_name": rname, "category": category,
                               "quality": quality, "reason": reason})
        else:
            ratio_vals[rname] = None
            flag_rows.append({**key, "ratio_name": rname, "category": category,
                               "quality": "not_applicable", "reason": "industry_exclusion"})

    for spec in all_specs:
        rname = spec.name

        # Industry exclusion
        if industry not in spec.industries:
            ratio_vals[rname] = None
            flag_rows.append({**key, "ratio_name": rname, "category": spec.category,
                               "quality": "not_applicable", "reason": "industry_exclusion"})
            continue

        # Valuation special handling
        override_num = override_den = None
        if spec.name in ("pe_ratio", "pb_ratio"):
            override_num = market_cap
        elif spec.name == "ev_to_ebitda":
            override_num = ev

        if spec in VALUATION_SPECS and market_cap is None:
            ratio_vals[rname] = None
            flag_rows.append({**key, "ratio_name": rname, "category": spec.category,
                               "quality": "low", "reason": "missing:price_data"})
            continue

        result, quality, reason, num_val, den_val = _compute_spec(
            row, spec, override_num, override_den
        )

        ratio_vals[rname] = result
        flag_rows.append({**key, "ratio_name": rname, "category": spec.category,
                           "quality": quality, "reason": reason})

        # Components — logged for every ratio (including failures) for full traceability
        comp_rows += [
            {**key, "ratio_name": rname,
             "component": "numerator",
             "field":     spec.numerator,
             "value":     num_val,
             "source":    _source(spec.numerator)},
            {**key, "ratio_name": rname,
             "component": "denominator",
             "field":     spec.denominator,
             "value":     den_val,
             "source":    _source(spec.denominator)},
        ]

    return ratio_vals, comp_rows, flag_rows


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_working_table(db_path: str) -> pd.DataFrame:
    """
    Joins normalized_financials + derived_metrics.
    Derived-only columns are added; no column is overwritten from normalized.
    """
    con = sqlite3.connect(db_path)
    norm    = pd.read_sql("SELECT * FROM normalized_financials", con)
    derived = pd.read_sql("SELECT * FROM derived_metrics", con)
    con.close()

    keys = ["ticker", "year", "month"]
    # Only bring derived-only columns into the merge (plus keys)
    derived_only_cols = [c for c in derived.columns if c not in norm.columns or c in keys]
    return norm.merge(derived[derived_only_cols], on=keys, how="left")


def load_prices(prices_path: str) -> Optional[pd.DataFrame]:
    if not prices_path or not os.path.exists(prices_path):
        return None
    df = pd.read_csv(prices_path)
    required = {"ticker", "year", "price"}
    if not required.issubset(df.columns):
        print(f"  WARNING: prices file missing columns {required - set(df.columns)}")
        return None
    return df.set_index(["ticker", "year"])


def save_to_sqlite(tables: dict[str, pd.DataFrame], db_path: str) -> None:
    con = sqlite3.connect(db_path)
    for name, df in tables.items():
        df.to_sql(name, con, if_exists="replace", index=False)
    con.close()


# ── Summary Report ─────────────────────────────────────────────────────────────

def print_summary(ratios: pd.DataFrame, flags: pd.DataFrame) -> None:
    ratio_cols = ([s.name for s in RATIO_SPECS + VALUATION_SPECS]
                  + [r[0] for r in BANK_PASSTHROUGH_RATIOS])

    print(f"\n{'='*65}")
    print(f"ratios              : {len(ratios):,} rows | "
          f"{ratios['ticker'].nunique()} tickers")
    print(f"ratio_quality_flags : {len(flags):,} rows")

    print("\nQuality distribution (all ratios × all rows):")
    dist  = flags["quality"].value_counts()
    total = len(flags)
    for q in ("high", "medium", "low", "invalid", "not_applicable"):
        cnt = dist.get(q, 0)
        pct = cnt / total * 100
        bar = "#" * int(pct / 4)
        print(f"  {q:<20} {cnt:>5}  ({pct:5.1f}%)  {bar}")

    print("\nCoverage by ratio (% rows with computed value):")
    cats = ({s.name: s.category for s in RATIO_SPECS + VALUATION_SPECS}
            | {r[0]: r[2] for r in BANK_PASSTHROUGH_RATIOS})
    present = [c for c in ratio_cols if c in ratios.columns]
    cov = (ratios[present].notna().mean() * 100).sort_values(ascending=False)
    prev_cat = None
    for rname, pct in cov.items():
        cat = cats.get(rname, "?")
        if cat != prev_cat:
            print(f"\n  [{cat.upper()}]")
            prev_cat = cat
        bar = "#" * int(pct / 5)
        print(f"    {rname:<35} {pct:5.1f}%  {bar}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="CMF Ratio Computation Engine")
    ap.add_argument("--db",     default=DB_PATH, help="warehouse.db path")
    ap.add_argument("--prices", default=None,    help="CSV with ticker,year,price")
    ap.add_argument("--no-csv", action="store_true")
    args = ap.parse_args()

    print(f"Loading warehouse: {args.db}")
    working = load_working_table(args.db)
    print(f"  {len(working):,} periods | {working['ticker'].nunique()} tickers")

    prices = load_prices(args.prices)
    if prices is not None:
        print(f"  Price data loaded: {len(prices)} ticker-year entries")
    else:
        print("  No price data — valuation ratios will be null")

    print("\nComputing ratios...")
    all_ratios:  list[dict] = []
    all_comps:   list[dict] = []
    all_flags:   list[dict] = []

    for _, row in working.iterrows():
        price_row = None
        if prices is not None:
            key = (row["ticker"], row["year"])
            if key in prices.index:
                price_row = prices.loc[key]

        ratio_vals, comps, flags = compute_row(row, price_row)
        all_ratios.append(ratio_vals)
        all_comps.extend(comps)
        all_flags.extend(flags)

    ratios_df = pd.DataFrame(all_ratios)
    comps_df  = pd.DataFrame(all_comps)
    flags_df  = pd.DataFrame(all_flags)

    tables = {
        "ratios":              ratios_df,
        "ratio_components":    comps_df,
        "ratio_quality_flags": flags_df,
    }

    print("Saving to SQLite...")
    save_to_sqlite(tables, args.db)
    print(f"  {args.db}  (+3 tables)")

    if not args.no_csv:
        os.makedirs(OUT_DIR, exist_ok=True)
        for name, df in tables.items():
            path = os.path.join(OUT_DIR, f"{name}.csv")
            df.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"  CSV: {path}")

    print_summary(ratios_df, flags_df)


if __name__ == "__main__":
    main()
