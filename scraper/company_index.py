"""
Builds and persists the RUT → {nombre, slug, ticker} index.
Crosses the CMF company list with tickers_chile.json (by RUT field).
"""
import json
import os
import re

TICKERS_FILE = "tickers_chile.json"
INDEX_FILE = os.path.join("data", "index.json")


def _slugify(name: str) -> str:
    """Converts a company name to a safe filesystem slug (max 40 chars)."""
    name = name.upper()
    replacements = {
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U", "Ñ": "N",
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
    }
    for accented, plain in replacements.items():
        name = name.replace(accented, plain)
    name = re.sub(r"[^A-Z0-9]+", "_", name)
    name = name.strip("_")
    return name[:40]


def _load_ticker_map() -> dict[str, str]:
    """Returns {rut_digits: ticker} from tickers_chile.json for entries that have 'rut'."""
    if not os.path.exists(TICKERS_FILE):
        return {}
    with open(TICKERS_FILE, encoding="utf-8") as f:
        tickers = json.load(f)
    result = {}
    for entry in tickers:
        rut = entry.get("rut")
        ticker = entry.get("ticker")
        if rut and ticker:
            # normalize: strip dígito verificador if present
            rut_digits = re.match(r"(\d+)", str(rut).replace(".", ""))
            if rut_digits:
                result[rut_digits.group(1)] = ticker
    return result


def build_index(companies: list[dict]) -> dict[str, dict]:
    """
    Takes the list from parser.extract_companies() and returns:
    {
      "96874030": {"nombre": "ABC S.A.", "slug": "ABC_SA", "ticker": "ABC.SN"},
      ...
    }
    Saves result to data/index.json.
    """
    os.makedirs("data", exist_ok=True)
    ticker_map = _load_ticker_map()

    index = {}
    for company in companies:
        rut = company["rut"]
        nombre = company["nombre"]
        slug = _slugify(nombre)
        ticker = ticker_map.get(rut)
        index[rut] = {"nombre": nombre, "slug": slug, "ticker": ticker}

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return index


def load_index() -> dict[str, dict]:
    """Loads the persisted index, or returns empty dict if not found."""
    if not os.path.exists(INDEX_FILE):
        return {}
    with open(INDEX_FILE, encoding="utf-8") as f:
        return json.load(f)


def folder_name(rut: str, index: dict) -> str:
    """Returns the human-readable folder name for a given RUT."""
    entry = index.get(rut)
    if not entry:
        return rut
    slug = entry["slug"]
    ticker = entry.get("ticker")
    if ticker:
        # e.g. "90749000_FALABELLA_SN_FALABELLA_SA"  → too long, use ticker only as prefix
        ticker_slug = ticker.replace(".", "_").replace("-", "_")
        return f"{ticker_slug}_{rut}"
    return f"{slug}_{rut}"
