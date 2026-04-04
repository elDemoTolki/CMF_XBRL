"""
normalizer.py — Normaliza facts XBRL a un modelo financiero estructurado.

Lee:
  output/facts_raw.csv   — todos los facts (generado por xbrl_parser.py)
  concept_map.yaml       — mapeo de campos a conceptos XBRL

Genera:
  output/financials.csv  — tabla wide (un row por ticker/year/month)
  output/financials.db   — SQLite con tabla 'financials'

Uso:
  python normalizer.py
  python normalizer.py --no-db        # solo CSV
  python normalizer.py --input output/facts_raw.csv
"""

import argparse
import os
import sqlite3

import pandas as pd
import yaml

FACTS_CSV   = os.path.join("output", "facts_raw.csv")
OUT_CSV     = os.path.join("output", "financials.csv")
OUT_DB      = os.path.join("output", "financials.db")
CONCEPT_MAP = "concept_map.yaml"
TABLE_NAME  = "financials"


def load_concept_map(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["fields"]


def load_facts(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    # Normalise concept key: "prefix:concept"
    df["concept_key"] = df["prefix"] + ":" + df["concept"]
    return df


def normalize(facts: pd.DataFrame, concept_map: dict) -> pd.DataFrame:
    """
    For each (ticker, year, month) group, resolve each field using the
    ordered candidate list + context_role. First match wins.
    Returns a wide DataFrame.
    """
    # Index facts for fast lookup: (ticker, year, month, context_role, concept_key) → value
    # Keep one row per combination (no duplicates — take first occurrence)
    key_cols = ["ticker", "year", "month", "context_role", "concept_key"]
    facts_dedup = (
        facts.dropna(subset=["value"])
             .drop_duplicates(subset=key_cols, keep="first")
             .set_index(key_cols)["value"]
    )

    # Unique (ticker, year, month) combinations
    periods = (
        facts[["ticker", "year", "month"]]
        .drop_duplicates()
        .sort_values(["ticker", "year", "month"])
        .reset_index(drop=True)
    )

    records = []
    for _, row in periods.iterrows():
        ticker = row["ticker"]
        year   = row["year"]
        month  = row["month"]

        rec = {"ticker": ticker, "year": int(year), "month": int(month)}

        for field, spec in concept_map.items():
            ctx_role   = spec["context_role"]
            candidates = spec.get("candidates", [])
            negate     = spec.get("negate", False)

            val = None
            for ckey in candidates:
                try:
                    val = facts_dedup.loc[(ticker, year, month, ctx_role, ckey)]
                    if pd.notna(val):
                        break
                    val = None
                except KeyError:
                    continue

            if val is not None and negate:
                val = -val

            rec[field] = val

        # ── Derived fields ────────────────────────────────────────────────────

        # debt_total: prefer sum of short + long; fallback to total borrowings
        st = rec.get("short_term_borrowings")
        lt = rec.get("long_term_borrowings")
        bw = rec.get("borrowings")
        if st is not None and lt is not None:
            rec["debt_total"] = st + lt
        elif st is not None and lt is None and bw is not None:
            rec["debt_total"] = bw  # can't split → use total
        elif lt is not None and st is None and bw is not None:
            rec["debt_total"] = bw
        elif bw is not None:
            rec["debt_total"] = bw
        elif st is not None:
            rec["debt_total"] = st  # only short-term available
        elif lt is not None:
            rec["debt_total"] = lt  # only long-term available
        else:
            rec["debt_total"] = None

        # net_debt = debt_total - cash
        cash = rec.get("cash")
        dt   = rec.get("debt_total")
        rec["net_debt"] = (dt - cash) if (dt is not None and cash is not None) else None

        # fcf = operating_cf - capex  (capex already positive after negate)
        ocf   = rec.get("operating_cf")
        capex = rec.get("capex")
        rec["fcf"] = (ocf - capex) if (ocf is not None and capex is not None) else None

        # ebitda: operating_income + depreciation_amortization
        oi  = rec.get("operating_income")
        da  = rec.get("depreciation_amortization")
        rec["ebitda"] = (oi + da) if (oi is not None and da is not None) else None

        # operating_expenses: distribution + admin + other  (best-effort, often partial)
        dc  = rec.get("distribution_costs")
        ae  = rec.get("administrative_expense")
        oe  = rec.get("other_expense")
        parts = [v for v in (dc, ae, oe) if v is not None]
        rec["operating_expenses"] = sum(parts) if parts else None

        records.append(rec)

    return pd.DataFrame(records)


def save_sqlite(df: pd.DataFrame, db_path: str, table: str):
    con = sqlite3.connect(db_path)
    df.to_sql(table, con, if_exists="replace", index=False)
    con.close()


def main():
    ap = argparse.ArgumentParser(description="Normaliza facts XBRL → tabla financiera")
    ap.add_argument("--input",   default=FACTS_CSV, help="CSV de facts raw")
    ap.add_argument("--map",     default=CONCEPT_MAP, help="Archivo concept_map.yaml")
    ap.add_argument("--out-csv", default=OUT_CSV, help="CSV de salida")
    ap.add_argument("--out-db",  default=OUT_DB,  help="SQLite de salida")
    ap.add_argument("--no-db",   action="store_true", help="No generar SQLite")
    args = ap.parse_args()

    print(f"Cargando concept map: {args.map}")
    concept_map = load_concept_map(args.map)
    print(f"  {len(concept_map)} campos definidos")

    print(f"Cargando facts: {args.input}")
    facts = load_facts(args.input)
    print(f"  {len(facts):,} filas | {facts['ticker'].nunique()} tickers | "
          f"años {sorted(facts['year'].unique())}")

    print("Normalizando...")
    df = normalize(facts, concept_map)
    print(f"  {len(df):,} periodos | {df['ticker'].nunique()} tickers")

    os.makedirs("output", exist_ok=True)

    df.to_csv(args.out_csv, index=False, encoding="utf-8-sig")
    print(f"CSV guardado: {args.out_csv}")

    if not args.no_db:
        save_sqlite(df, args.out_db, TABLE_NAME)
        print(f"SQLite guardado: {args.out_db}  (tabla '{TABLE_NAME}')")

    # Coverage summary
    print("\n=== Cobertura por campo (% periodos con valor) ===")
    total = len(df)
    field_cols = [c for c in df.columns if c not in ("ticker", "year", "month")]
    coverage = (df[field_cols].notna().sum() / total * 100).sort_values(ascending=False)
    for field, pct in coverage.items():
        bar = "#" * int(pct / 5)
        print(f"  {field:<30} {pct:5.1f}%  {bar}")


if __name__ == "__main__":
    main()
