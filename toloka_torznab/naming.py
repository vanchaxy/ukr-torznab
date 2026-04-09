from __future__ import annotations

import json
import re

_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

_SOURCE_MAP: dict[str, str] = {
    "sdtv": "SDTV",
    "webrip": "WEBRip",
    "webdl": "WEB-DL",
    "dvd": "DVDRip",
    "hdtv": "HDTV",
    "raw-hd": "Raw-HD",
    "raw_hd": "Raw-HD",
    "bluray": "BluRay",
    "remux": "BluRay-REMUX",
    "cam": "CAM",
    "telesync": "TS",
    "telecine": "TC",
    "dvdscr": "SCR",
    "dvd-r": "DVD-R",
    "dvd_r": "DVD-R",
    "br-disk": "BD",
    "br_disk": "BD",
}

_CODEC_MAP: dict[str, str] = {
    "H.264 / AVC": "x264",
    "H.265 / HEVC": "x265",
    "MPEG-4 Part 2": "MPEG-4",
    "MPEG-2": "MPEG-2",
    "MPEG-1": "MPEG-1",
    "VP9": "VP9",
    "VP8": "VP8",
    "AV1": "AV1",
    "VC-1 / WMV": "VC-1",
    # Legacy key kept for DB values written before enum rename
    "VC1 / WMV": "VC-1",
    "Unknown": "",
}

_AUDIO_TYPE_MAP: dict[str, str] = {
    "original": "ORIGINAL",
    "mvo": "MVO",
    "dvo": "DVO",
    "svo": "SVO",
    "dub": "DUB",
    "unknown": "",
}

_LANG_MAP: dict[str, str] = {
    "uk": "Ukrainian",
    "en": "English",
    "ru": "Russian",
    "es": "Spanish",
    "fr": "French",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "cs": "Czech",
    "sk": "Slovak",
    "bg": "Bulgarian",
    "ro": "Romanian",
    "hr": "Croatian",
    "sr": "Serbian",
    "sv": "Swedish",
    "da": "Danish",
    "fi": "Finnish",
    "no": "Norwegian",
    "hu": "Hungarian",
    "el": "Greek",
    "tr": "Turkish",
    "ar": "Arabic",
    "hi": "Hindi",
    "fa": "Persian",
    "id": "Indonesian",
    "is": "Icelandic",
    "et": "Estonian",
    "sl": "Slovenian",
    "mo": "Moldovan",
    "af": "Afrikaans",
    "th": "Thai",
    "none": "",
    "unknown": "",
}

# Display names for AudioSource enum values (stored as enum .name in DB)
_AUDIO_SOURCE_DISPLAY: dict[str, str] = {
    "INTER": "Inter",
    "K1": "K1",
    "NOVYI_KANAL": "NovyiKanal",
    "PLUS_PLUS": "PlusPlus",
    "TET": "TET",
    "NTN": "NTN",
    "ICTV": "ICTV",
    "TVI": "TVI",
    "UKRAINA": "Ukraina",
    "NLO_TV": "NloTV",
    "STB": "STB",
    "TWO_PLUS_TWO": "2plus2",
    "ONE_PLUS_ONE": "1plus1",
    "PIXEL": "Pixel",
    "PARAMOUNT_COMEDY": "ParamountComedy",
    "AMC": "AMC",
    "VOLYA_CINE_PLUS": "VolyaCinePlus",
    "VOLYA_CINE_PLUS_KIDS_HD": "VolyaKidsHD",
    "SUSPILNE_KULTURA": "SuspilneKultura",
    "TVOYE_KINO_RELAX_HD": "TvoyeKino",
    "HUMOR_TB": "HumorTV",
    "UAFLIX": "UAFlix",
    "MEGOGO": "Megogo",
    "HBO_MAX": "HBOMax",
    "APPLE_TV": "AppleTV",
    "ORIGINAL_BLURAY": "OriginalBluRay",
    "ORIGINAL_DVD": "OriginalDVD",
    "V_ODNE_RYLO": "VOdneRylo",
    "HAIDA_MIKE": "GaidaMike",
    "SWEET_SOUND_STUDIO": "SweetSoundStudio",
    "YANIAM": "Yaniam",
    "DNIPROFILM": "DniproFilm",
    "TSIKAVA_IDEYA": "TsikavaIdeya",
    "MATSURA_UA": "MatsuraUA",
    "POSTMODERN": "Postmodern",
    "AND5": "And5",
    "LE_DOYEN": "LeDoyen",
    "TAK_TREBA_PRODUCTION": "TakTrebaProduction",
    "KINOTA": "KINOTA",
    "CLOVER_DUB": "CloverDUB",
    "GWEAN_AND_MASLINKA": "GweanMaslinka",
    "OMIKRON": "Omikron",
    "TEREVENI_STUDIO": "TereveniStudio",
    "VOLTS_48": "48Volts",
    "MARIAM_PROJECT": "MariAmProject",
    "NE_ZUPYNYAY_PRODUCTION": "NeZupynyay",
    "TRETYAKOFF": "Tretyakoff",
    "AAA_SOUND": "AAASound",
    "MELODIC_VOICE_STUDIO": "MelodicVoice",
    "DZUSKI": "Dzuski",
    "QUAM_PROJECT": "QuamProject",
    "SUB_AUTUMN": "SubAutumn",
    "UFDUB": "UFDUB",
    "STRUGACHKA": "Strugachka",
    "GURTOM_STUDIO": "GurtomStudio",
    "TRY_KRAPKY": "TryKrapky",
    "KOLODIY_TRAYLERIV": "KolodiyTrayleriv",
    "HERMAN_LUKYCH": "HermanLukych",
    "SIMPSONS_UA": "SimpsonsUA",
    "UKRDUB_NET": "UkrDubNet",
    "ARTHAUS_TRAFFIC": "ArthausTraffik",
    "KWA_SOUND_PRODUCTION": "KWASound",
    "AMANOGAWA": "Amanogawa",
    "GLASS_MOON": "GlassMoon",
    "FANVOX_UA": "FanvoxUA",
    "INARI": "Inari",
    "SHIWA": "ShiWa",
    "ENEYV": "Eneyv",
    "LOGOS71": "Logos71",
    "LINE_IN": "LineIn",
    "ROBOTA_GOLOSOM": "RobotaGolosom",
}


def _sanitize(name: str) -> str:
    return _UNSAFE_RE.sub("", name).strip()


def source_tag(quality: str | None) -> str:
    return _SOURCE_MAP.get(quality or "", "")


def codec_tag(codec: str | None) -> str:
    return _CODEC_MAP.get(codec or "", "")


def audio_tag(audio_types_json: str | None) -> str:
    """DUB+MVO or ORIGINAL etc. from JSON list of AudioType values."""
    if not audio_types_json:
        return ""
    tags = [_AUDIO_TYPE_MAP[t] for t in json.loads(audio_types_json) if _AUDIO_TYPE_MAP.get(t)]
    return "+".join(tags)


def locale_tag(audio_lang_json: str | None) -> str:
    """Audio language(s): Ukrainian+English etc."""
    if not audio_lang_json:
        return ""
    names = [_LANG_MAP[lc] for lc in json.loads(audio_lang_json) if _LANG_MAP.get(lc)]
    return "+".join(names)


def subtitle_tag(subtitle_lang_json: str | None) -> str:
    """Sub.Ukrainian or Sub.Ukrainian+English etc. Empty string if no subs."""
    if not subtitle_lang_json:
        return ""
    names = [_LANG_MAP[lc] for lc in json.loads(subtitle_lang_json) if _LANG_MAP.get(lc)]
    return f"Sub.{'+'.join(names)}" if names else ""


def audio_source_tag(audio_sources_json: str | None) -> str:
    """Studio/channel names: Postmodern+STB etc. from JSON list of AudioSource.name values."""
    if not audio_sources_json:
        return ""
    tags = [
        _AUDIO_SOURCE_DISPLAY.get(s, s) for s in json.loads(audio_sources_json) if s != "UNKNOWN"
    ]
    return "+".join(tags)


def _group_tag(row) -> str:
    """release_group with author as fallback, sanitized."""
    g = getattr(row, "release_group", None) or getattr(row, "author", None)
    return _sanitize(str(g)) if g else ""


def _build_parts(
    row,
    *,
    season: int | None = None,
    episode: int | None = None,
) -> list[str]:
    """Ordered name components without group suffix or ID.

    Format: Title Year [S##E##] Source Resolution VCodec AudioType AudioLang [Sub.SubLang] [Studio]
    """
    parts: list[str] = []

    if row.title:
        parts.append(_sanitize(row.title))

    if row.year:
        parts.append(str(row.year))

    if season is not None and episode is not None:
        parts.append(f"S{season:02d}E{episode:02d}")
    elif season is not None:
        parts.append(f"S{season:02d}")

    src = source_tag(getattr(row, "quality", None))
    if src:
        parts.append(src)

    res = getattr(row, "resolution", None)
    if res and res != "unknown":
        parts.append(res)

    cc = codec_tag(getattr(row, "codec", None))
    if cc:
        parts.append(cc)

    audio = audio_tag(getattr(row, "audio_types", None))
    if audio:
        parts.append(audio)

    locale = locale_tag(getattr(row, "audio_lang", None))
    if locale:
        parts.append(locale)

    sub = subtitle_tag(getattr(row, "subtitle_lang", None))
    if sub:
        parts.append(sub)

    studio = audio_source_tag(getattr(row, "audio_sources", None))
    if studio:
        parts.append(studio)

    return parts


def release_name(row) -> str:
    """Full tracker-style release name for Torznab RSS <title>.

    Includes S##E## for single episodes, S## for season packs.
    Ends with -Group-ID#### or -ID####.
    """
    season = getattr(row, "season", None)
    last_ep = getattr(row, "last_episode", None)
    season_complete = getattr(row, "season_complete", None)
    ep = last_ep if (season is not None and not season_complete and last_ep is not None) else None

    parts = _build_parts(row, season=season, episode=ep)
    base = " ".join(parts)
    group = _group_tag(row)
    release_id = getattr(row, "id", None)

    suffix = f"-{group}" if group else ""
    id_tag = f"-ID{release_id}" if release_id is not None else ""
    return f"{base}{suffix}{id_tag}"


def movie_folder(row) -> str:
    """Full tracker-style folder name, identical base to movie_filename.

    e.g. 'Inception 2010 BluRay 1080p x264 DUB Ukrainian Sub.Ukrainian Postmodern-author-ID12345'
    """
    parts = _build_parts(row)
    base = " ".join(parts)
    group = _group_tag(row)
    release_id = getattr(row, "id", None)

    suffix = f"-{group}" if group else ""
    id_tag = f"-ID{release_id}" if release_id is not None else ""
    return f"{base}{suffix}{id_tag}"


def tv_folder(row, *, seasons: set[int] | None = None) -> str:
    """Single-season: 'Title (Year) S01-ID12345'. Multi-season: 'Title (Year)-ID12345'."""
    title = _sanitize(row.title or "Unknown")
    year = f" ({row.year})" if row.year else ""
    season = getattr(row, "season", None)
    single = season is not None and (seasons is None or len(seasons) == 1)
    season_suffix = f" S{season:02d}" if single else ""
    release_id = getattr(row, "id", None)
    id_tag = f"-ID{release_id}" if release_id is not None else ""
    return f"{title}{year}{season_suffix}{id_tag}"


def movie_filename(row, ext: str) -> str:
    """Full movie filename. Base identical to movie_folder."""
    return f"{movie_folder(row)}{ext}"


def episode_filename(row, season: int, episode: int, ext: str) -> str:
    """Episode filename. No ID — ends with -Group if present.

    e.g. 'Game of Thrones 2011 S01E05 WEBRip 1080p x265 MVO Ukrainian Sub.Ukrainian STB-author.mkv'
    """
    parts = _build_parts(row, season=season, episode=episode)
    base = " ".join(parts)
    group = _group_tag(row)
    suffix = f"-{group}" if group else ""
    return f"{base}{suffix}{ext}"
