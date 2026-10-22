import os
import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from decancer_py import parse as decancer_parse

KYIV_TZ = ZoneInfo("Europe/Kyiv")
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

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


def is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def findall_unidecode(pattern: str, string: str) -> list[str]:
    """Regex findall after normalising both pattern and string with decancer."""
    return re.findall(str(decancer_parse(pattern)), str(decancer_parse(string)))


def clean_string(s: str) -> str:
    """Strip non-printable characters."""
    return "".join(c for c in s if c.isprintable())


def unique_numbers_by_pattern(pattern: str, names: list[str]) -> dict[str, int] | None:
    """Map each name to the first number captured by ``pattern``.

    Returns ``None`` unless every name matches and all numbers are distinct.
    """
    results: dict[str, int] = {}
    for name in names:
        matches = re.findall(pattern, name, re.IGNORECASE)
        if matches:
            results[name] = int(matches[0])
    if len(results) == len(names) and len(set(results.values())) == len(names):
        return results
    return None


def positional_numbers(names: list[str]) -> dict[str, int] | None:
    """Find the first numeric column that differs across all names.

    Requires every name to contain the same count of numbers.
    """
    if len(names) <= 1:
        return None
    all_nums = [re.findall(r"\d+", name) for name in names]
    if len(set(len(nums) for nums in all_nums)) != 1:
        return None
    for col in range(len(all_nums[0])):
        vals = [int(nums[col]) for nums in all_nums]
        if len(set(vals)) == len(names):
            return {name: int(nums[col]) for name, nums in zip(names, all_nums)}
    return None
