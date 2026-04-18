"""UTP (utp.to) tracker client — unit3D API proxy."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict

import httpx

from ukr_torznab.enums import (
    AspectRatio,
    AudioSource,
    AudioType,
    CodecFamily,
    Lang,
    Quality,
    Resolution,
    VideoFormat,
)

log = logging.getLogger(__name__)

_BASE_URL = "https://utp.to/api/torrents"

_TYPE_TO_QUALITY: dict[str, Quality] = {
    "Encode": Quality.BLURAY,
    "Remux": Quality.REMUX,
    "WEB-DL": Quality.WEBDL,
    "WEBRip": Quality.WEBRIP,
    "HDTV": Quality.HDTV,
    "Full Disc": Quality.BR_DISK,
}

# unit3D "resolution" → Resolution enum
_RESOLUTION_MAP: dict[str, Resolution] = {
    "2160p": Resolution.UHD_2160P,
    "1080p": Resolution.FHD_1080P,
    "1080i": Resolution.FHD_1080P,
}

QUALITY_RE = re.compile(
    r"(?i)\b(?:1080[pi]|2160p|"
    r"web-?dl|web-?rip|bd-?remux|bd-?rip|hd-?tv-?rip|hdtv|"
    r"uhd-?bdrip|dvdrip|hdrip|hddvdrip|complete\s+bluray|bluray|webrip)\b",
)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
SEASON_RE = re.compile(r"(?<!\w)[Ss](\d{1,2})(?:[Ee](\d{1,3}))?(?!\w)")

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


def parse_release(name: str, is_tv: bool) -> dict:
    """Extract structured metadata from a UTP release name."""
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

    season = episode = season_pos = None
    if is_tv:
        sm = SEASON_RE.search(name, 0, qpos)
        if sm:
            season_pos = sm.start()
            season = int(sm.group(1))
            episode = int(sm.group(2)) if sm.group(2) else None

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
    elif "HEVC" in name or "H.265" in name or "x265" in name or "x.265" in name:
        codec = CodecFamily.HEVC
    else:
        codec = CodecFamily.AVC

    return {
        "title": title,
        "year": year,
        "season": season,
        "episode": episode,
        "cut": cut,
        "ratio": ratio,
        "hdr": hdr,
        "hybrid": is_hybrid,
        "group": group,
        "codec": codec,
    }


def parse_mediainfo(text: str) -> dict[str, list[dict[str, str]]]:
    """Parse mediainfo text into sections with key-value dicts."""
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


_LANG_MAP: list[tuple[str, Lang]] = [
    ("ukrainian", Lang.UKRAINIAN),
    ("english", Lang.ENGLISH),
    ("french", Lang.FRENCH),
    ("german", Lang.GERMAN),
    ("spanish", Lang.SPANISH),
    ("italian", Lang.ITALIAN),
    ("japanese", Lang.JAPANESE),
    ("korean", Lang.KOREAN),
    ("cantonese", Lang.CHINESE),
    ("mandarin", Lang.CHINESE),
    ("chinese", Lang.CHINESE),
    ("russian", Lang.RUSSIAN),
    ("polish", Lang.POLISH),
    ("czech", Lang.CZECH),
    ("portuguese", Lang.PORTUGUESE),
    ("dutch", Lang.DUTCH),
    ("swedish", Lang.SWEDISH),
    ("norwegian", Lang.NORWEGIAN),
    ("danish", Lang.DANISH),
    ("finnish", Lang.FINNISH),
    ("hungarian", Lang.HUNGARIAN),
    ("romanian", Lang.ROMANIAN),
    ("turkish", Lang.TURKISH),
    ("arabic", Lang.ARABIC),
    ("hindi", Lang.HINDI),
    ("thai", Lang.THAI),
    ("persian", Lang.PERSIAN),
    ("greek", Lang.GREEK),
    ("serbian", Lang.SERBIAN),
    ("croatian", Lang.CROATIAN),
    ("bulgarian", Lang.BULGARIAN),
    ("slovak", Lang.SLOVAK),
    ("slovenian", Lang.SLOVENIAN),
    ("estonian", Lang.ESTONIAN),
    ("indonesian", Lang.INDONESIAN),
    ("icelandic", Lang.ICELANDIC),
    ("afrikaans", Lang.AFRIKAANS),
    ("vietnamese", Lang.VIETNAMESE),
    ("flemish", Lang.DUTCH),
    ("hebrew", Lang.HEBREW),
    ("lithuanian", Lang.LITHUANIAN),
    ("malayalam", Lang.MALAYALAM),
    ("latvian", Lang.LATVIAN),
    ("catalan", Lang.CATALAN),
    ("bosnian", Lang.BOSNIAN),
    ("tamil", Lang.TAMIL),
    ("macedonian", Lang.MACEDONIAN),
]


def _parse_lang(raw: str) -> Lang:
    s = raw.lower()
    for key, lang in _LANG_MAP:
        if key in s:
            return lang
    return Lang.UNKNOWN


_STUDIO_MAP: list[tuple[str, AudioSource]] = sorted(
    [
        ("ааа-sound", AudioSource.AAA_SOUND),
        ("aaa-sound", AudioSource.AAA_SOUND),
        ("aaa sound", AudioSource.AAA_SOUND),
        ("aaasound", AudioSource.AAA_SOUND),
        ("ааа sound", AudioSource.AAA_SOUND),
        ("amanogawa", AudioSource.AMANOGAWA),
        ("amc", AudioSource.AMC),
        ("амс", AudioSource.AMC),
        ("aniua", AudioSource.ANI_UA),
        ("артхаус трафік", AudioSource.ARTHAUS_TRAFFIC),
        ("artymko", AudioSource.ARTYMKO),
        ("baibako.tv", AudioSource.BAIBAKO),
        ("baibako", AudioSource.BAIBAKO),
        ("cinemaker", AudioSource.CINEMAKER),
        ("cinema sound production", AudioSource.CINEMA_SOUND_PRODUCTION),
        ("cinemasoundproduction", AudioSource.CINEMA_SOUND_PRODUCTION),
        ("cinema sound ua", AudioSource.CINEMA_SOUND_PRODUCTION),
        ("cinetype", AudioSource.CINETYPE),
        ("clankaizoku", AudioSource.CLAN_KAIZOKU),
        ("kaizoku", AudioSource.CLAN_KAIZOKU),
        ("cloverdub", AudioSource.CLOVER_DUB),
        ("comedy central", AudioSource.COMEDY_CENTRAL),
        ("comedycentral", AudioSource.COMEDY_CENTRAL),
        ("didko studio", AudioSource.DIDKO_STUDIO),
        ("didkostudio", AudioSource.DIDKO_STUDIO),
        ("dniprofilm", AudioSource.DNIPROFILM),
        ("rezka", AudioSource.DNIPROFILM),
        ("dzuski", AudioSource.DZUSKI),
        ("enter-фільм", AudioSource.ENTER_FILM),
        ("enterfilm", AudioSource.ENTER_FILM),
        ("ентер", AudioSource.ENTER_FILM),
        ("enter", AudioSource.ENTER_FILM),
        ("еники-беники", AudioSource.ENYKY_BENYKY),
        ("fanvoxua", AudioSource.FANVOX_UA),
        ("гарні люди", AudioSource.GARNI_LUDY),
        ("гарнілюди", AudioSource.GARNI_LUDY),
        ("glassmoon", AudioSource.GLASS_MOON),
        ("glass moon", AudioSource.GLASS_MOON),
        ("gwean & maslinka", AudioSource.GWEAN_AND_MASLINKA),
        ("gwean&maslinka", AudioSource.GWEAN_AND_MASLINKA),
        ("гайдамайк", AudioSource.HAIDA_MIKE),
        ("hiventy", AudioSource.HIVENTY),
        ("hth", AudioSource.HUMOR_TB),
        ("ictv", AudioSource.ICTV),
        ("inaridub", AudioSource.INARI),
        ("inariokami", AudioSource.INARI),
        ("індиго", AudioSource.INDIGO),
        ("інтер", AudioSource.INTER),
        ("inter", AudioSource.INTER),
        ("itunes", AudioSource.ITUNES),
        ("к1", AudioSource.K1),
        ("k1", AudioSource.K1),
        ("kiho", AudioSource.KINO),
        ("кіно", AudioSource.KINO),
        ("kioto anime", AudioSource.KIOTO_ANIME),
        ("кіт", AudioSource.KIT),
        ("kit", AudioSource.KIT),
        ("колодій трейлерів", AudioSource.KOLODIY_TRAYLERIV),
        ("колодійтрейлерів", AudioSource.KOLODIY_TRAYLERIV),
        ("київстар тб", AudioSource.KYIVSTAR_TV),
        ("le doyen", AudioSource.LE_DOYEN),
        ("ledoyen", AudioSource.LE_DOYEN),
        ("matsura", AudioSource.MATSURA_UA),
        ("maxwell kennedy", AudioSource.MAXWELL_KENNEDY),
        ('тк "мега"', AudioSource.MEGA_TV),
        ("megogo", AudioSource.MEGOGO),
        ("mgg", AudioSource.MEGOGO),
        ("netflix", AudioSource.NETFLIX),
        ("незупиняйпродакшн", AudioSource.NE_ZUPYNYAY_PRODUCTION),
        ("нло", AudioSource.NLO_TV),
        ("nlo", AudioSource.NLO_TV),
        ("новий", AudioSource.NOVYI_KANAL),
        ("novy", AudioSource.NOVYI_KANAL),
        ("нтн", AudioSource.NTN),
        ("омікрон", AudioSource.OMIKRON),
        ("omikron", AudioSource.OMIKRON),
        ("1+1", AudioSource.ONE_PLUS_ONE),
        ("blu-ray", AudioSource.ORIGINAL_BLURAY),
        ("dvd", AudioSource.ORIGINAL_DVD),
        ("ozz tv", AudioSource.OZZ_TV),
        ("paramount comedy", AudioSource.PARAMOUNT_COMEDY),
        ("paramountcomedy", AudioSource.PARAMOUNT_COMEDY),
        ("перший", AudioSource.PERSHYI),
        ("piepostproduction", AudioSource.PIE_POST_PRODUCTION),
        ("дім", AudioSource.PIXEL),
        ("плюсплюс", AudioSource.PLUS_PLUS),
        ("postmodern", AudioSource.POSTMODERN),
        ("постмодерн", AudioSource.POSTMODERN),
        ("qtv", AudioSource.QTV),
        ("rakuten", AudioSource.RAKUTEN),
        ("робота голосом", AudioSource.ROBOTA_GOLOSOM),
        ("роботаголосом", AudioSource.ROBOTA_GOLOSOM),
        ("saturn union", AudioSource.SATURN_UNION),
        ("simpsonsua", AudioSource.SIMPSONS_UA),
        ("simpsonsua.tv", AudioSource.SIMPSONS_UA),
        ("slava radyk", AudioSource.SLAVA_RADYK),
        ("slavaradyk", AudioSource.SLAVA_RADYK),
        ("starfall", AudioSource.STARFALL),
        ("стб", AudioSource.STB),
        ("cтруґачка", AudioSource.STRUGACHKA),
        ("15k3", AudioSource.STUDIO_15K3),
        ("15к3", AudioSource.STUDIO_15K3),
        ("sunnysiders", AudioSource.SUNNYSIDERS),
        ("суспільне культура", AudioSource.SUSPILNE_KULTURA),
        ("суспільнекультура", AudioSource.SUSPILNE_KULTURA),
        ("культура", AudioSource.SUSPILNE_KULTURA),
        ("vhs record", AudioSource.SWEET_SOUND_STUDIO),
        ("sweet", AudioSource.SWEET_SOUND_STUDIO),
        ("тактребапродакшн", AudioSource.TAK_TREBA_PRODUCTION),
        ("так треба продакшн", AudioSource.TAK_TREBA_PRODUCTION),
        ("тет", AudioSource.TET),
        ("tet", AudioSource.TET),
        ("tretyakoff", AudioSource.TRETYAKOFF),
        ("цікава ідея", AudioSource.TSIKAVA_IDEYA),
        ("цікаваідея", AudioSource.TSIKAVA_IDEYA),
        ("tv5", AudioSource.TV5),
        ("твій продакшн", AudioSource.TVIY_PRODUCTION),
        ("твоє кіно", AudioSource.TVOYE_KINO_RELAX_HD),
        ("твоєкіно", AudioSource.TVOYE_KINO_RELAX_HD),
        ("2+2", AudioSource.TWO_PLUS_TWO),
        ("uaflix", AudioSource.UAFLIX),
        ("uateam", AudioSource.UATEAM),
        ("ufdub", AudioSource.UFDUB),
        ("україна", AudioSource.UKRAINA),
        ("vhsrecord", AudioSource.VHS_RECORD),
        ("cine+", AudioSource.VOLYA_CINE_PLUS),
        ("в одне рило", AudioSource.V_ODNE_RYLO),
        ("воднерило", AudioSource.V_ODNE_RYLO),
    ],
    key=lambda t: -len(t[0]),
)


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
    for keyword, source in _STUDIO_MAP:
        if keyword == t.split("|")[-1].strip():
            return source
    for keyword, source in _STUDIO_MAP:
        if keyword in t:
            return source
    return None


def parse_audio_tracks(
    mediainfo: dict[str, list[dict[str, str]]],
) -> tuple[list[AudioType], list[AudioSource], list[Lang]]:
    """Extract audio types, studios, and languages from parsed mediainfo."""
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

    return list(audio_types), list(audio_sources), list(audio_langs)


def parse_subtitle_langs(
    mediainfo: dict[str, list[dict[str, str]]],
) -> list[Lang]:
    """Extract subtitle languages from parsed mediainfo."""
    langs: set[Lang] = set()
    for track in mediainfo.get("Text", []):
        lang = _parse_lang(track.get("Language", ""))
        langs.add(lang)
    return list(langs)


_EPISODE_PATTERNS = [
    r"s\d+.?e(\d+)",  # S01E05
    r"\be(\d+)",  # E05
    r"\dx(\d+)",  # 1x05
    r"[^/](\d+)",  # dotted notation
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


def extract_episode_numbers(basenames: list[str]) -> dict[str, int] | None:
    """Map video basenames → episode number. Returns None if no pattern matches."""
    for pat in _EPISODE_PATTERNS:
        result = _try_pattern(pat, basenames)
        if result:
            return result
    return _positional(basenames)


class UtpClient:
    """Async client for the utp.to unit3D API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(base_url=_BASE_URL, timeout=30)

    async def search(
        self,
        *,
        name: str | None = None,
        imdb_id: int | None = None,
        tvdb_id: int | None = None,
        tmdb_id: int | None = None,
        categories: list[int] | None = None,
        season: int | None = None,
        episode: int | None = None,
        per_page: int = 100,
        page: int = 1,
    ) -> list[dict]:
        """Search UTP via unit3D filter API. Returns raw torrent dicts."""
        params: dict[str, str] = {
            "api_token": self._api_key,
            "perPage": str(per_page),
            "page": str(page),
        }
        if name:
            params["name"] = name
        if imdb_id is not None:
            params["imdbId"] = str(imdb_id)
        if tvdb_id is not None:
            params["tvdbId"] = str(tvdb_id)
        if tmdb_id is not None:
            params["tmdbId"] = str(tmdb_id)
        if season is not None:
            params["seasonNumber"] = str(season)
        if episode is not None:
            params["episodeNumber"] = str(episode)
        if categories:
            for i, cat_id in enumerate(categories):
                params[f"categories[{i}]"] = str(cat_id)

        try:
            resp = await self._client.get("/filter", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", data) if isinstance(data, dict) else data
        except httpx.HTTPError:
            log.exception("UTP API request failed")
            return []

    async def get_by_id(self, torrent_id: str) -> dict | None:
        try:
            resp = await self._client.get(f"/{torrent_id}", params={"api_token": self._api_key})
            resp.raise_for_status()
            return transform_utp_item(resp.json())
        except httpx.HTTPError:
            log.exception("UTP get_by_id failed for id=%s", torrent_id)
            return None

    async def close(self) -> None:
        await self._client.aclose()


def transform_utp_item(item: dict) -> dict:
    """Transform a raw UTP API response item into a normalised dict
    suitable for Torznab RSS building. Keys match DB row field names.
    """
    from datetime import datetime

    attrs = item["attributes"]
    is_tv = attrs["category"] == "TV"
    release = parse_release(attrs["name"], is_tv)

    quality = _TYPE_TO_QUALITY.get(attrs.get("type", ""), Quality.UNKNOWN)
    resolution = _RESOLUTION_MAP.get(attrs.get("resolution", ""), Resolution.UNKNOWN)

    audio_types: list[AudioType] = []
    audio_sources: list[AudioSource] = []
    audio_langs: list[Lang] = []
    subtitle_langs: list[Lang] = []

    mi_text = attrs.get("media_info")
    if mi_text:
        mi = parse_mediainfo(mi_text)
        audio_types, audio_sources, audio_langs = parse_audio_tracks(mi)
        subtitle_langs = parse_subtitle_langs(mi)

    registered_at = None
    created_at_str = attrs.get("created_at")
    if created_at_str:
        try:
            registered_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            pass

    return {
        "id": item["id"],
        "name": attrs["name"],
        "title": release["title"],
        "year": release["year"],
        "content_type": "tv" if is_tv else "movie",
        "season": release["season"],
        "last_episode": release["episode"],
        "season_complete": release["season"] is not None and release["episode"] is None,
        "quality": quality.value,
        "resolution": resolution.value,
        "codec": release["codec"].value,
        "hdr": release["hdr"].value,
        "cut": release["cut"],
        "ratio": release["ratio"].value if release["ratio"] else None,
        "hybrid": release["hybrid"],
        "release_group": release["group"],
        "author": attrs.get("uploader"),
        "imdb_id": attrs.get("imdb_id"),
        "tvdb_id": attrs.get("tvdb_id"),
        "tmdb_id": attrs.get("tmdb_id"),
        "torrent_size": attrs.get("size", 0),
        "seeders": attrs.get("seeders", 0),
        "leechers": attrs.get("leechers", 0),
        "download_link": attrs.get("download_link"),
        "details_link": attrs.get("details_link"),
        "registered_at": registered_at,
        "grabs": attrs.get("times_completed", 0),
        "freeleech": attrs.get("freeleech"),
        "double_upload": attrs.get("double_upload", False),
        "featured": attrs.get("featured", False),
        # JSON-serialised to match DB row format used by naming.release_name()
        "audio_types": json.dumps(sorted(v.value for v in audio_types)),
        "audio_sources": json.dumps(sorted(v.name for v in audio_sources)),
        "audio_lang": json.dumps(sorted(v.value for v in audio_langs)),
        "subtitle_lang": json.dumps(sorted(v.value for v in subtitle_langs)),
    }
