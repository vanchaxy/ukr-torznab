from __future__ import annotations

import json
import re
from typing import Any

from ukr_torznab.enums import AudioSource, AudioType, CodecFamily, Lang, Quality

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
    AudioSource.AAA_SOUND: "AAASound",
    AudioSource.ADRIAN_ZP: "AdrianZP",
    AudioSource.AMANOGAWA: "Amanogawa",
    AudioSource.AMC: "AMC",
    AudioSource.AND5: "And5",
    AudioSource.ANI_UA: "AniUA",
    AudioSource.ARTHAUS_TRAFFIC: "ArthouseTraffic",
    AudioSource.ARTYMKO: "ArtymKo",
    AudioSource.BAIBAKO: "BaibaKo",
    AudioSource.CINEMAKER: "Cinemaker",
    AudioSource.CINEMA_SOUND_PRODUCTION: "CinemaSoundProduction",
    AudioSource.CINETYPE: "CineType",
    AudioSource.CLAN_KAIZOKU: "Clan Kaizoku",
    AudioSource.CLOVER_DUB: "CloverDUB",
    AudioSource.COMEDY_CENTRAL: "СomedyСentral",
    AudioSource.DIDKO_STUDIO: "DidkoStudio",
    AudioSource.DIMUA: "DimUA",
    AudioSource.DNIPROFILM: "DniproFilm",
    AudioSource.DZUSKI: "Dzuski",
    AudioSource.ENEYV: "Eneyv",
    AudioSource.ENTER_FILM: "EnterFilm",
    AudioSource.ENYKY_BENYKY: "EnikiBeniki",
    AudioSource.FANVOX_UA: "FanVoxUA",
    AudioSource.GARNI_LUDY: "HarniLiudy",
    AudioSource.GLASS_MOON: "GlassMoon",
    AudioSource.GURTOM_STUDIO: "GurtomStudio",
    AudioSource.GWEAN_AND_MASLINKA: "GweanMaslinka",
    AudioSource.HAIDA_MIKE: "HaidaMike",
    AudioSource.HBO_MAX: "HBOMax",
    AudioSource.HERMAN_LUKYCH: "HermanLukych",
    AudioSource.HIVENTY: "Hiventy",
    AudioSource.HUMOR_TB: "HumorTV",
    AudioSource.ICTV: "ICTV",
    AudioSource.INARI: "Inari",
    AudioSource.INDIGO: "Indigo",
    AudioSource.INTER: "Inter",
    AudioSource.ITUNES: "iTunes",
    AudioSource.K1: "K1",
    AudioSource.KINO: "Kino",
    AudioSource.KINOTA: "Kinota",
    AudioSource.KIOTO_ANIME: "KiotoAnime",
    AudioSource.KIT: "Kit",
    AudioSource.KOLODIY_TRAYLERIV: "KolodiyTrayleriv",
    AudioSource.KWA_SOUND_PRODUCTION: "KWASound",
    AudioSource.KYIVSTAR_TV: "KyivstarTV",
    AudioSource.LE_DOYEN: "LeDoyen",
    AudioSource.LINE_IN: "LineIn",
    AudioSource.LOGOS71: "Logos71",
    AudioSource.MARIAM_PROJECT: "MariAmProject",
    AudioSource.MATSURA_UA: "MatsuraUA",
    AudioSource.MAXWELL_KENNEDY: "MaxwellKennedy",
    AudioSource.MEGA_TV: "MegaTV",
    AudioSource.MEGOGO: "Megogo",
    AudioSource.MELODIC_VOICE_STUDIO: "MelodicVoice",
    AudioSource.NETFLIX: "Netflix",
    AudioSource.NE_ZUPYNYAY_PRODUCTION: "DontStopPoduction",
    AudioSource.NLO_TV: "NloTV",
    AudioSource.NOVYI_KANAL: "NovyiKanal",
    AudioSource.NTN: "NTN",
    AudioSource.OMIKRON: "Omikron",
    AudioSource.ONE_PLUS_ONE: "1plus1",
    AudioSource.ORIGINAL_BLURAY: "OriginalBluRay",
    AudioSource.ORIGINAL_DVD: "OriginalDVD",
    AudioSource.OZZ_TV: "OzzTV",
    AudioSource.PARAMOUNT_COMEDY: "ParamountComedy",
    AudioSource.PERSHYI: "Pershyi",
    AudioSource.PIE_POST_PRODUCTION: "PiePostProduction",
    AudioSource.PIXEL: "PixelTV",
    AudioSource.PLUS_PLUS: "PlusPlus",
    AudioSource.POSTMODERN: "Postmodern",
    AudioSource.QTV: "QTV",
    AudioSource.QUAM_PROJECT: "QuamProject",
    AudioSource.RAKUTEN: "Rakuten",
    AudioSource.ROBOTA_GOLOSOM: "RobotaGolosom",
    AudioSource.SATURN_UNION: "SaturnUnion",
    AudioSource.SHIWA: "Shiwa",
    AudioSource.SIMPSONS_UA: "SimpsonsUA",
    AudioSource.SLAVA_RADYK: "SlavaRadyk",
    AudioSource.STARFALL: "Starfall",
    AudioSource.STB: "STB",
    AudioSource.STRUGACHKA: "Strugachka",
    AudioSource.STUDIO_15K3: "15K3",
    AudioSource.SUB_AUTUMN: "SubAutumn",
    AudioSource.SUNNYSIDERS: "Іunnysiders",
    AudioSource.SUSPILNE_KULTURA: "SuspilneKultura",
    AudioSource.SWEET_SOUND_STUDIO: "SweetSoundStudio",
    AudioSource.TAK_TREBA_PRODUCTION: "TakTrebaProduction",
    AudioSource.TEREVENI_STUDIO: "TereveniStudio",
    AudioSource.TET: "TET",
    AudioSource.TRETYAKOFF: "Tretyakoff",
    AudioSource.TRY_KRAPKY: "TryKrapky",
    AudioSource.TSIKAVA_IDEYA: "TsikavaIdeya",
    AudioSource.TV5: "TV5",
    AudioSource.TVI: "TVI",
    AudioSource.TVIY_PRODUCTION: "ЕviyProduction",
    AudioSource.TVOYE_KINO_RELAX_HD: "TvoyeKino",
    AudioSource.TWO_PLUS_TWO: "2plus2",
    AudioSource.UAFLIX: "UAFlix",
    AudioSource.UATEAM: "UATeam",
    AudioSource.UAVOICE: "UAVoice",
    AudioSource.UFDUB: "UFDUB",
    AudioSource.UKRAINA: "Ukraina",
    AudioSource.UKRDUB_NET: "UkrDubNet",
    AudioSource.VHS_RECORD: "VHSRECORD",
    AudioSource.VOLTS_48: "48Volts",
    AudioSource.VOLYA_CINE_PLUS: "VolyaCinePlus",
    AudioSource.VOLYA_CINE_PLUS_KIDS_HD: "VolyaKidsHD",
    AudioSource.V_ODNE_RYLO: "VOdneRylo",
    AudioSource.YANIAM: "Yaniam",
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
    if not audio_types_json:
        return ""
    tags = [
        _AUDIO_TYPE_MAP_BY_VALUE[t]
        for t in json.loads(audio_types_json)
        if _AUDIO_TYPE_MAP_BY_VALUE.get(t)
    ]
    return ".".join(tags)


def locale_tag(audio_lang_json: str | None) -> str:
    if not audio_lang_json:
        return ""
    names = [
        _LANG_DISPLAY_BY_VALUE[lc]
        for lc in json.loads(audio_lang_json)
        if _LANG_DISPLAY_BY_VALUE.get(lc)
    ]
    return ".".join(names)


def subtitle_tag(subtitle_lang_json: str | None) -> str:
    if not subtitle_lang_json:
        return ""
    tags = [
        f"sub{_LANG_CODE_BY_VALUE[lc]}"
        for lc in json.loads(subtitle_lang_json)
        if _LANG_CODE_BY_VALUE.get(lc)
    ]
    return ".".join(tags)


def audio_source_tag(audio_sources_json: str | None) -> str:
    if not audio_sources_json:
        return ""
    tags = [
        _AUDIO_SOURCE_MAP_BY_NAME.get(s, s)
        for s in json.loads(audio_sources_json)
        if s != "UNKNOWN"
    ]
    return ".".join(tags)


def _group_tag(row: dict) -> str:
    g = row.get("release_group") or row.get("author")
    return _sanitize(str(g)) if g else ""


def _build_parts(
    row: dict,
    *,
    season: int | None = None,
    episode: int | None = None,
) -> list[str]:
    parts: list[str] = []

    if row.get("title"):
        parts.append(_sanitize(row["title"]))

    if season is not None and episode is not None:
        parts.append(f"S{season:02d}E{episode:02d}")
    elif season is not None:
        parts.append(f"S{season:02d}")

    if row.get("year"):
        parts.append(str(row["year"]))

    if row.get("cut"):
        parts.append(row["cut"])

    ratio = row.get("ratio")
    if ratio == "open-matte":
        parts.append("Open Matte")
    elif ratio == "imax":
        parts.append("IMAX")

    if row.get("hybrid"):
        parts.append("Hybrid")

    src = source_tag(row.get("quality"))
    if src:
        parts.append(src)

    res = row.get("resolution")
    if res and res != "unknown":
        parts.append(res)

    cc = codec_tag(row.get("codec"))
    if cc:
        parts.append(cc)

    hdr = row.get("hdr")
    if hdr and hdr != "sdr":
        parts.append(hdr.upper().replace("-", " "))

    audio = audio_tag(row.get("audio_types"))
    if audio:
        parts.append(audio)

    locale = locale_tag(row.get("audio_lang"))
    if locale:
        parts.append(locale)

    sub = subtitle_tag(row.get("subtitle_lang"))
    if sub:
        parts.append(sub)

    studio = audio_source_tag(row.get("audio_sources"))
    if studio:
        parts.append(studio)

    return parts


def release_name(row: dict) -> str:
    season = row.get("season")
    last_ep = row.get("last_episode")
    season_complete = row.get("season_complete")
    ep = last_ep if (season is not None and not season_complete and last_ep is not None) else None

    parts = _build_parts(row, season=season, episode=ep)
    base = " ".join(parts)
    group = _group_tag(row)
    return f"{base}-{group}" if group else base


def tv_folder(row: dict, *, seasons: list[int] | None = None) -> str:
    season = None
    if seasons and len(seasons) == 1:
        season = seasons[0]
    parts = _build_parts(row, season=season)
    base = " ".join(parts)
    group = _group_tag(row)
    return f"{base}-{group}" if group else base


def episode_filename(row: Any, season: int, episode: int, ext: str) -> str:
    parts = _build_parts(row, season=season, episode=episode)
    base = " ".join(parts)
    group = _group_tag(row)
    return f"{base}-{group}{ext}" if group else base
