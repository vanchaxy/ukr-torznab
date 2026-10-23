# toloka-torznab

A [Torznab](https://torznab.github.io/spec-1.3-draft/) indexer for [toloka.to](https://toloka.to), a Ukrainian torrent tracker. Works with Sonarr, Radarr and Prowlarr. It can also proxy [utp.to](https://utp.to) and rename finished downloads in qBittorrent.

## Quick Start

```bash
cp .env.example .env
# Fill in TOLOKA_USERNAME and TOLOKA_PASSWORD in .env
docker compose up
```

Check that the API is running:

```bash
curl "http://localhost:8000/toloka/api?t=caps"
```

To add the indexer in Prowlarr, go to **Indexers → Add → Generic Torznab**, set the URL to `http://localhost:8000/toloka` and leave the API key blank. For UTP, use `http://localhost:8000/utp`.

---

## Prerequisites

**Docker Compose (recommended):** Docker 24+ with Compose v2.

**Local dev:** Python 3.13. The `libtorrent` wheel from PyPI is enough on Linux x86_64. Elsewhere, see the [libtorrent docs](https://libtorrent.org/python_binding.html).

---

## Components

toloka.to focuses on Ukrainian-language content: films, TV series and documentaries with Ukrainian dubbing, voice-over or subtitles. This project makes its catalogue searchable through the standard Torznab API.

Everything runs in a single process: a FastAPI server plus a set of async background tasks.

### 1. Scraper

Continuously indexes toloka.to releases.

**What it does:**
- Fetches the topic lists for every category in `TOLOKA_CATEGORIES` (`ukr_torznab/settings.py`)
- Downloads the HTML page and the `.torrent` file for each topic
- Parses each release to extract:
  - IMDB ID, matched against a local copy of the IMDB `title.basics` dataset
  - TV: TVDB ID, series title/year and the episode list via Sonarr's Skyhook
  - Movies: TMDB ID and title/year via Radarr's metadata API
  - Season detection and file → `S##E##` mapping. A heuristic matcher runs first and an optional OpenAI fallback handles hard cases.
  - Quality (BluRay, WEB-DL, WEBRip…), resolution, video codec, HDR format, edition/cut, IMAX/Open Matte, hybrid
  - Audio type (DUB, MVO, DVO, SVO, original), audio and subtitle languages, dubbing studio/channel
  - Release group and uploader
- Stores everything in SQLite or PostgreSQL

**Background tasks:**

| Task | Description |
|---|---|
| `CheckNewTopicsTask` | Polls recently active categories every 10 minutes |
| `RefreshTopicsTask` | Re-walks every page of every category every ~10 hours (seeders, size, updates) |
| `DownloadTopicsTask` | Downloads HTML and `.torrent` for new or changed topics |
| `RefreshImdbTask` | Downloads the IMDB dataset and swaps it in atomically every 5 hours |
| `ParseTopicsTask` | Turns downloaded pages into `release` rows. Pages are re-parsed when they change or when `PARSER_VERSION` is bumped. |

### 2. Torznab API

A FastAPI app on port `8000` with one Torznab endpoint per tracker.

**Endpoints:**
- `GET /toloka/api?t=caps`: capabilities
- `GET /toloka/api?t=search&q=...`: full-text search over topic name and title
- `GET /toloka/api?t=tvsearch&tvdbid=...&season=1&ep=5`: TV search (`imdbid` also accepted)
- `GET /toloka/api?t=movie&imdbid=tt1234567`: movie search (`tmdbid` also accepted)
- `GET /toloka/download/{download_id}`: proxies the `.torrent` file from toloka.to with the scraper's session
- `GET /utp/api?...`: the same Torznab interface, backed by the utp.to API (requires `UTP_API_KEY`)
- `GET /toloka/info/{topic_id}`: JSON parser state for one topic (`ok`, `skipped` with reason, `pending`, `not_downloaded`, `not_indexed`) and the parsed release
- `GET /utp/info/{torrent_id}`: JSON parsed view of one UTP torrent, with per-audio-track detection and warnings (cached for 15 minutes)
- `GET /stats`: parse-stats dashboard. Cross-filter toloka topics by posting year, category, parse result/skip reason, quality, resolution, codec, audio, subtitles, warnings and more (data from `GET /stats/data`, cached for 5 minutes)

All search functions accept `cat`, `offset`, `limit` (max 100) and `xseed=1`. With `xseed=1` the release group suffix is dropped from titles, which helps cross-seed matching.

Only toloka topics seen on the tracker within the last 2 days are returned.

**Release naming:**

Titles use a scene-style format that Sonarr and Radarr can parse:

```
Title [Year|S##E##] [Cut] [IMAX] [Hybrid] Resolution Source Codec [HDR] AudioType AudioLangs [subXXX] [Studios]-Group
```

Examples:
```
The Bear S02E06 1080p WEB-DL H.265 DUB Ukrainian subUKR STB-username
Dune 2021 2160p BluRay H.265 HDR DUB.MVO English.Ukrainian subUKR Postmodern-group
```

**Season packs:**

toloka.to often uses rolling season packs, where episodes are added to an existing torrent over time. For a pack that is not marked complete, the feed shows an episode range (`S01E01-08`) built from the file → episode map. Sonarr then grabs the updated torrent as new episodes appear. Multi-season packs are skipped during parsing.

### 3. Renamer (optional)

Renames torrents downloaded by qBittorrent to the same scene-style names, then resumes them. It's enabled by setting `QBITTORRENT_URL`.

**Workflow:**
1. Configure Sonarr/Radarr to add downloads to qBittorrent as **stopped**, in one of the `QBITTORRENT_CATEGORIES`.
2. `RenameTorrentsTask` polls qBittorrent every 60 seconds for stopped torrents that don't carry the rename or rename-error tag yet.
3. Toloka torrents are matched to `release` rows by infohash (SHA256 of the SHA1 infohash). UTP torrents are looked up through the UTP API using the torrent comment URL.
4. The torrent, its files and its top folder are renamed. Then the torrent is tagged `QBITTORRENT_RENAME_TAG`, rechecked and started. On failure it is tagged `QBITTORRENT_RENAME_ERROR_TAG` and left alone.

**Naming rules:**
- **TV episodes:** each mapped file becomes `<episode release name>.<ext>`, and the folder becomes `<season release name> [<id>]-group`. Files missing from the episode map (extras, samples) are left untouched.
- **Movies:** the file gets the full release name, and the folder (if any) gets the release name with `[<id>]`.

### 4. ElectricSQL consumer mode (optional)

Running the scraper needs toloka.to credentials and the IMDB dataset, and optionally OpenAI. Instead, one instance can run the scraper on PostgreSQL and publish the `topic` and `release` tables through [ElectricSQL](https://electric-sql.com/). Other instances set `ELECTRIC_URL` and replace the scraper tasks with `ElectricConsumerTask`, which streams those tables into their local database. Toloka credentials are still required so `/toloka/download` can fetch `.torrent` files.

On the publishing side, set `CREATE_ELECTRIC_PUBLICATION=1` and `ELECTRIC_USER_PASSWORD` before the first migration. This creates the `electric_user` role and the publication.

### 5. Browser extension (optional)

`browser-extension/` is a Chrome (MV3) extension that shows the parser's view on the tracker pages, using the `/info` endpoints:

- toloka.to topic lists (`tracker.php`, `/fNN`) and utp.to/torrents: one line under each title with the release name, or why the topic was skipped or isn't indexed yet
- toloka.to topics and utp.to torrent pages: a panel with the release, cross-seed and folder names, ids, every detected attribute, the file → episode map and renamed files (TV), and the per-track audio detection (UTP)

Load it via `chrome://extensions` → Developer mode → **Load unpacked**. Set the indexer URL in the extension popup (default `http://localhost:8000`). See `browser-extension/README.md`.

---

## Configuration

All configuration comes from environment variables. Copy `.env.example` to `.env` and fill in the required values.

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | SQLAlchemy async URL, either `sqlite+aiosqlite:///toloka.db` or `postgresql+asyncpg://...` |
| `TOLOKA_USERNAME` | Yes | toloka.to login |
| `TOLOKA_PASSWORD` | Yes | toloka.to password |
| `API_PORT` | No | API port (default: `8000`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |
| `OPENAI_API_KEY` | No | Enables the LLM fallback for file → episode mapping |
| `UTP_API_KEY` | No | Enables the `/utp/api` proxy and renaming of UTP torrents |
| `ELECTRIC_URL` | No | ElectricSQL endpoint. Switches to consumer mode. |
| `CREATE_ELECTRIC_PUBLICATION` | No | PostgreSQL only. Creates the Electric role and publication during migration. |
| `ELECTRIC_USER_PASSWORD` | With the above | Password for `electric_user` |
| `QBITTORRENT_URL` | No | qBittorrent Web UI URL. Enables the renamer. |
| `QBITTORRENT_USERNAME` | No | default: `admin` |
| `QBITTORRENT_PASSWORD` | No | default: `adminadmin` |
| `QBITTORRENT_CATEGORIES` | No | Comma-separated categories to process (default: `tv,movies`) |
| `QBITTORRENT_RENAME_TAG` | No | Tag added after a successful rename (default: `renamed`) |
| `QBITTORRENT_RENAME_ERROR_TAG` | No | Tag added after a failed rename (default: `rename-error`) |

`DATABASE_URL`, `TOLOKA_USERNAME` and `TOLOKA_PASSWORD` have no defaults. The process fails on startup if any of them is missing.

Database migrations run automatically on startup.

---

## Running with Docker Compose

The included `docker-compose.yml` is a development stack:

- **app**: this project, installed from the working directory, on port `8000`
- **postgres**: PostgreSQL 17 with logical replication enabled
- **electric**: ElectricSQL sync gateway on port `3000`
- **sonarr** / **prowlarr**: on ports `8989` / `9696`, for testing the indexer end to end

Docker Compose loads `.env` from the working directory. To use PostgreSQL, set
`DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/toloka`.

A production image is built by `.github/workflows/docker-build-push.yml` and pushed to `ghcr.io`. The version in `ukr_torznab/__init__.py` must be an `rc` version on branches and a non-`rc` version on `main`.

---

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run with SQLite:

```bash
export DATABASE_URL=sqlite+aiosqlite:///toloka.db
export TOLOKA_USERNAME=your_username
export TOLOKA_PASSWORD=your_password
python -m ukr_torznab.main
```

Lint and type-check:

```bash
ruff check .
mypy ukr_torznab
```

---

## Architecture

```
CheckNew/Refresh ──► DownloadTopics ──► ParseTopics ──► Torznab API
 (poll tracker,        (fetch HTML        (IMDB/Skyhook/      (RSS for
  upsert topic rows)    + .torrent         Radarr lookups,     Sonarr/Radarr)
                        into page)         write release)
```

Each stage is an async background task that communicates only through the database. `topic` rows carry a hash of the listing fields, and a hash change triggers a re-download. A newer `page.downloaded_at` or a lower `release.parser_version` triggers a re-parse.

```
ukr_torznab/
  main.py            wiring: migrations, clients, tasks, uvicorn
  settings.py        env vars and toloka category list
  api/               FastAPI routers (/toloka, /utp), caps and RSS builders
  clients/           HTTP clients: toloka, skyhook, servarr, qbittorrent, utp, openai
  db/                SQLAlchemy Core tables, queries, cross-dialect upsert
  models/            enums (quality, codec, language, studio…) and the Release model with naming rules
  tasks/
    scraper/         check/refresh/download/imdb tasks
      parse_topics/  the page parser (processor.py is the entry point)
    renamer.py       qBittorrent renamer
    consumer.py      ElectricSQL consumer
migrations/          Alembic migrations (hand-written)
browser-extension/   Chrome extension showing parser output on toloka.to / utp.to
```

---

## Database Schema

| Table | Purpose |
|---|---|
| `topic` | Topic listing data from toloka.to (name, category, size, seeders, status, change hash) |
| `page` | Downloaded HTML and `.torrent` for each topic |
| `release` | Parsed release data that the API and renamer query. `result` is `ok` or a skip reason. |
| `imdb_titles` | Local IMDB title database used for ID matching |
| `skyhook` | Cached Skyhook responses (TVDB series metadata) |
| `servarr` | Cached Radarr metadata responses (TMDB movie metadata) |
| `electric_offset` | Resume offsets for ElectricSQL shape subscriptions |
