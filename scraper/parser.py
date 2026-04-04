import re
import hashlib
from bs4 import BeautifulSoup
from scraper.logger import logger

BASE_URL = "https://www.cmfchile.cl"


def extract_companies(html: str) -> list[dict]:
    """
    Parses the RVEMI company list page and returns:
    [{"rut": "96874030", "nombre": "ABC S.A."}, ...]
    RUT is returned without dígito verificador.
    """
    companies = []
    try:
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("table tr")

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            rut_text = cells[0].get_text(strip=True)
            nombre_text = cells[1].get_text(strip=True)

            rut_clean = _clean_rut(rut_text)
            if not rut_clean:
                continue

            companies.append({"rut": rut_clean, "nombre": nombre_text})

    except Exception as exc:
        logger.warning(f"PARSE_WARNING | extract_companies | {exc}")

    logger.info(f"Parsed {len(companies)} companies from listing")
    return companies


def _clean_rut(rut_text: str) -> str | None:
    """Strips dots and dígito verificador from a RUT string."""
    rut_text = rut_text.replace(".", "").strip()
    match = re.match(r"^(\d{7,8})", rut_text)
    return match.group(1) if match else None


def find_xbrl_url(html: str, period: str, rut: str) -> str | None:
    """
    Searches the company detail page for an XBRL download link.
    Looks for links to safec_ifrs_verarchivo.php (the CMF XBRL download endpoint).
    Falls back to any link containing xbrl, .zip, descargar, or download.
    Returns absolute URL or None.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        all_links = soup.find_all("a", href=True)

        # Priority 1: link whose TEXT explicitly says "xbrl" (e.g. "Estados financieros (XBRL)")
        # Priority 2: href contains "xbrl" and is not a safec endpoint (unlikely but possible)
        # Priority 3: href contains ".zip"
        # Priority 4: text says "descargar"/"download" and is a safec endpoint
        candidates = {"text_xbrl": [], "href_xbrl": [], "zip": [], "descargar": []}

        for a in all_links:
            href = a["href"]
            href_lower = href.lower()
            text_lower = a.get_text(strip=True).lower()

            if "xbrl" in text_lower:
                candidates["text_xbrl"].append(href)
            elif "xbrl" in href_lower:
                candidates["href_xbrl"].append(href)
            elif ".zip" in href_lower:
                candidates["zip"].append(href)
            elif "descargar" in text_lower or "download" in text_lower:
                candidates["descargar"].append(href)

        for priority in ["text_xbrl", "href_xbrl", "zip", "descargar"]:
            if candidates[priority]:
                url = candidates[priority][0]
                return _make_absolute(url)

    except Exception as exc:
        logger.warning(f"{period} | RUT:{rut} | PARSE_WARNING | find_xbrl_url | {exc}")

    return None


def _make_absolute(url: str) -> str:
    from urllib.parse import urljoin, urlparse
    import posixpath
    if url.startswith("http"):
        parsed = urlparse(url)
        clean_path = posixpath.normpath(parsed.path)
        return parsed._replace(path=clean_path).geturl()
    if url.startswith("/"):
        return BASE_URL + url
    # relative to the detail page directory
    base = f"{BASE_URL}/institucional/mercados/entidad.php"
    absolute = urljoin(base, url)
    parsed = urlparse(absolute)
    clean_path = posixpath.normpath(parsed.path)
    return parsed._replace(path=clean_path).geturl()


def extract_filing_id(url: str) -> str:
    """Tries to extract a filing ID from the URL; falls back to md5 hash."""
    patterns = [
        re.compile(r"[?&]auth=([A-Za-z0-9%+/=_\-]{6,20})"),
        re.compile(r"/([A-Za-z0-9_\-]{6,})(?:\.zip)?$"),
    ]
    for pattern in patterns:
        match = pattern.search(url)
        if match:
            candidate = match.group(1)
            if len(candidate) <= 32:
                return re.sub(r"[^A-Za-z0-9_\-]", "", candidate)[:20]
    return hashlib.md5(url.encode()).hexdigest()[:12]
