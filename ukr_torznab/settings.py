import os

DATABASE_URL: str = os.environ["DATABASE_URL"]
ALEMBIC_DATABASE_URL: str = DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")

OPENAI_API_KEY: str | None = os.environ.get("OPENAI_API_KEY")

UTP_API_KEY: str | None = os.environ.get("UTP_API_KEY")

# Consumer mode by default; set ELECTRIC_URL to an empty string to run the scraper instead.
ELECTRIC_URL: str = os.environ.get("ELECTRIC_URL", "https://electric.vnchx.com")

API_PORT: int = int(os.environ.get("API_PORT", "8000"))

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

QBITTORRENT_URL: str | None = os.environ.get("QBITTORRENT_URL")
QBITTORRENT_USERNAME: str = os.environ.get("QBITTORRENT_USERNAME", "admin")
QBITTORRENT_PASSWORD: str = os.environ.get("QBITTORRENT_PASSWORD", "adminadmin")
QBITTORRENT_CATEGORIES: set[str] = {
    c.strip() for c in os.environ.get("QBITTORRENT_CATEGORIES", "tv,movies").split(",") if c.strip()
}
QBITTORRENT_RENAME_TAG: str = os.environ.get("QBITTORRENT_RENAME_TAG", "renamed")
QBITTORRENT_RENAME_ERROR_TAG: str = os.environ.get("QBITTORRENT_RENAME_ERROR_TAG", "rename-error")

TOLOKA_USERNAME = os.environ["TOLOKA_USERNAME"]
TOLOKA_PASSWORD = os.environ["TOLOKA_PASSWORD"]

# Category id -> display name (shown on /stats). The group is kept as a prefix because names repeat.
TOLOKA_CATEGORY_NAMES: dict[str, str] = {
    # Українське кіно
    "84": "Укр. кіно · Мультфільми і казки",
    "42": "Укр. кіно · Художні фільми",
    "124": "Укр. кіно · Телесеріали",
    "125": "Укр. кіно · Мультсеріали",
    "129": "Укр. кіно · АртХаус",
    "219": "Укр. кіно · Аматорське відео",
    # Українське озвучення
    "16": "Озвучення · Фільми",
    "32": "Озвучення · Телесеріали",
    "19": "Озвучення · Мультфільми",
    "44": "Озвучення · Мультсеріали",
    "127": "Озвучення · Аніме",
    "55": "Озвучення · АртХаус",
    "144": "Озвучення · Короткометражні",
    # Українські субтитри
    "70": "Субтитри · Фільми",
    "192": "Субтитри · Телесеріали",
    "193": "Субтитри · Мультфільми",
    "195": "Субтитри · Мультсеріали",
    "194": "Субтитри · Аніме",
    "196": "Субтитри · АртХаус",
    "197": "Субтитри · Короткометражні",
    # Документальні фільми українською
    "21": "Документальні · Українські наукові документальні фільми",
    "131": "Документальні · Українські історичні документальні фільми",
    "226": "Документальні · BBC",
    "227": "Документальні · Discovery",
    "228": "Документальні · National Geographic",
    "229": "Документальні · History Channel",
    "230": "Документальні · Інші іноземні документальні фільми",
    # Телепередачі українською
    "132": "Телепередачі · Телевізійні шоу та програми",
    # HD українською
    "96": "HD · Фільми в HD",
    "173": "HD · Серіали в HD",
    "139": "HD · Мультфільми в HD",
    "174": "HD · Мультсеріали в HD",
    "140": "HD · Документальні фільми в HD",
    # DVD українською
    "66": "DVD · Художні фільми та серіали в DVD",
    "137": "DVD · Мультфільми та мультсеріали в DVD",
    "138": "DVD · Документальні фільми в DVD",
}
TOLOKA_CATEGORIES = list(TOLOKA_CATEGORY_NAMES)
