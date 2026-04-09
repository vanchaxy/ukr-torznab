from __future__ import annotations

import re

from decancer_py import parse as decancer_parse

VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {".mkv", ".avi", ".mp4", ".ts", ".vob", ".m4v", ".mpg", ".mpeg"},
)
SUB_EXTENSIONS: frozenset[str] = frozenset({".srt", ".ass", ".ssa", ".sup"})
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".png", ".jpg"})
AUDIO_EXTENSIONS: frozenset[str] = frozenset({".mp2", ".mp3", ".ac3", ".dts"})
OTHER_EXTENSIONS: frozenset[str] = frozenset({".ttf", ".ifo", ".bup", ".txt", ".otf"})

ALLOWED_EXTENSIONS: frozenset[str] = (
    VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | SUB_EXTENSIONS | IMAGE_EXTENSIONS | OTHER_EXTENSIONS
)


def findall_unidecode(pattern: str, string: str) -> list[str]:
    """Regex findall after normalising both pattern and string with decancer."""
    return re.findall(str(decancer_parse(pattern)), str(decancer_parse(string)))


def clean_string(s: str) -> str:
    """Strip non-printable characters."""
    return "".join(c for c in s if c.isprintable())
