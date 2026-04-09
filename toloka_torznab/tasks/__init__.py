from .base import AbstractTask
from .consumer import ElectricConsumerTask
from .renamer import RenameTorrentsTask
from .scraper import (
    CheckNewTopicsTask,
    DownloadTopicsTask,
    ParseTopicsTask,
    RefreshImdbTask,
    RefreshTopicsTask,
)

__all__ = [
    "AbstractTask",
    "CheckNewTopicsTask",
    "DownloadTopicsTask",
    "ElectricConsumerTask",
    "ParseTopicsTask",
    "RefreshImdbTask",
    "RefreshTopicsTask",
    "RenameTorrentsTask",
]
