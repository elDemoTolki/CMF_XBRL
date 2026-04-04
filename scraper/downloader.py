import os
from scraper.logger import logger

DATA_DIR = "data"


def save(content: bytes, rut: str, year: int, month: int,
         folder_name: str) -> str | None:
    """
    Saves the downloaded XBRL ZIP to:
      data/{folder_name}/{year}/{month:02d}/{folder_name}_{year}_{month:02d}.zip

    folder_name is built by company_index.folder_name() and is human-readable.
    Returns the file path if saved, None if skipped or failed.
    """
    dest_dir = os.path.join(DATA_DIR, folder_name, str(year), f"{month:02d}")
    os.makedirs(dest_dir, exist_ok=True)

    filename = f"{folder_name}_{year}_{month:02d}.zip"
    filepath = os.path.join(dest_dir, filename)

    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        logger.info(f"{year}-{month:02d} | RUT:{rut} | SKIPPED | {filename}")
        return filepath

    try:
        with open(filepath, "wb") as f:
            f.write(content)
        logger.info(f"{year}-{month:02d} | RUT:{rut} | DOWNLOADED | {filename}")
        return filepath
    except OSError as exc:
        logger.error(f"{year}-{month:02d} | RUT:{rut} | SAVE_ERROR | {filename} | {exc}")
        return None
