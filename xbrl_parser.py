"""
xbrl_parser.py — Extrae todos los facts de estados financieros XBRL (CMF Chile).

Genera:
  output/facts_raw.csv      — todos los facts de todos los tickers/años
  output/facts_raw.xlsx     — misma data, más fácil de explorar

Uso:
  python xbrl_parser.py                          # todos los ZIPs en data/
  python xbrl_parser.py --ticker FALABELLA_SN    # solo un ticker
  python xbrl_parser.py --year 2023              # solo un año
"""

import argparse
import json
import os
import zipfile
from datetime import datetime, timedelta

import pandas as pd
from lxml import etree

NS_XBRLI = "http://www.xbrl.org/2003/instance"
DATA_DIR  = "data"
OUT_DIR   = "output"

# Tolerance (days) when matching a context date to the expected year-end date.
# Covers fiscal years that close on Dec 28–31 or Jan 1–2.
DATE_TOLERANCE_DAYS = 20

# Known named context IDs → role (fallback for companies that still use names)
NAMED_CONTEXT_ROLE = {
    "CierreTrimestreActual":    "balance_current",
    "SaldoActualInicio":        "balance_prev_year_end",
    "TrimestreAcumuladoActual": "period_current",
    "AnualAnterior":            "period_prev_year",
}


def _last_day(year: int, month: int) -> int:
    """Returns the last calendar day of the given month."""
    if month == 12:
        return 31
    return (datetime(year, month + 1, 1) - timedelta(days=1)).day


def _build_context_map(root, year: int, month: int) -> dict[str, dict]:
    """
    Returns {context_id: {type, date, start, role}} for simple (non-dimensional) contexts.

    Role assignment uses two strategies in order:
      1. Named context IDs (NAMED_CONTEXT_ROLE dict) — covers early XBRL files.
      2. Date analysis — covers generic IDs like p1_Instant, p2_Duration, etc.
         - instant closest to year-end          → balance_current
         - instant closest to previous year-end → balance_prev_year_end
         - full-year duration ending at year-end          → period_current
         - full-year duration ending at previous year-end → period_prev_year
    """
    # ── Step 1: parse all simple contexts ────────────────────────────────────
    raw: dict[str, dict] = {}
    for ctx in root.findall(f"{{{NS_XBRLI}}}context"):
        cid = ctx.get("id")
        if ctx.find(f"{{{NS_XBRLI}}}scenario") is not None:
            continue
        period  = ctx.find(f"{{{NS_XBRLI}}}period")
        instant = period.find(f"{{{NS_XBRLI}}}instant")
        start   = period.find(f"{{{NS_XBRLI}}}startDate")
        end     = period.find(f"{{{NS_XBRLI}}}endDate")
        try:
            if instant is not None:
                raw[cid] = {"type": "instant", "date": instant.text.strip()[:10],
                             "start": None, "role": None}
            elif start is not None and end is not None:
                raw[cid] = {"type": "duration", "date": end.text.strip()[:10],
                             "start": start.text.strip()[:10], "role": None}
        except AttributeError:
            continue

    # ── Step 2: named-ID assignment ───────────────────────────────────────────
    for cid, meta in raw.items():
        if cid in NAMED_CONTEXT_ROLE:
            meta["role"] = NAMED_CONTEXT_ROLE[cid]

    # ── Step 3: date-based assignment for contexts still without a role ───────
    year_end  = datetime(year, month, _last_day(year, month))
    prev_end  = datetime(year - 1, month, _last_day(year - 1, month))

    unresolved_instants  = [(cid, m) for cid, m in raw.items()
                            if m["type"] == "instant"  and m["role"] is None]
    unresolved_durations = [(cid, m) for cid, m in raw.items()
                            if m["type"] == "duration" and m["role"] is None]

    # Instants — pick the one closest to each target date (within tolerance)
    def _closest_instant(targets, candidates):
        """For each target, find the closest unassigned instant within tolerance."""
        assigned: dict[str, str] = {}
        remaining = list(candidates)
        for target_date, role in targets:
            best_cid, best_diff = None, DATE_TOLERANCE_DAYS + 1
            for cid, meta in remaining:
                try:
                    d = datetime.strptime(meta["date"], "%Y-%m-%d")
                    diff = abs((d - target_date).days)
                    if diff < best_diff:
                        best_diff, best_cid = diff, cid
                except ValueError:
                    continue
            if best_cid is not None:
                assigned[best_cid] = role
                remaining = [(c, m) for c, m in remaining if c != best_cid]
        return assigned

    instant_roles = _closest_instant(
        [(year_end, "balance_current"), (prev_end, "balance_prev_year_end")],
        unresolved_instants,
    )
    for cid, role in instant_roles.items():
        raw[cid]["role"] = role

    # Durations — full-year periods (300–400 days) ending closest to target dates
    def _closest_duration(targets, candidates):
        assigned: dict[str, str] = {}
        remaining = list(candidates)
        for target_date, role in targets:
            best_cid, best_diff = None, DATE_TOLERANCE_DAYS + 1
            for cid, meta in remaining:
                try:
                    d_start = datetime.strptime(meta["start"], "%Y-%m-%d")
                    d_end   = datetime.strptime(meta["date"],  "%Y-%m-%d")
                    days    = (d_end - d_start).days
                    if not (300 <= days <= 400):
                        continue
                    diff = abs((d_end - target_date).days)
                    if diff < best_diff:
                        best_diff, best_cid = diff, cid
                except ValueError:
                    continue
            if best_cid is not None:
                assigned[best_cid] = role
                remaining = [(c, m) for c, m in remaining if c != best_cid]
        return assigned

    duration_roles = _closest_duration(
        [(year_end, "period_current"), (prev_end, "period_prev_year")],
        unresolved_durations,
    )
    for cid, role in duration_roles.items():
        raw[cid]["role"] = role

    # Return only contexts that resolved to a known role
    return {cid: meta for cid, meta in raw.items() if meta["role"] is not None}


def parse_xbrl(zip_path: str, rut: str, ticker: str | None, year: int, month: int) -> list[dict]:
    """Parses one ZIP and returns a list of fact dicts."""
    rows = []
    try:
        with zipfile.ZipFile(zip_path) as z:
            xbrl_name = next(n for n in z.namelist() if n.endswith(".xbrl"))
            with z.open(xbrl_name) as f:
                raw = f.read()
            # lxml handles the encoding declaration in the XML header automatically
            try:
                tree = etree.fromstring(raw)
            except etree.XMLSyntaxError:
                parser = etree.XMLParser(recover=True)
                tree = etree.fromstring(raw, parser)

        contexts = _build_context_map(tree, year, month)
        if not contexts:
            return rows

        for elem in tree:
            tag = elem.tag
            if not isinstance(tag, str):
                continue  # skip comments / processing instructions (tag is a callable)
            if tag.startswith(f"{{{NS_XBRLI}}}"):
                continue  # skip xbrli: elements (contexts, units, etc.)

            cref = elem.get("contextRef")
            if cref not in contexts:
                continue  # dimensional context → skip

            val_raw = (elem.text or "").strip()
            if not val_raw:
                continue

            decimals = elem.get("decimals")
            unit     = elem.get("unitRef", "")

            # Parse namespace prefix and concept name
            if "}" in tag:
                ns_uri, concept = tag[1:].split("}", 1)
                prefix = "ifrs-full" if "ifrs" in ns_uri else "cl-ci"
            else:
                prefix, concept = "unknown", tag

            ctx = contexts[cref]

            # Numeric value — always use the raw reported amount.
            # The XBRL 'decimals' attribute indicates precision/rounding (e.g. -3 means
            # accurate to the nearest 1000), NOT a scale factor. All CMF XBRL files
            # report values in full CLP units regardless of the decimals attribute.
            value = None
            if unit:  # monetary / numeric facts
                try:
                    value = float(val_raw)
                except (ValueError, TypeError):
                    pass

            rows.append({
                "rut":          rut,
                "ticker":       ticker or "",
                "year":         year,
                "month":        month,
                "prefix":       prefix,
                "concept":      concept,
                "context_id":   cref,
                "context_role": ctx["role"],
                "period_type":  ctx["type"],
                "date":         ctx["date"],
                "period_start": ctx["start"],
                "unit":         unit,
                "value":        value,
                "value_raw":    val_raw,
            })

    except Exception as exc:
        print(f"  ERROR parsing {zip_path}: {exc}")

    return rows


def find_zips(data_dir: str, ticker_filter: str | None, year_filter: int | None) -> list[tuple]:
    """Yields (zip_path, rut, ticker, year, month) for all matching ZIPs."""
    index_path = os.path.join(data_dir, "index.json")
    index = {}
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            index = json.load(f)

    # Build rut→ticker from tickers_chile.json
    ticker_map = {}
    if os.path.exists("tickers_chile.json"):
        with open("tickers_chile.json", encoding="utf-8") as f:
            for t in json.load(f):
                if t.get("rut"):
                    ticker_map[t["rut"]] = t["ticker"]

    results = []
    for folder in sorted(os.listdir(data_dir)):
        if folder in ("index.json",) or not os.path.isdir(os.path.join(data_dir, folder)):
            continue
        if ticker_filter and ticker_filter.upper() not in folder.upper():
            continue

        # Extract RUT from folder name (last numeric segment)
        import re
        rut_match = re.search(r"(\d{7,8})$", folder)
        rut = rut_match.group(1) if rut_match else folder
        ticker = ticker_map.get(rut)

        folder_path = os.path.join(data_dir, folder)
        for year_dir in sorted(os.listdir(folder_path)):
            if not year_dir.isdigit():
                continue
            year = int(year_dir)
            if year_filter and year != year_filter:
                continue
            year_path = os.path.join(folder_path, year_dir)
            for month_dir in sorted(os.listdir(year_path)):
                month_path = os.path.join(year_path, month_dir)
                if not os.path.isdir(month_path):
                    continue
                for fname in os.listdir(month_path):
                    if fname.endswith(".zip"):
                        results.append((
                            os.path.join(month_path, fname),
                            rut, ticker, year, int(month_dir)
                        ))
    return results


def main():
    ap = argparse.ArgumentParser(description="CMF XBRL → CSV/Excel")
    ap.add_argument("--ticker", default=None, help="Filtrar por ticker/folder (ej: FALABELLA)")
    ap.add_argument("--year",   type=int, default=None, help="Filtrar por año")
    ap.add_argument("--no-excel", action="store_true", help="No generar .xlsx (más rápido)")
    args = ap.parse_args()

    zips = find_zips(DATA_DIR, args.ticker, args.year)
    print(f"ZIPs a procesar: {len(zips)}")

    all_rows = []
    for i, (zip_path, rut, ticker, year, month) in enumerate(zips, 1):
        label = ticker or rut
        print(f"  [{i}/{len(zips)}] {label} {year}-{month:02d} ... ", end="", flush=True)
        rows = parse_xbrl(zip_path, rut, ticker, year, month)
        print(f"{len(rows)} facts")
        all_rows.extend(rows)

    if not all_rows:
        print("No facts extracted.")
        return

    df = pd.DataFrame(all_rows)

    # Sort for readability
    df = df.sort_values(["ticker", "year", "month", "context_role", "prefix", "concept"])

    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "facts_raw.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\nCSV guardado: {csv_path}  ({len(df):,} filas, {df['concept'].nunique()} conceptos únicos)")

    if not args.no_excel:
        xlsx_path = os.path.join(OUT_DIR, "facts_raw.xlsx")
        df.to_excel(xlsx_path, index=False)
        print(f"Excel guardado: {xlsx_path}")

    # Quick summary
    print("\n=== Resumen ===")
    print(f"Tickers:   {df['ticker'].nunique()}")
    print(f"Años:      {sorted(df['year'].unique())}")
    print(f"Conceptos: {df['concept'].nunique()} únicos")
    print(f"Filas:     {len(df):,}")
    print("\nConceptos con más presencia (top 20):")
    print(df.groupby("concept")["rut"].nunique().sort_values(ascending=False).head(20).to_string())


if __name__ == "__main__":
    main()
