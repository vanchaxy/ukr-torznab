"""Parse 0day.community list and topic pages into releases.

0day titles never name the audio language, so the language, voice-over type and studio come
from the topic description, which lists one line per track:

    Звук #1: Український (Дубльований), E-AC-3, 5.1 ch, 640 кбіт/с |Netflix|
    Аудіо #2: Англійська (Оригінал), E-AC3 JOC, 6ch, 768 Кбіт/с
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from zoneinfo import ZoneInfo

from lxml import etree
from lxml.etree import _Element

from ukr_torznab.clients.utp.mappings import STUDIO_MAP
from ukr_torznab.models import (
    AudioSource,
    AudioType,
    ContentType,
    Lang,
    Release,
    Resolution,
    Tracker,
    VideoFormat,
)
from ukr_torznab.tasks.scraper.parse_topics.mappings import LANG_MAP
from ukr_torznab.tasks.scraper.parse_topics.metadata import (
    detect_codec,
    detect_quality,
    detect_resolution,
)

BASE_URL = "https://tracker.0day.community/"
SITE_TZ = ZoneInfo("Europe/Kyiv")

MOVIE_CATEGORIES = {10, 11, 16, 27, 28}
TV_CATEGORIES = {19, 29, 30}

_SIZE_UNITS = {"кб": 2**10, "мб": 2**20, "гб": 2**30, "тб": 2**40}
_FREELEECH = {"золото": "0", "срібло": "0.5", "серебро": "0.5"}


@dataclass(slots=True)
class ListRow:
    id: int
    category: int
    title: str
    size: int
    seeders: int
    leechers: int
    grabs: int
    added: datetime
    uploader: str | None
    download_volume_factor: str

    @property
    def content_type(self) -> ContentType:
        if self.category in TV_CATEGORIES or "сезон" in self.title.lower():
            return ContentType.TV
        return ContentType.MOVIE


def _int(text: str) -> int:
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else 0


def _size(text: str) -> int:
    m = re.search(r"([\d.,]+)\s*([кмгт]б)", text.lower())
    if not m:
        return 0
    return int(float(m.group(1).replace(",", ".")) * _SIZE_UNITS[m.group(2)])


def _xp(el: _Element, expr: str) -> list[Any]:
    return cast("list[Any]", el.xpath(expr))


def _str(el: _Element) -> str:
    return str(el.xpath("string()")).strip()


def parse_list(html: str) -> list[ListRow]:
    rows = []
    for tr in _xp(etree.HTML(html), '//tr[@class="rowtorrentinfo"]'):
        tds = _xp(tr, "./td")
        links = _xp(tr, './/a[starts-with(@href, "details.php?id=")]')
        cats = _xp(tr, './/a[starts-with(@href, "browse.php?cat=")]/@href')
        added = _xp(tr, './/i[@class="added"]/text()')
        if len(tds) < 7 or not links or not cats or not added:
            continue
        badge = "".join(_xp(tr, ".//td[2]//span/text()")).strip().lower()
        peers = _xp(tds[5], ".//a")
        rows.append(
            ListRow(
                id=_int(links[0].get("href").split("&")[0]),
                category=_int(cats[0]),
                title=_str(links[0]),
                size=_size(_str(tds[3])),
                seeders=_int(_str(peers[0])) if peers else 0,
                leechers=_int(_str(peers[1])) if len(peers) > 1 else 0,
                grabs=_int(_str(tds[4])),
                added=datetime.strptime(str(added[0]).strip(), "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=SITE_TZ,
                ),
                uploader=_str(tds[6]) or None,
                download_volume_factor=_FREELEECH.get(badge, "1"),
            ),
        )
    return rows


@dataclass(slots=True)
class AudioTrack:
    lang: Lang
    type: AudioType
    source: AudioSource | None


@dataclass(slots=True)
class Topic:
    imdb_id: int | None
    audio: list[AudioTrack]
    subtitles: list[Lang]
    text: str


# The stems cover the Ukrainian and Russian spellings 0day uploaders use; anything else goes
# through the Toloka language table.
_LANG_STEMS: list[tuple[str, Lang]] = [
    ("україн", Lang.UKRAINIAN),
    ("украин", Lang.UKRAINIAN),
    ("ukrain", Lang.UKRAINIAN),
    ("укр", Lang.UKRAINIAN),
    ("росій", Lang.RUSSIAN),
    ("русск", Lang.RUSSIAN),
    ("russian", Lang.RUSSIAN),
    ("рус", Lang.RUSSIAN),
    ("англ", Lang.ENGLISH),
    ("english", Lang.ENGLISH),
    ("польськ", Lang.POLISH),
    ("польск", Lang.POLISH),
]

_TYPE_STEMS: list[tuple[str, AudioType]] = [
    ("оригін", AudioType.ORIGINAL),
    ("оригин", AudioType.ORIGINAL),
    ("original", AudioType.ORIGINAL),
    ("дубл", AudioType.DUB),
    ("багатоголос", AudioType.MVO),
    ("многоголос", AudioType.MVO),
    ("двоголос", AudioType.DVO),
    ("двохголос", AudioType.DVO),
    ("двухголос", AudioType.DVO),
    ("одноголос", AudioType.SVO),
    ("авторськ", AudioType.SVO),
    ("авторск", AudioType.SVO),
]

# "Звук #1:", "Аудіо #2:", "Аудио#1:", "Звук рус:"; not "Аудио кодек:" or bare MediaInfo headers.
_TRACK_RE = re.compile(r"^(?:звук|аудіо|аудио)(?!\s*кодек)([^:\n]{0,12}):(.+)$", re.MULTILINE)
_SUBS_RE = re.compile(r"^(?:субтитри|субтитры)\s*:(.+)$", re.MULTILINE)
_IMDB_RE = re.compile(r"imdb\.com/title/tt(\d+)")


def _lang(text: str) -> Lang:
    for stem, lang in _LANG_STEMS:
        if stem in text:
            return lang
    for stem, lang in LANG_MAP.items():
        if stem in text:
            return lang
    return Lang.UNKNOWN


def _audio_type(text: str, lang: Lang) -> AudioType:
    for stem, audio_type in _TYPE_STEMS:
        if stem in text:
            return audio_type
    if lang not in (Lang.UKRAINIAN, Lang.UNKNOWN):
        return AudioType.ORIGINAL
    return AudioType.UNKNOWN


def _studio(text: str) -> AudioSource | None:
    for keyword, source in STUDIO_MAP:
        if keyword in text:
            return source
    return None


def _description(dom: _Element) -> _Element | None:
    cells = _xp(dom, '//td[normalize-space()="Описание"]/following-sibling::td[1]')
    return cells[0] if cells else None


def _text(el: _Element) -> str:
    for br in el.iter("br"):
        br.tail = "\n" + (br.tail or "")
    return "".join(str(t) for t in el.itertext()).replace("\xa0", " ").lower()


def parse_topic(html: str) -> Topic | None:
    """The description of a topic page, or None when the page has none (removed or no access)."""
    desc = _description(etree.HTML(html))
    if desc is None:
        return None
    text = _text(desc)

    audio = []
    for label, value in _TRACK_RE.findall(text):
        # The language is the first word of the value ("Український (...)") or, on old
        # topics, part of the label ("Звук рус:").
        head = value.strip().split(",")[0]
        lang = _lang(f"{label} {head}")
        studio = re.search(r"\|([^|]+)\|", value)
        audio.append(
            AudioTrack(
                lang=lang,
                type=_audio_type(head, lang),
                source=_studio(studio.group(1)) if studio else None,
            ),
        )

    subtitles: list[Lang] = []
    for line in _SUBS_RE.findall(text):
        for part in line.split(","):
            lang = _lang(part)
            if lang is not Lang.UNKNOWN and lang not in subtitles:
                subtitles.append(lang)

    imdb = _IMDB_RE.search(etree.tostring(desc, encoding="unicode"))
    return Topic(
        imdb_id=int(imdb.group(1)) if imdb else None,
        audio=audio,
        subtitles=subtitles,
        text=text,
    )


_YEAR_RE = re.compile(r"\((\d{4})\)")
_SEASON_RE = re.compile(r"сезони?\s*:?\s*(\d+)", re.IGNORECASE)
_EPISODES_RE = re.compile(
    r"(?:серії|серія|серии|серия|епізоди?)\s*:?\s*(\d+)(?:\s*-\s*(\d+))?", re.IGNORECASE
)
_TITLE_END_RE = re.compile(r"\(|\||\[|\b(?:19|20)\d{2}\b")


def _english_title(title: str) -> str:
    """The last " / " part before the year or season: the original (usually English) name."""
    m = _TITLE_END_RE.search(title)
    names = title[: m.start()] if m else title
    return names.split(" / ")[-1].strip(" -:")


def _hdr(title: str, text: str) -> VideoFormat:
    s = f"{title}\n{text}".lower()
    dv = "dolby vision" in s or re.search(r"\bdv\b", s) is not None
    if "hdr10+" in s:
        return VideoFormat.DV_HDR10_PLUS if dv else VideoFormat.HDR10_PLUS
    if "hdr" in s:
        return VideoFormat.DV_HDR if dv else VideoFormat.HDR
    return VideoFormat.DV if dv else VideoFormat.SDR


def _video_line(text: str) -> str:
    m = re.search(r"^(?:відео|видео)\s*:(.+)$", text, re.MULTILINE)
    return m.group(1) if m else ""


def build_release(row: ListRow, topic: Topic) -> Release:
    title = row.title
    video = _video_line(topic.text)
    year = _YEAR_RE.search(title)

    season = 1
    min_episode = max_episode = None
    season_complete = None
    if row.content_type is ContentType.TV:
        sm = _SEASON_RE.search(title)
        season = int(sm.group(1)) if sm else 1
        em = _EPISODES_RE.search(title)
        if em:
            min_episode = int(em.group(1))
            max_episode = int(em.group(2) or em.group(1))
        season_complete = em is None

    resolution = detect_resolution("", title)
    if resolution is Resolution.UNKNOWN:
        # The Toloka helper reads the frame size from a "розмір кадру" line; 0day has it in "Відео:".
        resolution = detect_resolution(f"розмір кадру {video}\n", title)

    audio_lang: list[Lang] = list(
        dict.fromkeys(t.lang for t in topic.audio if t.lang is not Lang.UNKNOWN)
    )
    return Release(
        id=row.id,
        tracker=Tracker.zeroday,
        name=title,
        content_type=row.content_type,
        title=_english_title(title),
        year=int(year.group(1)) if year else None,
        imdb_id=topic.imdb_id,
        season=season,
        min_episode=min_episode,
        max_episode=max_episode,
        season_complete=season_complete,
        torrent_size=row.size,
        quality=detect_quality(topic.text, title.lower()),
        resolution=resolution,
        codec=detect_codec(f"кодек: {video}\n", video),
        hdr=_hdr(title, video),
        audio_types=list(
            dict.fromkeys(t.type for t in topic.audio if t.type is not AudioType.UNKNOWN)
        ),
        audio_sources=list(
            dict.fromkeys(
                t.source for t in topic.audio if t.lang is Lang.UKRAINIAN and t.source is not None
            ),
        ),
        audio_lang=audio_lang,
        subtitle_lang=topic.subtitles,
        author=row.uploader,
        registered_at=row.added,
        seeders=row.seeders,
        leechers=row.leechers,
        grabs=row.grabs,
        download_link=f"download/{row.id}",
        details_link=f"{BASE_URL}details.php?id={row.id}",
        download_volume_factor=row.download_volume_factor,
    )
