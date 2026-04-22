import os
import re
from collections import defaultdict

from ukr_torznab.clients.utp.mappings import QUALITY_MAP, RESOLUTION_MAP, STUDIO_MAP
from ukr_torznab.models import (
    LANG_FULL_REVERSE,
    AspectRatio,
    AudioSource,
    AudioType,
    CodecFamily,
    Lang,
    Quality,
    Resolution,
    VideoFormat,
)
from ukr_torznab.utils import VIDEO_EXTENSIONS

QUALITY_RE = re.compile(
    r"(?i)\b(?:1080[pi]|2160p|"
    r"web-?dl|web-?rip|bd-?remux|bd-?rip|hd-?tv-?rip|hdtv|"
    r"uhd-?bdrip|dvdrip|hdrip|hddvdrip|complete\s+bluray|bluray|webrip)\b",
)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
SEASON_RE = re.compile(r"(?<!\w)[Ss](\d{1,2})(?:[Ee](\d{1,3}))?(?!\w)")
SEASON_PART_RE = re.compile(r"(?i)\bpart\s*\d")

_APOS = r"['`'\u02bc]"

CUT_RE = re.compile(
    rf"\b("
    rf"(?:Unrated|Extended|Final|Ultimate)\s+Director{_APOS}?s?\s+Cut"
    rf"|Director{_APOS}?s?\s+(?:Definitive|Final)\s+Cut"
    rf"|Director{_APOS}?s?\s+Cut"
    rf"|(?:Special\s+)?Assembly\s+Cut(?:\s+Edition)?"
    rf"|The\s+Super\s+Duper\s+Cut"
    rf"|The\s+(?:Final|Rogue|Darklighter)\s+Cut"
    rf"|Unrated\s+Extended\s+Cut"
    rf"|Extended\s+Cut"
    rf"|Unrated\s+Cut(?:\s+Version)?"
    rf"|(?:Theatrical|International|Alternate|Original|Bootleg|Cannes|Ulysses|Remastered|European|Ultimate|Final)\s+Cut"
    rf"|Producer{_APOS}?s?\s+Cut"
    rf"|Roadshow\s+Version"
    rf"|(?:Hong\s+Kong|Taco\s+Bell|UK\s+Theatrical)\s+Cut"
    rf"|(?:US|UK|GBR|FRA|JPN|GER|EUR|NLD|CAN|AUS|TWN|SWE|ITA|NOR|KOR)\s+Cut"
    rf"|Uncut\s+Version"
    rf"|Uncut"
    rf")\b",
    re.IGNORECASE,
)
GROUP_RE = re.compile(r"-([^-\s]+(?:\.\s?[^-\s]+)?(?:\s*[,/]\s*[^-\s]+(?:\.\s?[^-\s]+)?)*)\s*$")
HYBRID_RE = re.compile(r"\bhybrid", re.IGNORECASE)

_REGIONS = {
    "us",
    "uk",
    "gbr",
    "fra",
    "jpn",
    "ger",
    "eur",
    "nld",
    "can",
    "aus",
    "twn",
    "swe",
    "ita",
    "nor",
    "kor",
}


def _normalize_cut(cut: str) -> str:
    cut = re.sub(r"\s+", " ", cut.strip())
    cut = re.sub(rf"\bDirector{_APOS}?s?\b", "Director's", cut, flags=re.IGNORECASE)
    cut = re.sub(rf"\bProducer{_APOS}?s?\b", "Producer's", cut, flags=re.IGNORECASE)
    out = []
    for w in cut.split():
        if w.lower() in _REGIONS:
            out.append(w.upper())
        elif w in ("Director's", "Producer's"):
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


_EPISODE_PATTERNS = [
    r"s\d+.?e(\d+)",  # S01E05
    r"\be(\d+)",  # E05
    r"\dx(\d+)",  # 1x05
    r"[^/](\d+)",  # /5.
]


def _try_pattern(pattern: str, files: list[str]) -> dict[str, int] | None:
    results: dict[str, int] = {}
    for f in files:
        m = re.findall(pattern, f, re.IGNORECASE)
        if m:
            results[f] = int(m[0])
    if len(results) == len(files) and len(set(results.values())) == len(files):
        return results
    return None


def _positional(files: list[str]) -> dict[str, int] | None:
    if len(files) <= 1:
        return None
    all_nums = [re.findall(r"\d+", f) for f in files]
    if len(set(len(n) for n in all_nums)) != 1:
        return None
    for col in range(len(all_nums[0])):
        vals = [int(n[col]) for n in all_nums]
        if len(set(vals)) == len(files):
            return {f: int(n[col]) for f, n in zip(files, all_nums)}
    return None


def _extract_episode_numbers(basenames: list[str]) -> dict[str, int] | None:
    for pat in _EPISODE_PATTERNS:
        result = _try_pattern(pat, basenames)
        if result:
            return result
    return _positional(basenames)


def build_file_to_episode(season: int, files: list[dict]) -> dict[str, list[int]] | None:
    video_files = [
        f for f in files if os.path.splitext(f.get("name", ""))[1].lower() in VIDEO_EXTENSIONS
    ]
    if not video_files:
        return None
    paths = [f["name"] for f in video_files]
    ep_map = _extract_episode_numbers(paths)
    if ep_map is None:
        return None
    season = season or 1
    return {filename.lower(): [season, ep] for filename, ep in ep_map.items()}


def parse_release(name: str, type: str, resolution: str, files: list, is_tv: bool) -> dict:
    quality = QUALITY_MAP.get(type, Quality.UNKNOWN)
    resolution = RESOLUTION_MAP.get(resolution, Resolution.UNKNOWN)

    group = None
    gm = GROUP_RE.search(name)
    if gm:
        group = gm.group(1).lower()
        if group in ("1", "2", "dl"):
            group = None

    qm = QUALITY_RE.search(name)
    qpos = qm.start() if qm else len(name)

    year_match = None
    for m in YEAR_RE.finditer(name, 0, qpos):
        year_match = m
    year = int(year_match.group()) if year_match else None
    year_pos = year_match.start() if year_match else None
    year_end = year_match.end() if year_match else None

    season = None
    min_episode = None
    max_episode = None
    season_complete = None
    season_pos = None
    if is_tv:
        sm = SEASON_RE.search(name, 0, qpos)
        if sm:
            season_pos = sm.start()
            season = int(sm.group(1))
            min_episode = max_episode = int(sm.group(2)) if sm.group(2) else None
        else:
            season = 1
        season_complete = min_episode is None or SEASON_PART_RE.search(name, 0, qpos)
        file_to_episode = build_file_to_episode(season, files)
        if file_to_episode and not season_complete:
            eps = [v[1] for v in file_to_episode.values() if v[0] == season]
            if eps:
                min_episode, max_episode = min(eps), max(eps)

    cands = [p for p in (year_pos, season_pos) if p is not None]
    end = min(cands) if cands else qpos
    title = name[:end].strip()

    cut = None
    cm = CUT_RE.search(name, year_end if year_end is not None else 0)
    if cm:
        c = _normalize_cut(cm.group(1))
        if c.lower() != "theatrical cut":
            cut = c

    is_hybrid = bool(HYBRID_RE.search(name, year_end if year_end is not None else 0))

    ratio = None
    if re.findall(r"\bIMAX\b", name):
        ratio = AspectRatio.IMAX
    elif re.findall(r"\bOpen Matte\b", name):
        ratio = AspectRatio.OPEN_MATTE

    if "DV HDR10+" in name:
        hdr = VideoFormat.DV_HDR10_PLUS
    elif "DV HDR" in name:
        hdr = VideoFormat.DV_HDR
    elif "DV" in name:
        hdr = VideoFormat.DV
    elif "HDR10+" in name:
        hdr = VideoFormat.HDR10_PLUS
    elif "HDR" in name:
        hdr = VideoFormat.HDR
    elif "HLG" in name:
        hdr = VideoFormat.HLG
    elif "PQ10" in name:
        hdr = VideoFormat.PQ10
    else:
        hdr = VideoFormat.SDR

    if "MPEG-2" in name:
        codec = CodecFamily.MPEG2
    elif "VC-1" in name:
        codec = CodecFamily.VC1
    elif "VP9" in name:
        codec = CodecFamily.VP9
    elif "AV1" in name:
        codec = CodecFamily.AV1
    elif (
        "HEVC" in name
        or "H.265" in name
        or "x265" in name
        or "x.265" in name
        or resolution is Resolution.UHD_2160P
    ):
        codec = CodecFamily.HEVC
    else:
        codec = CodecFamily.AVC

    return {
        "title": title,
        "year": year,
        "season": season,
        "min_episode": min_episode,
        "max_episode": max_episode,
        "season_complete": season_complete,
        "quality": quality,
        "resolution": resolution,
        "cut": cut,
        "ratio": ratio,
        "hdr": hdr,
        "hybrid": is_hybrid,
        "group": group,
        "codec": codec,
    }


def parse_mediainfo(text: str) -> dict[str, list[dict[str, str]]]:
    sections: dict[str, list[dict[str, str]]] = defaultdict(list)
    current: str | None = None
    current_data: dict[str, str] | None = None

    for line in text.splitlines():
        if not line.strip():
            continue
        if ":" not in line or re.match(r"^[A-Za-z][A-Za-z0-9 #]*$", line.strip()):
            if current_data is not None and current is not None:
                sections[current].append(current_data)
            current = line.strip().split()[0]
            current_data = {}
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if current_data is not None:
            current_data[key] = value

    if current_data is not None and current is not None:
        sections[current].append(current_data)

    return dict(sections)


def _parse_lang(raw: str) -> Lang:
    s = raw.lower()
    for key, lang in LANG_FULL_REVERSE.items():
        if key in s:
            return lang
    return Lang.UNKNOWN


def _detect_audio_type(title: str) -> AudioType:
    t = title.lower()
    if "dub" in t or "дубляж" in t:
        return AudioType.DUB
    if "mvo" in t or "багатоголосий" in t:
        return AudioType.MVO
    if "dvo" in t:
        return AudioType.DVO
    if "svo" in t:
        return AudioType.SVO
    if "original" in t or "оригінал" in t or "eng" in t:
        return AudioType.ORIGINAL
    return AudioType.UNKNOWN


def _detect_studio(title: str) -> AudioSource | None:
    t = title.lower()
    for keyword, source in STUDIO_MAP:
        if keyword in [x.strip() for x in t.split("|")]:
            return source
    for keyword, source in STUDIO_MAP:
        if keyword in t:
            return source
    return None


def parse_audio_tracks(
    mediainfo: dict[str, list[dict[str, str]]],
) -> tuple[list[AudioType], list[AudioSource], list[Lang]]:
    audio_types: set[AudioType] = set()
    audio_sources: set[AudioSource] = set()
    audio_langs: set[Lang] = set()

    for track in mediainfo.get("Audio", []):
        lang = _parse_lang(track.get("Language", ""))
        audio_langs.add(lang)

        title = track.get("Title", "")
        audio_types.add(_detect_audio_type(title))

        studio = _detect_studio(title)
        if studio is not None:
            audio_sources.add(studio)

    return (
        sorted(audio_types, key=lambda l: l.value),
        sorted(audio_sources, key=lambda l: l.name),
        sorted(audio_langs, key=lambda l: l.value),
    )


def parse_subtitle_langs(
    mediainfo: dict[str, list[dict[str, str]]],
) -> list[Lang]:
    langs: set[Lang] = set()
    for track in mediainfo.get("Text", []):
        lang = _parse_lang(track.get("Language", ""))
        langs.add(lang)
    return sorted(langs, key=lambda l: l.value)
