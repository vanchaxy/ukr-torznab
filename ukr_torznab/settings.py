import os

DATABASE_URL: str = os.environ["DATABASE_URL"]
ALEMBIC_DATABASE_URL: str = DATABASE_URL.replace("+aiosqlite", "").replace("+asyncpg", "")

OPENAI_API_KEY: str | None = os.environ.get("OPENAI_API_KEY")

UTP_API_KEY: str | None = os.environ.get("UTP_API_KEY")

ELECTRIC_URL: str | None = os.environ.get("ELECTRIC_URL")

API_PORT: int = int(os.environ.get("API_PORT", "8000"))

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

TOLOKA_CATEGORIES = [
    # Українське кіно
    "84",  # Мультфільми і казки
    "42",  # Художні фільми
    "124",  # Телесеріали
    "125",  # Мультсеріали
    "129",  # АртХаус
    "219",  # Аматорське відео
    # Українське озвучення
    "16",  # Фільми
    "32",  # Телесеріали
    "19",  # Мультфільми
    "44",  # Мультсеріали
    "127",  # Аніме
    "55",  # АртХаус
    "144",  # Короткометражні
    # Українські субтитри
    "70",  # Фільми
    "192",  # Телесеріали
    "193",  # Мультфільми
    "195",  # Мультсеріали
    "194",  # Аніме
    "196",  # АртХаус
    "197",  # Короткометражні
    # Документальні фільми українською
    "21",  # Українські наукові документальні фільми
    "131",  # Українські історичні документальні фільми
    "226",  # BBC
    "227",  # Discovery
    "228",  # National Geographic
    "229",  # History Channel
    "230",  # Інші іноземні документальні фільми
    # Телепередачі українською
    "132",  # Телевізійні шоу та програми
    # HD українською
    "96",  # Фільми в HD
    "173",  # Серіали в HD
    "139",  # Мультфільми в HD
    "174",  # Мультсеріали в HD
    "140",  # Документальні фільми в HD
    # DVD українською
    "66",  # Художні фільми та серіали в DVD
    "137",  # Мультфільми та мультсеріали в DVD
    "138",  # Документальні фільми в DVD
]

VIDEO_EXTENSIONS = []
