import time
import requests
from scraper.logger import logger

BASE_URL = "https://www.cmfchile.cl"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
DELAY_SECONDS = 0.75

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

COMPANY_LIST_URL = (
    f"{BASE_URL}/institucional/mercados/consulta.php"
    "?mercado=V&Estado=VI&entidad=RVEMI"
)

DETAIL_URL_TEMPLATE = (
    f"{BASE_URL}/institucional/mercados/entidad.php"
    "?mercado=V&rut={rut}&tipoentidad=RVEMI&vig=VI"
    "&mm={month:02d}&aa={year}&tipo=C"
    "&control=svs&tipo_norma=IFRS&pestania=3"
)


def _get_with_retry(url: str, context: str) -> requests.Response | None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = SESSION.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            time.sleep(DELAY_SECONDS)
            return response
        except requests.RequestException as exc:
            logger.warning(f"{context} | intento {attempt}/{MAX_RETRIES} | {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(DELAY_SECONDS * attempt * 2)
    return None


def get_company_list() -> str | None:
    """Fetches the full list of RVEMI entities from CMF."""
    logger.info(f"Fetching company list | {COMPANY_LIST_URL}")
    response = _get_with_retry(COMPANY_LIST_URL, "company-list")
    if response is None:
        logger.error("COMPANY_LIST_ERROR | Failed to fetch company list")
        return None
    return response.text


def get_company_period(rut: str, year: int, month: int) -> str | None:
    """
    Fetches the financial statements page (pestania=3) for a company
    for a specific year/month period.
    """
    url = DETAIL_URL_TEMPLATE.format(rut=rut, month=month, year=year)
    period = f"{year}-{month:02d}"
    response = _get_with_retry(url, f"{period} | RUT:{rut}")
    if response is None:
        logger.error(f"{period} | RUT:{rut} | DETAIL_ERROR | {url}")
        return None
    return response.text


def download_file(url: str, period: str, rut: str) -> bytes | None:
    """Downloads a file (XBRL ZIP) from the given URL."""
    if url.startswith("/"):
        url = BASE_URL + url
    elif not url.startswith("http"):
        url = BASE_URL + "/" + url

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = SESSION.get(url, timeout=REQUEST_TIMEOUT, stream=True)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if not any(t in content_type.lower() for t in
                       ["zip", "octet-stream", "application", "x-zip", "xbrl"]):
                logger.warning(
                    f"{period} | RUT:{rut} | Unexpected Content-Type: {content_type}"
                )

            data = response.content
            time.sleep(DELAY_SECONDS)
            return data
        except requests.RequestException as exc:
            logger.warning(
                f"{period} | RUT:{rut} | DOWNLOAD_ERROR | intento {attempt}/{MAX_RETRIES} | {exc}"
            )
            if attempt < MAX_RETRIES:
                time.sleep(DELAY_SECONDS * attempt * 2)

    logger.error(f"{period} | RUT:{rut} | DOWNLOAD_ERROR | intento {MAX_RETRIES}/{MAX_RETRIES}")
    return None
