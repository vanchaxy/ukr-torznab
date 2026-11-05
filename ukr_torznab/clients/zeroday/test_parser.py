import os
from datetime import datetime
from pathlib import Path

# The parser reuses the Toloka detectors, whose package reads these settings on import.
for _name in ("DATABASE_URL", "TOLOKA_USERNAME", "TOLOKA_PASSWORD"):
    os.environ.setdefault(_name, "unused")

from ukr_torznab.clients.zeroday.parser import (
    SITE_TZ,
    ListRow,
    build_release,
    parse_list,
    parse_topic,
)
from ukr_torznab.models import (
    AudioSource,
    AudioType,
    ContentType,
    Lang,
    Resolution,
    VideoFormat,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _release(fixture: str, title: str, *, category: int = 16):
    topic = parse_topic((FIXTURES / f"{fixture}.html").read_text())
    assert topic is not None
    row = ListRow(
        id=1,
        category=category,
        title=title,
        size=1,
        seeders=1,
        leechers=0,
        grabs=0,
        added=datetime(2026, 11, 4, tzinfo=SITE_TZ),
        uploader="uploader",
        download_volume_factor="1",
    )
    return build_release(row, topic)


def test_list_page():
    rows = parse_list((FIXTURES / "browse.html").read_text())
    assert [r.id for r in rows] == [153313, 153312, 153311]
    first = rows[0]
    assert first.title == "Прайм-тайм / Primetime (2026) 1080p WEB-DL"
    assert first.category == 16
    assert first.size == int(8.44 * 2**30)
    assert (first.seeders, first.leechers, first.grabs) == (11, 2, 31)
    assert first.uploader == "FILIP"
    assert first.download_volume_factor == "0"  # gold: download not counted
    assert rows[2].content_type is ContentType.TV


def test_film_with_ukrainian_russian_and_english_audio():
    r = _release(
        "film_ua_ru_en",
        "Ідеальне Різдво для собаки / Идеальное собачье Рождество / "
        "A Dog's Perfect Christmas (2026) 1080p WEB-DL",
    )
    assert r.title == "A Dog's Perfect Christmas"
    assert r.year == 2026
    assert r.imdb_id == 38515310
    assert r.audio_lang == [Lang.UKRAINIAN, Lang.RUSSIAN, Lang.ENGLISH]
    assert r.audio_types == [AudioType.DUB, AudioType.ORIGINAL]
    assert r.audio_sources == [AudioSource.NETFLIX]
    assert Lang.UKRAINIAN in r.subtitle_lang
    assert r.release_name().startswith(
        "A Dog's Perfect Christmas 2026 1080p WEB-DL H.264 DUB Ukrainian.Russian.English"
    )


def test_4k_film():
    r = _release(
        "film_4k_ua_en",
        "Resident Evil: Оселя Зла / Resident Evil (2026) 2160p 4K WEB-DL HDR10+ Dolby Vision",
    )
    assert r.title == "Resident Evil"
    assert r.resolution is Resolution.UHD_2160P
    assert r.hdr is VideoFormat.DV_HDR10_PLUS
    assert r.audio_lang == [Lang.UKRAINIAN, Lang.ENGLISH]
    assert r.audio_sources == [AudioSource.LE_DOYEN]


def test_series_with_two_ukrainian_dubs():
    r = _release(
        "series_two_ua_dubs",
        "Спіймати Джиро / Get Jiro! (Сезон 1) Серія 1-6 | 1080p WEB-DL (DniproFilm, HBO Max)",
        category=30,
    )
    assert r.content_type is ContentType.TV
    assert r.title == "Get Jiro!"
    assert (r.season, r.min_episode, r.max_episode) == (1, 1, 6)
    assert r.audio_lang == [Lang.UKRAINIAN, Lang.ENGLISH]
    assert r.audio_types == [AudioType.MVO, AudioType.DVO, AudioType.ORIGINAL]


def test_russian_only_film_has_no_ukrainian_audio():
    r = _release("film_ru_only", "Курьер / Runner (2026) 1080p WEB-DL")
    assert r.audio_lang == [Lang.RUSSIAN, Lang.ENGLISH]


def test_old_topic_track_format():
    # "Аудио#1: Russian(многоголосый закадровый): 48 kHz, ..." from the early tracker years.
    r = _release(
        "old_film_ru_en",
        "Страх и ненависть в Лас-Вегасе / Fear and Loathing in Las Vegas (1998) 720p HD DVDRip",
    )
    assert r.audio_lang == [Lang.RUSSIAN, Lang.ENGLISH]
    assert AudioType.MVO in r.audio_types
