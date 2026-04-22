import re
from typing import cast

from decancer_py import parse as decancer_parse

from ukr_torznab.models import (
    LANG_CODE_REVERSE,
    AudioSource,
    AudioType,
    CodecFamily,
    Lang,
    Quality,
    Resolution,
)
from ukr_torznab.tasks.scraper.parse_topics.mappings import (
    AUDIO_SOURCE_MAP,
    AUDIO_SOURCE_TITLES_MAP,
    AUDIO_TYPE_MAP,
    CODEC_MAP,
    LANG_MAP,
    QUALITY_BY_VALUE,
    QUALITY_STRINGS_SORTED,
)
from ukr_torznab.utils import clean_string


def detect_quality(text: str, name: str) -> Quality:
    # 1) look in the "якість:" field first
    for match_str in re.findall(r"якість:(.+?)\n", text):
        q = _match_quality_string(match_str)
        if q is not None:
            return q

    # 2) fall back to torrent name
    q = _match_quality_string(name)
    if q is not None:
        return q

    return Quality.UNKNOWN


def _match_quality_string(raw: str) -> Quality | None:
    normalised = str(decancer_parse(raw))
    for qs in QUALITY_STRINGS_SORTED:
        if str(decancer_parse(qs)) in normalised:
            return QUALITY_BY_VALUE[qs]
    return None


_RESOLUTION_RE = re.compile(r"(\d\s*(?:\d\s*){2,3})[xх×*-]\s*((?:\d\s*){2,3}\d)")


def detect_resolution(text: str, name: str) -> Resolution:
    name_lc = name.lower()
    if "2160" in name_lc:
        return Resolution.UHD_2160P
    if "1080" in name_lc:
        return Resolution.FHD_1080P
    if "720" in name_lc:
        return Resolution.HD_720P

    for line in re.findall(r"розмір кадру(.+)\n", text):
        matches = _RESOLUTION_RE.findall(line)
        if not matches:
            continue
        w_raw, h_raw = matches[0]
        w = int("".join(c for c in w_raw if c.isdigit()))
        h = int("".join(c for c in h_raw if c.isdigit()))
        if h > 3000 or w > 5000:
            continue
        if h >= 1600 or w >= 3800:
            return Resolution.UHD_2160P
        if h >= 900 or w >= 1900:
            return Resolution.FHD_1080P
        if h >= 650 or w >= 1260:
            return Resolution.HD_720P
        if h >= 576 or w >= 1000:
            return Resolution.SD_576P
        return Resolution.SD_480P

    return Resolution.UNKNOWN


_CODEC_RE = re.compile(
    r"(mpeg(?:-| )?(?:1|2|4|h)|ffdshow|dx50|wmv"
    r"|(?:x|х|h|н)\.?26(?:4|5)|xvid|avc|vc-1|divx|av1|hevc|vp9|vp8)",
    re.IGNORECASE,
)


def detect_codec(text: str, html_raw: str) -> CodecFamily:
    matches = re.findall(r"кодек:.*" + _CODEC_RE.pattern + r".*\n", text, re.IGNORECASE)
    if not matches:
        matches = _CODEC_RE.findall(clean_string(html_raw))
    if matches:
        return _normalise_codec(matches[0])
    return CodecFamily.UNKNOWN


def _normalise_codec(raw: str) -> CodecFamily:
    s = raw.lower().replace("н", "h").replace("х", "x")
    cleaned = re.sub(r"[^a-z0-9]", "", s)
    return CODEC_MAP.get(cleaned, CodecFamily.UNKNOWN)


_AUDIO_KEYWORDS = ("озвучення", "переклад", "мова", "аудіо")


def detect_audio_types(text: str) -> set[AudioType]:
    tracks: set[AudioType] = set()
    for kw in _AUDIO_KEYWORDS:
        if tracks:
            break
        for line in re.findall(rf"{kw}(.+)", text, re.IGNORECASE):
            for tag, atype in AUDIO_TYPE_MAP.items():
                if tag in line:
                    tracks.add(atype)
                    break
    return tracks or {AudioType.UNKNOWN}


def detect_audio_sources(html_lower: str, text: str) -> set[AudioSource]:
    found: set[AudioSource] = set()
    for tag, source in AUDIO_SOURCE_MAP:
        if tag in html_lower:
            found.add(source)
    title_rows = (
        re.findall(
            r"(?i)(?:Audio|Аудіо)(?:\s+#\d+)?(?:(?!(?:Text|Текст)(?:\s+#\d+)?)[\s\S])*?(?<!Комерційна.)(?:Title|Назва|Заголовок)\s*:\s*([^\r\n]+)",
            text,
        )
        + re.findall(r".*переклад:(.+)", text)
        + re.findall(r".*озвучення:(.+)", text)
    )
    for tag, source in AUDIO_SOURCE_TITLES_MAP:
        for row in title_rows:
            if re.findall(tag, row):
                found.add(source)
    return found


_ALLOW_GROUPS = {"hdm", "rgb", "dk"}
_BAN_REGEX = [
    "1080",
    "2160",
    "264",
    "265",
    "480",
    "576",
    "720",
    "^1plus1$",
    "^2xua$",
    "^\\d+$",
    "^amazon$",
    "^bdrip$",
    "^dlrip$",
    "^dnr$",
    "^dvdrip$",
    "^dvt$",
    "^extended$",
    "^fullscreen$",
    "^hdtvrip$",
    "^hybrid$",
    "^imax$",
    "^movie$",
    "^remastered$",
    "^s\\d+$",
    "^uh$",
    "^uncut$",
    "^unrated$",
    "eng",
    "ukr",
]


def detect_release_group(ti_name: str) -> str | None:
    candidates: list[str] = []
    candidates.extend(re.findall(r"-(\w+)(?:\.\w+)$", ti_name))
    candidates.extend(re.findall(r"\[(\w+)\](?:\.\w+)$", ti_name))
    candidates = [
        g
        for g in candidates
        if (len(g) > 3 or g in _ALLOW_GROUPS)
        and not any(re.findall(ban, g.lower()) for ban in _BAN_REGEX)
    ]
    return candidates[0] if candidates else None


_AUTHOR_DISALLOWED = re.compile(r"[^a-zа-яіїєґ0-9_-]+")


def detect_author(dom) -> str | None:
    author_raw = str(cast("list", dom.xpath('//span[@class="name"]//text()'))[0]).lower()
    return _AUTHOR_DISALLOWED.sub("", author_raw) or None


def _detect_single_lang(text: str) -> Lang:
    text_lower = text.lower()
    for substr, lang in LANG_MAP.items():
        if substr.lower() in text_lower:
            return lang
    return Lang.UNKNOWN


def detect_languages(text: str) -> tuple[set[Lang], set[Lang]]:
    audio_langs: set[Lang] = set()
    sub_langs: set[Lang] = set()

    for m in re.finditer(r"мова:\s*(.+)", text, re.IGNORECASE):
        raw = m.group(1)
        lang = _detect_single_lang(raw)

        before = text[: m.start()].lower()
        audio_pos = before.rfind("аудіо")
        sub_pos = before.rfind("субтитр")

        if sub_pos > audio_pos:
            sub_langs.add(lang)
        else:
            audio_langs.add(lang)

    return audio_langs, sub_langs


def resolve_original_lang(code: str | None) -> Lang | None:
    if not code:
        return None
    code = code.lower()
    if len(code) == 3:
        return LANG_CODE_REVERSE.get(code)
    try:
        return Lang(code)
    except ValueError:
        return None
