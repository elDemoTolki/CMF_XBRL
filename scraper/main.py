import argparse
import json
import os
from scraper import fetcher, parser, downloader
from scraper.company_index import build_index, folder_name
from scraper.logger import logger

ANNUAL_MONTH = [12]
QUARTERLY_MONTHS = [3, 6, 9, 12]

TICKERS_FILE = "tickers_chile.json"


def load_ticker_ruts() -> set[str]:
    """Returns the set of RUTs from tickers_chile.json (excluding nulls)."""
    if not os.path.exists(TICKERS_FILE):
        logger.warning(f"{TICKERS_FILE} not found — running full universe")
        return set()
    with open(TICKERS_FILE, encoding="utf-8") as f:
        tickers = json.load(f)
    ruts = {t["rut"] for t in tickers if t.get("rut")}
    logger.info(f"Ticker universe: {len(ruts)} RUTs from {TICKERS_FILE}")
    return ruts


def run(year_start: int, year_end: int, month_only: int | None = None,
        all_months: bool = False, tickers_only: bool = False,
        quarterly: bool = False):

    # Step 1: Get full company list and build RUT→name/ticker index
    html_list = fetcher.get_company_list()
    if html_list is None:
        logger.error("Cannot proceed without company list. Exiting.")
        return

    companies = parser.extract_companies(html_list)
    if not companies:
        logger.error("No companies parsed from listing. Exiting.")
        return

    index = build_index(companies)

    # Step 1b: Filter to ticker universe if requested
    if tickers_only:
        ticker_ruts = load_ticker_ruts()
        # Also add any ticker RUTs not in the CMF RVEMI list (e.g. banks)
        # by injecting synthetic company entries
        cmf_ruts = {c["rut"] for c in companies}
        with open(TICKERS_FILE, encoding="utf-8") as f:
            all_tickers = json.load(f)
        for t in all_tickers:
            rut = t.get("rut")
            if rut and rut not in cmf_ruts:
                companies.append({"rut": rut, "nombre": t["name"]})
                index[rut] = {
                    "nombre": t["name"],
                    "slug": rut,
                    "ticker": t["ticker"],
                }
        companies = [c for c in companies if c["rut"] in ticker_ruts]
        logger.info(f"Filtered to {len(companies)} companies (tickers-only mode)")
    else:
        logger.info(f"Total companies: {len(companies)} | Index saved to data/index.json")

    # Step 2: Iterate periods
    # audit_missed: {period: [{"rut", "nombre", "razon"}]}
    audit_missed: dict[str, list[dict]] = {}

    for year in range(year_start, year_end + 1):
        if month_only:
            months = [month_only]
        elif all_months:
            months = list(range(1, 13))
        elif quarterly:
            months = QUARTERLY_MONTHS
        else:
            months = ANNUAL_MONTH  # default: solo diciembre

        for month in months:
            period = f"{year}-{month:02d}"
            downloaded = 0
            no_xbrl = 0
            errors = 0
            missed = []

            logger.info(f"=== {period} | Processing {len(companies)} companies ===")

            for company in companies:
                rut = company["rut"]
                nombre = company["nombre"]
                fname = folder_name(rut, index)

                html_detail = fetcher.get_company_period(rut, year, month)
                if html_detail is None:
                    errors += 1
                    missed.append({"rut": rut, "nombre": nombre, "razon": "DETAIL_ERROR"})
                    continue

                xbrl_url = parser.find_xbrl_url(html_detail, period, rut)
                if xbrl_url is None:
                    logger.debug(f"{period} | RUT:{rut} | NO_XBRL | {nombre}")
                    no_xbrl += 1
                    missed.append({"rut": rut, "nombre": nombre, "razon": "NO_XBRL"})
                    continue

                logger.info(f"{period} | RUT:{rut} | {nombre} | Found XBRL")

                content = fetcher.download_file(xbrl_url, period, rut)
                if content is None:
                    errors += 1
                    missed.append({"rut": rut, "nombre": nombre, "razon": "DOWNLOAD_ERROR"})
                    continue

                saved = downloader.save(content, rut, year, month, fname)
                if saved:
                    downloaded += 1
                else:
                    errors += 1
                    missed.append({"rut": rut, "nombre": nombre, "razon": "SAVE_ERROR"})

            if missed:
                audit_missed[period] = missed

            logger.info(
                f"=== {period} | Descargados: {downloaded} | "
                f"Sin XBRL: {no_xbrl} | Errores: {errors} ==="
            )

    # Final audit summary
    if audit_missed:
        logger.info("=" * 60)
        logger.info("AUDITORIA — Periodos con empresas sin descarga:")
        for period, entries in audit_missed.items():
            by_reason: dict[str, list[str]] = {}
            for e in entries:
                by_reason.setdefault(e["razon"], []).append(e["nombre"])
            for razon, nombres in by_reason.items():
                logger.info(f"  {period} | {razon} ({len(nombres)}): {', '.join(nombres)}")
        logger.info("=" * 60)
    else:
        logger.info("AUDITORIA — Sin ausencias: todos los archivos descargados.")


def main():
    ap = argparse.ArgumentParser(description="CMF XBRL Scraper")
    ap.add_argument("--year", type=int, required=True, help="Año de inicio")
    ap.add_argument("--year-end", type=int, default=None,
                    help="Año de fin (inclusive). Por defecto igual a --year")
    ap.add_argument("--month", type=int, default=None,
                    choices=range(1, 13), metavar="[1-12]",
                    help="Mes específico (opcional)")
    ap.add_argument("--quarterly", action="store_true",
                    help="Descargar los 4 trimestres (mar, jun, sep, dic)")
    ap.add_argument("--all-months", action="store_true",
                    help="Procesar los 12 meses")
    ap.add_argument("--tickers-only", action="store_true",
                    help=f"Solo empresas definidas en {TICKERS_FILE}")
    args = ap.parse_args()

    year_end = args.year_end if args.year_end else args.year
    run(args.year, year_end, args.month, args.all_months, args.tickers_only, args.quarterly)


if __name__ == "__main__":
    main()
