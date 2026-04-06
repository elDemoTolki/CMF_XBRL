"""
validate.py — Cross-validation against external sources (Yahoo Finance / StockAnalysis)
========================================================================================
Genera un reporte de validación para 10 tickers seleccionados, 2020-2025.

Modo 1 (default) — genera tabla de nuestros datos lista para comparar manualmente:
  python validate.py

Modo 2 — intenta fetch desde Yahoo Finance (requiere acceso de red):
  python validate.py --yfinance

Modo 3 — genera solo Excel para comparación manual:
  python validate.py --format excel

Métricas validadas:
  revenue, net_income, assets, equity, cfo
  ebitda_calc, debt_total, net_debt, capex

Tolerancias aceptables:
  < 1%   → Match perfecto (diferencia de redondeo)
  1-5%   → Match bueno (diferencias de restatements menores)
  5-15%  → Revisar (puede ser diferencia de metodología, moneda o período)
  > 15%  → Alerta (probable error de parsing, escala o concepto equivocado)
"""

import argparse
import os
import sqlite3
import warnings
from typing import Optional

import pandas as pd

DB_PATH  = os.path.join("output", "warehouse.db")
OUT_DIR  = "output"
YEARS    = [2020, 2021, 2022, 2023, 2024, 2025]

# 10 tickers seleccionados: diversidad de sector, tamaño y complejidad contable
SAMPLE_TICKERS = [
    "FALABELLA.SN",   # Retail — grande, complejo, muy seguido
    "CENCOSUD.SN",    # Retail — comparable a Falabella
    "COPEC.SN",       # Energía/forestal — holding complejo
    "SQM-A.SN",       # Minería — litio, reporta en USD internamente
    "ENTEL.SN",       # Telecomunicaciones — relativamente simple
    "CMPC.SN",        # Forestal/papel — exporter con ingresos mixtos
    "COLBUN.SN",      # Energía — utility regulada, estable
    "AGUAS-A.SN",     # Utilities — muy predecible, buen sanity check
    "LTM.SN",         # Aerolínea — alta volatilidad post-COVID, caso interesante
    "CAP.SN",         # Minería hierro — commodity cíclico
]

# Métricas a validar + su nombre en el warehouse
METRICS = {
    "revenue":      ("Revenue / Ingresos",          "B CLP"),
    "net_income":   ("Net Income / Utilidad Neta",  "B CLP"),
    "assets":       ("Total Assets / Activos",      "B CLP"),
    "equity":       ("Equity / Patrimonio",         "B CLP"),
    "cfo":          ("Operating CF (CFO)",          "B CLP"),
    "ebitda_calc":  ("EBITDA (calculado)",          "B CLP"),
    "debt_total":   ("Deuda Total",                 "B CLP"),
    "capex":        ("CAPEX (positivo)",            "B CLP"),
}

# yfinance field mapping (label in Yahoo Finance financials/balance_sheet/cashflow)
YF_MAP = {
    "revenue":    ("financials",    "Total Revenue"),
    "net_income": ("financials",    "Net Income"),
    "assets":     ("balance_sheet", "Total Assets"),
    "equity":     ("balance_sheet", "Stockholders Equity"),
    "cfo":        ("cashflow",      "Operating Cash Flow"),
    "capex":      ("cashflow",      "Capital Expenditure"),
}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_warehouse(tickers: list[str], years: list[int]) -> pd.DataFrame:
    """Loads and joins normalized_financials + derived_metrics for sample."""
    placeholders = ",".join("?" * len(tickers))
    con = sqlite3.connect(DB_PATH)
    norm = pd.read_sql(
        f"SELECT *, reporting_currency FROM normalized_financials WHERE ticker IN ({placeholders})",
        con, params=tickers
    )
    derived = pd.read_sql(
        f"SELECT ticker, year, month, fcf, debt_total, net_debt, ebitda_calc "
        f"FROM derived_metrics WHERE ticker IN ({placeholders})",
        con, params=tickers
    )
    con.close()

    keys = ["ticker", "year", "month"]
    df = norm.merge(derived, on=keys, how="left")
    return df[df["year"].isin(years)].copy()


# ── yfinance fetch (optional) ─────────────────────────────────────────────────

def fetch_yfinance(ticker: str) -> Optional[dict]:
    """
    Returns {metric: {year: value}} dict from Yahoo Finance.
    Returns None on error/timeout.
    """
    try:
        import yfinance as yf
        warnings.filterwarnings("ignore")
        t = yf.Ticker(ticker)

        result: dict[str, dict] = {m: {} for m in YF_MAP}

        sources = {
            "financials":    t.financials,
            "balance_sheet": t.balance_sheet,
            "cashflow":      t.cashflow,
        }

        for metric, (src_key, label) in YF_MAP.items():
            df = sources[src_key]
            if df is None or df.empty or label not in df.index:
                continue
            row = df.loc[label]
            for col in row.index:
                try:
                    year = pd.Timestamp(col).year
                    val  = float(row[col])
                    if not pd.isna(val):
                        result[metric][year] = val
                except Exception:
                    continue

        return result

    except Exception as e:
        return None


# ── Comparison table ──────────────────────────────────────────────────────────

def build_comparison(
    warehouse: pd.DataFrame,
    yf_data: Optional[dict[str, dict]],
    ticker: str,
) -> pd.DataFrame:
    """
    Builds a long-format comparison table for one ticker.
    Columns: ticker, year, metric, our_value_B, yf_value_B, diff_pct, status
    """
    rows = []
    our = warehouse[warehouse["ticker"] == ticker].set_index("year")

    # Detect reporting currency for this ticker (use most recent year)
    currency = "CLP"
    if "reporting_currency" in our.columns and not our.empty:
        currency = our["reporting_currency"].dropna().iloc[-1] if not our["reporting_currency"].dropna().empty else "CLP"

    for metric, (label, _unit) in METRICS.items():
        unit = f"B {currency}"
        for year in YEARS:
            if year not in our.index:
                continue

            our_val_raw = our.loc[year, metric] if metric in our.columns else None
            our_val = (float(our_val_raw) / 1e9) if (
                our_val_raw is not None and pd.notna(our_val_raw)
            ) else None

            yf_val = None
            if yf_data and metric in yf_data and year in yf_data[metric]:
                yf_val = yf_data[metric][year] / 1e9  # also convert to B

            # Compute difference
            diff_pct = None
            status   = "no_external"
            if our_val is not None and yf_val is not None:
                if abs(yf_val) > 0.001:
                    diff_pct = abs(our_val - yf_val) / abs(yf_val) * 100
                    if diff_pct < 1:
                        status = "match"
                    elif diff_pct < 5:
                        status = "good"
                    elif diff_pct < 15:
                        status = "review"
                    else:
                        status = "ALERT"
                else:
                    status = "yf_zero"
            elif our_val is None:
                status = "missing_ours"
            elif yf_val is None:
                status = "no_external"

            rows.append({
                "ticker":       ticker,
                "year":         year,
                "metric":       metric,
                "label":        label,
                "our_B_CLP":    round(our_val, 2) if our_val is not None else None,
                "yf_B_CLP":     round(yf_val, 2)  if yf_val  is not None else None,
                "diff_pct":     round(diff_pct, 1) if diff_pct is not None else None,
                "status":       status,
            })

    return pd.DataFrame(rows)


# ── Console report ────────────────────────────────────────────────────────────

def print_ticker_report(df_ticker: pd.DataFrame, ticker: str, has_yf: bool) -> None:
    print(f"\n{'='*72}")
    print(f"  {ticker}")
    if not has_yf:
        print(f"  (sin datos externos — solo nuestros valores)")
    print(f"{'='*72}")

    for metric, (label, unit) in METRICS.items():
        sub = df_ticker[df_ticker["metric"] == metric].set_index("year")
        if sub.empty:
            continue

        # Header
        print(f"\n  {label} ({unit})")
        header = f"  {'Año':<6}"
        for y in YEARS:
            header += f"  {y:>10}"
        print(header)
        print("  " + "-" * (6 + 12 * len(YEARS)))

        # Our values
        line = f"  {'Nuestro':<6}"
        for y in YEARS:
            if y in sub.index and sub.loc[y, "our_B_CLP"] is not None:
                line += f"  {sub.loc[y, 'our_B_CLP']:>10.1f}"
            else:
                line += f"  {'—':>10}"
        print(line)

        # YF values (if available)
        if has_yf:
            line = f"  {'YF':>6}"
            for y in YEARS:
                if y in sub.index and sub.loc[y, "yf_B_CLP"] is not None:
                    line += f"  {sub.loc[y, 'yf_B_CLP']:>10.1f}"
                else:
                    line += f"  {'—':>10}"
            print(line)

            # Diff %
            line = f"  {'Diff%':>6}"
            for y in YEARS:
                if y in sub.index and sub.loc[y, "diff_pct"] is not None:
                    d = sub.loc[y, "diff_pct"]
                    flag = " !" if sub.loc[y, "status"] == "ALERT" else (
                           " ?" if sub.loc[y, "status"] == "review" else "  ")
                    line += f"  {d:>8.1f}%{flag}"
                else:
                    line += f"  {'—':>10}"
            print(line)


# ── Excel export ──────────────────────────────────────────────────────────────

def export_excel(all_comparisons: pd.DataFrame, warehouse: pd.DataFrame) -> str:
    """
    Exports a multi-sheet Excel:
      - Summary: pivot of our values, all tickers × years
      - Comparison: full diff table (when yfinance data available)
      - [one sheet per ticker]: detailed wide view
    """
    path = os.path.join(OUT_DIR, "validation_report.xlsx")
    os.makedirs(OUT_DIR, exist_ok=True)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:

        # Sheet 1: Summary pivot (revenue, net_income, assets, equity)
        for metric in ("revenue", "net_income", "assets", "equity", "cfo"):
            pivot = (
                warehouse[warehouse["year"].isin(YEARS)]
                [["ticker", "year", metric]]
                .pivot(index="ticker", columns="year", values=metric)
                .div(1e9)
                .round(1)
            )
            pivot.to_excel(writer, sheet_name=metric[:20])

        # Sheet: full comparison table
        if not all_comparisons.empty:
            all_comparisons.to_excel(writer, sheet_name="full_comparison", index=False)

        # Auto-width helper
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = max(
                    (len(str(cell.value or "")) for cell in col), default=8
                ) + 2
                ws.column_dimensions[col[0].column_letter].width = min(max_len, 25)

    return path


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Validacion datos XBRL vs fuentes externas")
    ap.add_argument("--tickers",   default=",".join(SAMPLE_TICKERS),
                    help="Tickers separados por coma")
    ap.add_argument("--years",     default="2020,2021,2022,2023,2024,2025",
                    help="Anos separados por coma")
    ap.add_argument("--yfinance",  action="store_true",
                    help="Intentar fetch desde Yahoo Finance")
    ap.add_argument("--format",    default="console",
                    choices=["console", "excel", "both"])
    ap.add_argument("--db",        default=DB_PATH)
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")]
    years   = [int(y) for y in args.years.split(",")]

    print(f"Cargando warehouse: {len(tickers)} tickers | anos {years}")
    warehouse = load_warehouse(tickers, years)

    # Filter to tickers actually in DB
    available = warehouse["ticker"].unique().tolist()
    missing   = [t for t in tickers if t not in available]
    if missing:
        print(f"  Advertencia: no encontrados en DB: {missing}")
    tickers = available

    print(f"  {len(warehouse)} filas cargadas\n")

    all_comparisons = []

    for ticker in tickers:
        yf_data = None
        if args.yfinance:
            print(f"  Fetching Yahoo Finance: {ticker} ...", end=" ", flush=True)
            yf_data = fetch_yfinance(ticker)
            if yf_data:
                print("OK")
            else:
                print("TIMEOUT/ERROR — usando solo nuestros datos")

        comp = build_comparison(warehouse, yf_data, ticker)
        all_comparisons.append(comp)

        if args.format in ("console", "both"):
            print_ticker_report(comp, ticker, yf_data is not None)

    full_comp = pd.concat(all_comparisons, ignore_index=True) if all_comparisons else pd.DataFrame()

    if args.format in ("excel", "both"):
        path = export_excel(full_comp, warehouse)
        print(f"\nExcel guardado: {path}")
        print("  Hojas: revenue, net_income, assets, equity, cfo, full_comparison")

    # Summary stats (when yfinance data available)
    has_diff = full_comp[full_comp["diff_pct"].notna()]
    if not has_diff.empty:
        print(f"\n{'='*50}")
        print(f"RESUMEN VALIDACION ({len(has_diff)} comparaciones con datos externos)")
        dist = has_diff["status"].value_counts()
        for s in ("match", "good", "review", "ALERT"):
            n = dist.get(s, 0)
            pct = n / len(has_diff) * 100
            print(f"  {s:<15} {n:>4}  ({pct:5.1f}%)")
    else:
        print(f"\n{'='*50}")
        print("Datos externos no disponibles.")
        print("Para validar manualmente, abre validation_report.xlsx")
        print("y compara contra:")
        print("  Yahoo Finance: https://finance.yahoo.com/quote/FALABELLA.SN/financials/")
        print("  StockAnalysis: https://stockanalysis.com/stocks/cl/falabella/financials/")
        print()
        print("Metricas clave a verificar (en B CLP):")
        pivot = (
            warehouse[warehouse["ticker"].isin(SAMPLE_TICKERS[:5])]
            [["ticker","year","revenue","net_income","assets","equity"]]
            .assign(
                revenue    = lambda d: (d["revenue"]     / 1e9).round(1),
                net_income = lambda d: (d["net_income"]  / 1e9).round(1),
                assets     = lambda d: (d["assets"]      / 1e9).round(1),
                equity     = lambda d: (d["equity"]      / 1e9).round(1),
            )
            .sort_values(["ticker","year"])
        )
        print(pivot.to_string(index=False))


if __name__ == "__main__":
    main()
