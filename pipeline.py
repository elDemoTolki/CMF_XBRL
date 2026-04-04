"""
pipeline.py — Financial Data Warehouse Pipeline
================================================
Transforms raw XBRL facts into a structured 3-table schema:

  normalized_financials  — one row per (ticker, year, month), all mapped fields
  derived_metrics        — FCF, net_debt, EBITDA, financing_liabilities
  quality_flags          — field-level quality assessments

Industry rules:
  financial     → Banca, AFP (debt fields are not_applicable; bank-specific fields active)
  non_financial → everything else

Usage:
  python pipeline.py
  python pipeline.py --no-csv          # SQLite only
  python pipeline.py --input other.csv
"""

import argparse
import json
import os
import sqlite3
from typing import Optional

import pandas as pd
import yaml


# ── Config ────────────────────────────────────────────────────────────────────

FACTS_CSV    = os.path.join("output", "facts_raw.csv")
TICKERS_JSON = "tickers_chile.json"
CONCEPT_MAP  = "concept_map.yaml"
DB_PATH      = os.path.join("output", "warehouse.db")
OUT_DIR      = "output"

FINANCIAL_CATEGORIES = {"Banca", "AFP"}

# Concept_map field → warehouse column rename
FIELD_RENAME = {
    "operating_cf":          "cfo",
    "short_term_borrowings": "debt_short_term",
    "long_term_borrowings":  "debt_long_term",
}

# Ordered list of "critical" fields used to compute data_completeness_pct
CRITICAL_FIELDS = [
    "assets", "liabilities", "equity", "cash",
    "revenue", "ebit", "net_income",
    "cfo",
]


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_concept_map(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["fields"]


def load_facts(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df["concept_key"] = df["prefix"] + ":" + df["concept"]
    return df


def build_industry_map(tickers_path: str) -> dict[str, str]:
    """Returns {ticker: 'financial' | 'non_financial'}."""
    if not os.path.exists(tickers_path):
        return {}
    with open(tickers_path, encoding="utf-8") as f:
        tickers = json.load(f)
    result = {}
    for t in tickers:
        ticker = t.get("ticker", "")
        cat    = t.get("categoria", "")
        result[ticker] = "financial" if cat in FINANCIAL_CATEGORIES else "non_financial"
    return result


# ── Step 1: Normalize ─────────────────────────────────────────────────────────

def normalize(
    facts: pd.DataFrame,
    concept_map: dict,
    industry_map: dict[str, str],
) -> pd.DataFrame:
    """
    Produces one row per (ticker, year, month).
    Priority: consolidated (type=C already enforced by scraper) > CLP > full-year.
    First non-null candidate in each field's list wins.
    """
    key_cols = ["ticker", "year", "month", "context_role", "concept_key"]
    facts_idx = (
        facts.dropna(subset=["value"])
             .drop_duplicates(subset=key_cols, keep="first")
             .set_index(key_cols)["value"]
    )

    # Reporting currency: most common monetary unit per (ticker, year, month)
    currency_idx = (
        facts[facts["unit"].isin(["CLP", "USD", "EUR", "BRL"])]
        .groupby(["ticker", "year", "month"])["unit"]
        .agg(lambda x: x.value_counts().index[0])
    )

    periods = (
        facts[["ticker", "year", "month"]]
        .drop_duplicates()
        .sort_values(["ticker", "year", "month"])
        .reset_index(drop=True)
    )

    records = []
    for _, row in periods.iterrows():
        ticker = row["ticker"]
        year   = int(row["year"])
        month  = int(row["month"])
        industry = industry_map.get(ticker, "non_financial")

        try:
            currency = currency_idx.loc[(ticker, year, month)]
        except KeyError:
            currency = "CLP"

        rec = {
            "ticker":             ticker,
            "year":               year,
            "month":              month,
            "industry":           industry,
            "reporting_currency": currency,
        }

        for field, spec in concept_map.items():
            col      = FIELD_RENAME.get(field, field)
            ctx_role = spec["context_role"]
            negate   = spec.get("negate", False)

            val = None
            for ckey in spec.get("candidates", []):
                try:
                    v = facts_idx.loc[(ticker, year, month, ctx_role, ckey)]
                    if pd.notna(v):
                        val = v
                        break
                except KeyError:
                    continue

            if val is not None and negate:
                val = -val

            rec[col] = val

        records.append(rec)

    df = pd.DataFrame(records)

    # Enforce industry separation: null out non-applicable fields
    fin_mask  = df["industry"] == "financial"
    nfin_mask = df["industry"] == "non_financial"

    # Debt fields → only meaningful for non-financial
    for col in ("debt_short_term", "debt_long_term", "borrowings"):
        if col in df.columns:
            df.loc[fin_mask, col] = None

    # Bank-specific fields → only meaningful for financial
    for col in ("deposits_from_customers", "loans_to_customers"):
        if col in df.columns:
            df.loc[nfin_mask, col] = None

    return df


# ── Step 2: Derived Metrics ───────────────────────────────────────────────────

def _val(row: pd.Series, col: str) -> Optional[float]:
    v = row.get(col)
    return None if (v is None or pd.isna(v)) else float(v)


def derive_metrics(norm: pd.DataFrame) -> pd.DataFrame:
    """
    Computes derived metrics with industry-aware logic.
    All derivations are traceable via *_source columns.
    """
    rows = []
    for _, row in norm.iterrows():
        industry = row["industry"]

        r: dict = {
            "ticker":  row["ticker"],
            "year":    row["year"],
            "month":   row["month"],
            "industry": industry,
        }

        # ── FCF (all industries) ─────────────────────────────────────────
        cfo   = _val(row, "cfo")
        capex = _val(row, "capex")
        if cfo is not None and capex is not None:
            r["fcf"]        = cfo - capex
            r["fcf_source"] = "cfo_minus_capex"
        elif cfo is not None:
            r["fcf"]        = None
            r["fcf_source"] = "missing_capex"
        else:
            r["fcf"]        = None
            r["fcf_source"] = "missing_cfo"

        # ── debt_total (non-financial only) ──────────────────────────────
        if industry == "non_financial":
            st = _val(row, "debt_short_term")
            lt = _val(row, "debt_long_term")
            bw = _val(row, "borrowings")

            if st is not None and lt is not None:
                r["debt_total"]        = st + lt
                r["debt_total_source"] = "short_plus_long"
            elif bw is not None:
                r["debt_total"]        = bw
                r["debt_total_source"] = "borrowings_total"
            elif st is not None:
                r["debt_total"]        = st
                r["debt_total_source"] = "short_term_only"
            elif lt is not None:
                r["debt_total"]        = lt
                r["debt_total_source"] = "long_term_only"
            else:
                r["debt_total"]        = None
                r["debt_total_source"] = "missing"

            # net_debt = debt_total - cash
            cash = _val(row, "cash")
            dt   = r.get("debt_total")
            r["net_debt"] = (dt - cash) if (dt is not None and cash is not None) else None

            # EBITDA = operating_income + D&A
            oi = _val(row, "operating_income")
            da = _val(row, "depreciation_amortization")
            r["ebitda_calc"]        = (oi + da) if (oi is not None and da is not None) else None
            r["ebitda_source"]      = "ebit_plus_da" if r["ebitda_calc"] is not None else "missing"
            r["financing_liabilities"] = None

        else:  # financial
            r["debt_total"]        = None
            r["debt_total_source"] = "not_applicable"
            r["net_debt"]          = None
            r["ebitda_calc"]       = None
            r["ebitda_source"]     = "not_applicable"

            deposits = _val(row, "deposits_from_customers")
            r["financing_liabilities"] = deposits  # None if bank doesn't publish XBRL IFRS

        rows.append(r)

    return pd.DataFrame(rows)


# ── Step 3: Quality Flags ─────────────────────────────────────────────────────

def quality_flags(norm: pd.DataFrame) -> pd.DataFrame:
    """
    Produces per-row quality assessments.
    Also computes data_completeness_pct over CRITICAL_FIELDS.
    """
    rows = []
    for _, row in norm.iterrows():
        industry = row["industry"]

        # operating_expenses_quality
        has_dist  = _val(row, "distribution_costs") is not None
        has_admin = _val(row, "administrative_expense") is not None
        has_other = _val(row, "other_expense") is not None
        if has_dist and has_admin:
            opex_q = "full"
        elif has_admin or has_dist:
            opex_q = "partial"
        else:
            opex_q = "poor"

        # debt_quality
        if industry == "financial":
            debt_q = "not_applicable"
        else:
            has_st = _val(row, "debt_short_term") is not None
            has_lt = _val(row, "debt_long_term") is not None
            has_bw = _val(row, "borrowings") is not None
            if has_st and has_lt:
                debt_q = "reliable"
            elif has_st or has_lt or has_bw:
                debt_q = "proxy"
            else:
                debt_q = "poor"

        # fcf_quality
        has_cfo   = _val(row, "cfo") is not None
        has_capex = _val(row, "capex") is not None
        if has_cfo and has_capex:
            fcf_q = "high"
        elif has_cfo:
            fcf_q = "medium"
        else:
            fcf_q = "low"

        # data_completeness_pct
        critical_present = sum(
            1 for f in CRITICAL_FIELDS
            if _val(row, f) is not None
        )
        completeness = round(critical_present / len(CRITICAL_FIELDS) * 100, 1)

        rows.append({
            "ticker":                      row["ticker"],
            "year":                        row["year"],
            "month":                       row["month"],
            "industry":                    industry,
            "operating_expenses_quality":  opex_q,
            "debt_quality":                debt_q,
            "fcf_quality":                 fcf_q,
            "has_revenue":                 _val(row, "revenue") is not None,
            "has_assets":                  _val(row, "assets") is not None,
            "has_equity":                  _val(row, "equity") is not None,
            "has_operating_cf":            has_cfo,
            "data_completeness_pct":       completeness,
        })

    return pd.DataFrame(rows)


# ── Step 4: Save ──────────────────────────────────────────────────────────────

def save_to_sqlite(tables: dict[str, pd.DataFrame], db_path: str) -> None:
    con = sqlite3.connect(db_path)
    for name, df in tables.items():
        df.to_sql(name, con, if_exists="replace", index=False)
    con.close()


def save_to_csv(tables: dict[str, pd.DataFrame], out_dir: str) -> None:
    for name, df in tables.items():
        path = os.path.join(out_dir, f"{name}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  CSV: {path}")


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(norm: pd.DataFrame, derived: pd.DataFrame, flags: pd.DataFrame) -> None:
    print(f"\n{'='*60}")
    print(f"normalized_financials : {len(norm):,} rows | "
          f"{norm['ticker'].nunique()} tickers | "
          f"años {sorted(norm['year'].unique())}")

    print(f"\nIndustry split:")
    for ind, grp in norm.groupby("industry"):
        print(f"  {ind:20s} {len(grp):>4} rows | {grp['ticker'].nunique()} tickers")

    print(f"\nderived_metrics       : {len(derived):,} rows")
    for col in ("fcf", "net_debt", "ebitda_calc"):
        if col in derived.columns:
            pct = derived[col].notna().mean() * 100
            print(f"  {col:<22} {pct:5.1f}% coverage")

    print(f"\nquality_flags         : {len(flags):,} rows")
    for col in ("operating_expenses_quality", "debt_quality", "fcf_quality"):
        if col in flags.columns:
            dist = flags[col].value_counts().to_dict()
            print(f"  {col}:")
            for k, v in sorted(dist.items()):
                print(f"    {k:<20} {v:>4}")

    print(f"\nData completeness (critical fields, % of rows with value):")
    for f in CRITICAL_FIELDS:
        col = FIELD_RENAME.get(f, f)
        if col in norm.columns:
            pct = norm[col].notna().mean() * 100
            bar = "#" * int(pct / 5)
            print(f"  {col:<25} {pct:5.1f}%  {bar}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="CMF XBRL → Financial Data Warehouse")
    ap.add_argument("--input",    default=FACTS_CSV,    help="facts_raw.csv path")
    ap.add_argument("--map",      default=CONCEPT_MAP,  help="concept_map.yaml path")
    ap.add_argument("--tickers",  default=TICKERS_JSON, help="tickers_chile.json path")
    ap.add_argument("--db",       default=DB_PATH,      help="SQLite output path")
    ap.add_argument("--no-csv",   action="store_true",  help="Skip CSV output")
    args = ap.parse_args()

    print("Loading concept map...")
    concept_map = load_concept_map(args.map)
    print(f"  {len(concept_map)} fields defined")

    print("Loading industry classification...")
    industry_map = build_industry_map(args.tickers)
    print(f"  {sum(v == 'financial' for v in industry_map.values())} financial tickers")

    print(f"Loading facts: {args.input}")
    facts = load_facts(args.input)
    print(f"  {len(facts):,} rows | {facts['ticker'].nunique()} tickers")

    print("\nStep 1: Normalizing...")
    norm = normalize(facts, concept_map, industry_map)

    print("Step 2: Deriving metrics...")
    derived = derive_metrics(norm)

    print("Step 3: Quality flags...")
    flags = quality_flags(norm)

    print("\nStep 4: Saving...")
    os.makedirs(OUT_DIR, exist_ok=True)

    tables = {
        "normalized_financials": norm,
        "derived_metrics":       derived,
        "quality_flags":         flags,
    }
    save_to_sqlite(tables, args.db)
    print(f"  SQLite: {args.db}")

    if not args.no_csv:
        save_to_csv(tables, OUT_DIR)

    print_summary(norm, derived, flags)


if __name__ == "__main__":
    main()
