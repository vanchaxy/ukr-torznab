from __future__ import annotations

import json
import re

from toloka_torznab.enums import AudioSource, AudioType, CodecFamily, Lang, Quality

_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

_SOURCE_MAP: dict[Quality, str] = {
    Quality.SDTV: "SDTV",
    Quality.WEBRIP: "WEBRip",
    Quality.WEBDL: "WEB-DL",
    Quality.DVD: "DVDRip",
    Quality.HDTV: "HDTV",
    Quality.RAW_HD: "Raw-HD",
    Quality.BLURAY: "BluRay",
    Quality.REMUX: "BluRay-REMUX",
    Quality.CAM: "CAM",
    Quality.TELESYNC: "TS",
    Quality.TELECINE: "TC",
    Quality.DVDSCR: "SCR",
    Quality.DVD_R: "DVD-R",
    Quality.BR_DISK: "BD",
}

_CODEC_MAP: dict[CodecFamily, str] = {
    CodecFamily.AVC: "x264",
    CodecFamily.HEVC: "x265",
    CodecFamily.MPEG4: "MPEG-4",
    CodecFamily.MPEG2: "MPEG-2",
    CodecFamily.MPEG1: "MPEG-1",
    CodecFamily.VP9: "VP9",
    CodecFamily.VP8: "VP8",
    CodecFamily.AV1: "AV1",
    CodecFamily.VC1: "VC-1",
}

_AUDIO_TYPE_MAP: dict[AudioType, str] = {
    AudioType.MVO: "MVO",
    AudioType.DVO: "DVO",
    AudioType.SVO: "SVO",
    AudioType.DUB: "DUB",
}

# Full English words for audio languages — Sonarr's Contains checks
# pick these up as audio regardless of context, which is what we want.
_LANG_DISPLAY: dict[Lang, str] = {
    Lang.UKRAINIAN: "Ukrainian",
    Lang.ENGLISH: "English",
    Lang.RUSSIAN: "Russian",
    Lang.SPANISH: "Spanish",
    Lang.FRENCH: "French",
    Lang.CHINESE: "Chinese",
    Lang.JAPANESE: "Japanese",
    Lang.KOREAN: "Korean",
    Lang.GERMAN: "German",
    Lang.ITALIAN: "Italian",
    Lang.DUTCH: "Dutch",
    Lang.POLISH: "Polish",
    Lang.PORTUGUESE: "Portuguese",
    Lang.CZECH: "Czech",
    Lang.SLOVAK: "Slovak",
    Lang.BULGARIAN: "Bulgarian",
    Lang.ROMANIAN: "Romanian",
    Lang.CROATIAN: "Croatian",
    Lang.SERBIAN: "Serbian",
    Lang.SWEDISH: "Swedish",
    Lang.DANISH: "Danish",
    Lang.FINNISH: "Finnish",
    Lang.NORWEGIAN: "Norwegian",
    Lang.HUNGARIAN: "Hungarian",
    Lang.GREEK: "Greek",
    Lang.TURKISH: "Turkish",
    Lang.ARABIC: "Arabic",
    Lang.HINDI: "Hindi",
    Lang.PERSIAN: "Persian",
    Lang.INDONESIAN: "Indonesian",
    Lang.ICELANDIC: "Icelandic",
    Lang.ESTONIAN: "Estonian",
    Lang.SLOVENIAN: "Slovenian",
    Lang.MOLDOVAN: "Moldovan",
    Lang.AFRIKAANS: "Afrikaans",
    Lang.THAI: "Thai",
    Lang.VIETNAMESE: "Vietnamese",
    Lang.HEBREW: "Hebrew",
    Lang.LITHUANIAN: "Lithuanian",
    Lang.MALAYALAM: "Malayalam",
    Lang.LATVIAN: "Latvian",
    Lang.CATALAN: "Catalan",
    Lang.BOSNIAN: "Bosnian",
    Lang.TAMIL: "Tamil",
    Lang.MACEDONIAN: "Macedonian",
}

# 3-letter codes for subtitle tags (ISO 639-2/B).
# Prefixed with "sub" (e.g. subUKR) so Sonarr's \b-anchored regex
# can't match the code as a standalone word → not detected as audio.
_LANG_CODE: dict[Lang, str] = {
    Lang.UKRAINIAN: "UKR",
    Lang.ENGLISH: "ENG",
    Lang.RUSSIAN: "RUS",
    Lang.SPANISH: "SPA",
    Lang.FRENCH: "FRE",
    Lang.CHINESE: "CHI",
    Lang.JAPANESE: "JPN",
    Lang.KOREAN: "KOR",
    Lang.GERMAN: "GER",
    Lang.ITALIAN: "ITA",
    Lang.DUTCH: "DUT",
    Lang.POLISH: "POL",
    Lang.PORTUGUESE: "POR",
    Lang.CZECH: "CZE",
    Lang.SLOVAK: "SLO",
    Lang.BULGARIAN: "BUL",
    Lang.ROMANIAN: "ROM",
    Lang.CROATIAN: "HRV",
    Lang.SERBIAN: "SRP",
    Lang.SWEDISH: "SWE",
    Lang.DANISH: "DAN",
    Lang.FINNISH: "FIN",
    Lang.NORWEGIAN: "NOR",
    Lang.HUNGARIAN: "HUN",
    Lang.GREEK: "GRE",
    Lang.TURKISH: "TUR",
    Lang.ARABIC: "ARA",
    Lang.HINDI: "HIN",
    Lang.PERSIAN: "PER",
    Lang.INDONESIAN: "IND",
    Lang.ICELANDIC: "ICE",
    Lang.ESTONIAN: "EST",
    Lang.SLOVENIAN: "SLV",
    Lang.MOLDOVAN: "MOL",
    Lang.AFRIKAANS: "AFR",
    Lang.THAI: "THA",
    Lang.VIETNAMESE: "VIE",
    Lang.HEBREW: "HEB",
    Lang.LITHUANIAN: "LIT",
    Lang.MALAYALAM: "MAL",
    Lang.LATVIAN: "LAV",
    Lang.CATALAN: "CAT",
    Lang.BOSNIAN: "BOS",
    Lang.TAMIL: "TAM",
    Lang.MACEDONIAN: "MAC",
}

_AUDIO_SOURCE_DISPLAY: dict[AudioSource, str] = {
    AudioSource.INTER: "Inter",
    AudioSource.K1: "K1",
    AudioSource.NOVYI_KANAL: "NovyiKanal",
    AudioSource.PLUS_PLUS: "PlusPlus",
    AudioSource.TET: "TET",
    AudioSource.NTN: "NTN",
    AudioSource.ICTV: "ICTV",
    AudioSource.TVI: "TVI",
    AudioSource.UKRAINA: "Ukraina",
    AudioSource.NLO_TV: "NloTV",
    AudioSource.STB: "STB",
    AudioSource.TWO_PLUS_TWO: "2plus2",
    AudioSource.ONE_PLUS_ONE: "1plus1",
    AudioSource.PIXEL: "Pixel",
    AudioSource.PARAMOUNT_COMEDY: "ParamountComedy",
    AudioSource.AMC: "AMC",
    AudioSource.VOLYA_CINE_PLUS: "VolyaCinePlus",
    AudioSource.VOLYA_CINE_PLUS_KIDS_HD: "VolyaKidsHD",
    AudioSource.SUSPILNE_KULTURA: "SuspilneKultura",
    AudioSource.TVOYE_KINO_RELAX_HD: "TvoyeKino",
    AudioSource.HUMOR_TB: "HumorTV",
    AudioSource.UAFLIX: "UAFlix",
    AudioSource.MEGOGO: "Megogo",
    AudioSource.HBO_MAX: "HBOMax",
    AudioSource.APPLE_TV: "AppleTV",
    AudioSource.ORIGINAL_BLURAY: "OriginalBluRay",
    AudioSource.ORIGINAL_DVD: "OriginalDVD",
    AudioSource.V_ODNE_RYLO: "VOdneRylo",
    AudioSource.HAIDA_MIKE: "GaidaMike",
    AudioSource.SWEET_SOUND_STUDIO: "SweetSoundStudio",
    AudioSource.YANIAM: "Yaniam",
    AudioSource.DNIPROFILM: "DniproFilm",
    AudioSource.TSIKAVA_IDEYA: "TsikavaIdeya",
    AudioSource.MATSURA_UA: "MatsuraUA",
    AudioSource.POSTMODERN: "Postmodern",
    AudioSource.AND5: "And5",
    AudioSource.LE_DOYEN: "LeDoyen",
    AudioSource.TAK_TREBA_PRODUCTION: "TakTrebaProduction",
    AudioSource.KINOTA: "KINOTA",
    AudioSource.CLOVER_DUB: "CloverDUB",
    AudioSource.GWEAN_AND_MASLINKA: "GweanMaslinka",
    AudioSource.OMIKRON: "Omikron",
    AudioSource.TEREVENI_STUDIO: "TereveniStudio",
    AudioSource.VOLTS_48: "48Volts",
    AudioSource.MARIAM_PROJECT: "MariAmProject",
    AudioSource.NE_ZUPYNYAY_PRODUCTION: "NeZupynyay",
    AudioSource.TRETYAKOFF: "Tretyakoff",
    AudioSource.AAA_SOUND: "AAASound",
    AudioSource.MELODIC_VOICE_STUDIO: "MelodicVoice",
    AudioSource.DZUSKI: "Dzuski",
    AudioSource.QUAM_PROJECT: "QuamProject",
    AudioSource.SUB_AUTUMN: "SubAutumn",
    AudioSource.UFDUB: "UFDUB",
    AudioSource.STRUGACHKA: "Strugachka",
    AudioSource.GURTOM_STUDIO: "GurtomStudio",
    AudioSource.TRY_KRAPKY: "TryKrapky",
    AudioSource.KOLODIY_TRAYLERIV: "KolodiyTrayleriv",
    AudioSource.HERMAN_LUKYCH: "HermanLukych",
    AudioSource.SIMPSONS_UA: "SimpsonsUA",
    AudioSource.UKRDUB_NET: "UkrDubNet",
    AudioSource.ARTHAUS_TRAFFIC: "ArthausTraffik",
    AudioSource.KWA_SOUND_PRODUCTION: "KWASound",
    AudioSource.AMANOGAWA: "Amanogawa",
    AudioSource.GLASS_MOON: "GlassMoon",
    AudioSource.FANVOX_UA: "FanvoxUA",
    AudioSource.INARI: "Inari",
    AudioSource.SHIWA: "ShiWa",
    AudioSource.ENEYV: "Eneyv",
    AudioSource.LOGOS71: "Logos71",
    AudioSource.LINE_IN: "LineIn",
    AudioSource.ROBOTA_GOLOSOM: "RobotaGolosom",
}

# Reverse lookup dicts keyed by the .value / .name strings stored in the DB
_SOURCE_MAP_BY_VALUE = {k.value: v for k, v in _SOURCE_MAP.items()}
_CODEC_MAP_BY_VALUE = {k.value: v for k, v in _CODEC_MAP.items()}
_AUDIO_TYPE_MAP_BY_VALUE = {k.value: v for k, v in _AUDIO_TYPE_MAP.items()}
_LANG_DISPLAY_BY_VALUE = {k.value: v for k, v in _LANG_DISPLAY.items()}
_LANG_CODE_BY_VALUE = {k.value: v for k, v in _LANG_CODE.items()}
_AUDIO_SOURCE_MAP_BY_NAME = {k.name: v for k, v in _AUDIO_SOURCE_DISPLAY.items()}


def _sanitize(name: str) -> str:
    return _UNSAFE_RE.sub("", name).strip()


def source_tag(quality: str | None) -> str:
    return _SOURCE_MAP_BY_VALUE.get(quality or "", "")


def codec_tag(codec: str | None) -> str:
    return _CODEC_MAP_BY_VALUE.get(codec or "", "")


def audio_tag(audio_types_json: str | None) -> str:
    """DUB+MVO or ORIGINAL etc. from JSON list of AudioType values."""
    if not audio_types_json:
        return ""
    tags = [
        _AUDIO_TYPE_MAP_BY_VALUE[t]
        for t in json.loads(audio_types_json)
        if _AUDIO_TYPE_MAP_BY_VALUE.get(t)
    ]
    return ".".join(tags)


def locale_tag(audio_lang_json: str | None) -> str:
    """Audio languages as full words: Ukrainian.English etc."""
    if not audio_lang_json:
        return ""
    names = [
        _LANG_DISPLAY_BY_VALUE[lc]
        for lc in json.loads(audio_lang_json)
        if _LANG_DISPLAY_BY_VALUE.get(lc)
    ]
    return ".".join(names)


def subtitle_tag(subtitle_lang_json: str | None) -> str:
    """Subtitle languages as subCODE tokens: subUKR.subENG etc.

    The "sub" prefix fuses with the 3-letter code into a single word,
    so Sonarr's \\b-anchored regex cannot match the code standalone
    and won't mis-detect subtitles as audio languages.
    """
    if not subtitle_lang_json:
        return ""
    tags = [
        f"sub{_LANG_CODE_BY_VALUE[lc]}"
        for lc in json.loads(subtitle_lang_json)
        if _LANG_CODE_BY_VALUE.get(lc)
    ]
    return ".".join(tags)


def audio_source_tag(audio_sources_json: str | None) -> str:
    """Studio/channel names: Postmodern+STB etc. from JSON list of AudioSource.name values."""
    if not audio_sources_json:
        return ""
    tags = [
        _AUDIO_SOURCE_MAP_BY_NAME.get(s, s)
        for s in json.loads(audio_sources_json)
        if s != "UNKNOWN"
    ]
    return ".".join(tags)


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

    Format: Title Year [S##E##] Source Resolution VCodec AudioType AudioLang [subLang] [Studio]
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

    suffix = f"-{group}" if group else ""
    return f"{base}{suffix}"


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

    e.g. 'Game of Thrones 2011 S01E05 WEBRip 1080p x265 MVO Ukrainian subUKR STB-author.mkv'
    """
    parts = _build_parts(row, season=season, episode=episode)
    base = " ".join(parts)
    group = _group_tag(row)
    suffix = f"-{group}" if group else ""
    return f"{base}{suffix}{ext}"
