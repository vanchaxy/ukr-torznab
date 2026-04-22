from pathlib import Path

from ukr_torznab.utils import findall_unidecode


def _unique_season_from_files(
    files: list[Path],
    primary_pattern: str,
    fallback_patterns: list[str] | None = None,
) -> int | None:
    seasons: set[int] = set()
    has_missing = False

    for f in files:
        matches = findall_unidecode(primary_pattern, str(f.name))
        if not matches:
            matches = findall_unidecode(primary_pattern, str(f))
        if not matches and fallback_patterns:
            for pat in fallback_patterns:
                matches = findall_unidecode(pat, str(f))
                if matches:
                    break
        if matches:
            seasons.update(int(m) for m in matches if int(m))
        else:
            has_missing = True

    if len(seasons) > 1:
        return None
    if len(seasons) == 1 and not has_missing:
        return seasons.pop()
    return None


def detect_season(name: str, video_files: list[Path]) -> int | None:
    # Multi-season indicators in the torrent name → skip
    if (
        findall_unidecode(r"сезони\s\d", name)
        or findall_unidecode(r"\d\sсезони", name)
        or findall_unidecode(r"(сезон|season)\s*\d+\s*-\s*\d", name)
        or len(findall_unidecode(r"сезон\s\d", name)) > 1
    ):
        return None

    # Strategy 1: SxxExx pattern in file names
    season = _unique_season_from_files(
        video_files,
        primary_pattern=r"(?:[^a-z]|^)s(\d+)",
    )
    if season is not None:
        return season

    # Strategy 2: NNxNN pattern
    season = _unique_season_from_files(
        video_files,
        primary_pattern=r"[^\d](\d{1,2})x\d{1,2}",
    )
    if season is not None:
        return season

    # Strategy 3: "сезон N" / "season N" in torrent name
    from_name = (
        findall_unidecode(r"сезон\s*(\d+)", name)
        or findall_unidecode(r"(\d+)[\s]*сезон", name)
        or findall_unidecode(r"seasоn\s*(\d+)", name)
        or findall_unidecode(r"(\d+)[\s]*seasоn", name)
    )
    if from_name:
        return int(from_name[0])

    # Strategy 4: "сезон/season N" inside file paths
    season = _unique_season_from_files(
        video_files,
        primary_pattern=r"сезон[\s_]*(\d+)",
        fallback_patterns=[
            r"(\d+)[\s_]*сезон",
            r"season[\s_]*(\d+)",
            r"(\d+)[\s_]*season",
        ],
    )
    if season is not None:
        return season

    # Default: assume season 1 when nothing else matches
    return 1
