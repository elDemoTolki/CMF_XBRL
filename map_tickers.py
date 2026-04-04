"""
map_tickers.py — Mapea tickers de tickers_chile.json a RUTs del CMF.

Estrategia (en orden):
  1. RUT ya definido en tickers_chile.json ->usar directamente.
  2. Buscar nemotécnico en CMF (pestania=1) para cada RUT del listado,
     construir tabla nemo→RUT, luego cruzar con la parte del ticker antes de ".SN".
  3. Fallback: fuzzy match por nombre normalizado.

Actualiza tickers_chile.json in-place agregando "rut" donde se encontró match.
Genera rut_mapping_report.json con los resultados y los no-resueltos.
"""

import json
import re
import time
import unicodedata

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.cmfchile.cl"
COMPANY_LIST_URL = f"{BASE_URL}/institucional/mercados/consulta.php?mercado=V&Estado=VI&entidad=RVEMI"
DETAIL_URL = f"{BASE_URL}/institucional/mercados/entidad.php?mercado=V&rut={{rut}}&tipoentidad=RVEMI&vig=VI&control=svs&pestania=1"

DELAY = 0.5
TIMEOUT = 20

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CMF-Mapper/1.0)",
    "Accept": "text/html",
    "Referer": BASE_URL,
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ── helpers ───────────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Lowercase, remove accents, collapse non-alphanum to space."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    # drop common suffixes that differ between sources
    for suffix in ["s a", "sa", "s p a", "spa", "ltda", "y subsidiarias",
                   "y filiales", "serie a", "serie b"]:
        text = re.sub(rf"\b{re.escape(suffix)}\b", "", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    """Jaccard similarity on word sets."""
    wa, wb = set(a.split()), set(b.split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


# ── step 1: fetch full company list from CMF ──────────────────────────────────

def fetch_company_list() -> list[dict]:
    print("Fetching CMF company list...")
    r = SESSION.get(COMPANY_LIST_URL, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    companies = []
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        rut_text = cells[0].get_text(strip=True).replace(".", "")
        m = re.match(r"(\d{7,8})", rut_text)
        if not m:
            continue
        rut = m.group(1)
        nombre = cells[1].get_text(strip=True)
        companies.append({"rut": rut, "nombre": nombre, "nombre_norm": normalize(nombre)})
    print(f"  -> {len(companies)} companies found")
    return companies


# ── step 2: fetch nemotécnico from pestania=1 for each company ────────────────

def fetch_nemo(rut: str) -> str | None:
    url = DETAIL_URL.format(rut=rut)
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        # The CMF page has: <th>Nombre con  que transa en la Bolsa 2</th><td>FALABELLA</td>
        for th in soup.find_all("th"):
            text = th.get_text(" ", strip=True)
            if "transa" in text.lower() and "bolsa" in text.lower():
                td = th.find_next_sibling("td")
                if td:
                    val = td.get_text(strip=True)
                    # Valid nemo: 1–15 uppercase alphanumeric chars (may include -)
                    if val and re.match(r"^[A-Z][A-Z0-9\-]{0,14}$", val):
                        return val
    except Exception:
        pass
    return None


def build_nemo_map(companies: list[dict]) -> dict[str, str]:
    """Returns {NEMO: rut} for all companies that have a nemotécnico."""
    nemo_map = {}
    total = len(companies)
    for i, c in enumerate(companies, 1):
        rut = c["rut"]
        nemo = fetch_nemo(rut)
        if nemo:
            nemo_map[nemo] = rut
            print(f"  [{i}/{total}] {rut} ->{nemo}")
        else:
            print(f"  [{i}/{total}] {rut} ->(no nemo)")
        time.sleep(DELAY)
    return nemo_map


# ── step 3: resolve tickers ───────────────────────────────────────────────────

def resolve_tickers(tickers: list[dict], companies: list[dict],
                    nemo_map: dict[str, str]) -> tuple[list[dict], list[dict]]:
    resolved = []
    unresolved = []

    for t in tickers:
        ticker = t["ticker"]
        if t.get("rut"):
            resolved.append({**t, "_method": "existing"})
            continue

        # Extract the base nemo (e.g. "FALABELLA" from "FALABELLA.SN", "ANDINA" from "ANDINA-B.SN")
        nemo_base = ticker.replace(".SN", "").split("-")[0]
        nemo_full = ticker.replace(".SN", "")

        # Try exact nemo match (full then base)
        rut = nemo_map.get(nemo_full) or nemo_map.get(nemo_base)
        if rut:
            resolved.append({**t, "rut": rut, "_method": f"nemo:{nemo_full}"})
            continue

        # Fuzzy name match
        name_norm = normalize(t["name"])
        best_score, best_rut, best_nombre = 0.0, None, None
        for c in companies:
            score = similarity(name_norm, c["nombre_norm"])
            if score > best_score:
                best_score, best_rut, best_nombre = score, c["rut"], c["nombre"]

        if best_score >= 0.45:
            resolved.append({
                **t, "rut": best_rut,
                "_method": f"fuzzy:{best_score:.2f}:{best_nombre}"
            })
        else:
            unresolved.append({**t, "_best_score": best_score, "_best_nombre": best_nombre})

    return resolved, unresolved


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    with open("tickers_chile.json", encoding="utf-8") as f:
        tickers = json.load(f)

    companies = fetch_company_list()

    # Only fetch nemos for companies not already resolved via RUT
    already_known_ruts = {t["rut"] for t in tickers if t.get("rut")}
    print(f"\nFetching nemotécnicos from CMF (pestania=1)...")
    print(f"  This will make ~{len(companies)} requests at {DELAY}s delay "
          f"(~{len(companies)*DELAY/60:.1f} min)")

    nemo_map = build_nemo_map(companies)
    print(f"\nNemo map built: {len(nemo_map)} entries")

    # Save nemo_map for inspection / reuse
    with open("nemo_map.json", "w", encoding="utf-8") as f:
        json.dump(nemo_map, f, ensure_ascii=False, indent=2)
    print("nemo_map.json saved")

    resolved, unresolved = resolve_tickers(tickers, companies, nemo_map)

    # Write updated tickers_chile.json (strip _method key)
    updated = []
    for t in resolved:
        entry = {k: v for k, v in t.items() if not k.startswith("_")}
        updated.append(entry)
    for t in unresolved:
        entry = {k: v for k, v in t.items() if not k.startswith("_")}
        updated.append(entry)

    with open("tickers_chile.json", "w", encoding="utf-8") as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)

    # Report
    report = {
        "resolved": [
            {"ticker": t["ticker"], "rut": t.get("rut"), "method": t.get("_method")}
            for t in resolved
        ],
        "unresolved": [
            {"ticker": t["ticker"], "name": t["name"],
             "best_score": t.get("_best_score"), "best_nombre": t.get("_best_nombre")}
            for t in unresolved
        ],
    }
    with open("rut_mapping_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Resolved:   {len(resolved)}/{len(tickers)}")
    print(f"Unresolved: {len(unresolved)}/{len(tickers)}")
    if unresolved:
        print("\nUnresolved tickers:")
        for t in unresolved:
            print(f"  {t['ticker']:20s} {t['name']}")
    print("\ntickers_chile.json updated")
    print("rut_mapping_report.json saved")


if __name__ == "__main__":
    main()
