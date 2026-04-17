# toloka-torznab

A [Torznab](https://torznab.github.io/spec-1.3-draft/) indexer for [toloka.to](https://toloka.to) — a Ukrainian torrent tracker. Integrates with Sonarr, Radarr, and Prowlarr.

## Quick Start

```bash
cp .env.example .env
# Fill in TOLOKA_USERNAME and TOLOKA_PASSWORD in .env
docker compose up
```

Verify the API is running:

```bash
curl "http://localhost:8000/api?t=caps"
```

To add the indexer in Prowlarr: go to **Indexers → Add → Generic Torznab**, set the URL to `http://localhost:8000` and leave the API key blank.

---

## Prerequisites

**Docker Compose (recommended):** Docker 24+ with Compose v2.

**Local dev:** Python 3.13, plus `libtorrent` available as a system package or wheel (see [libtorrent docs](https://libtorrent.org/python_binding.html)).

---

## Components

toloka.to is a Ukrainian tracker focused on Ukrainian-language content: films, TV series, and documentaries with Ukrainian dubbing, voice-over, or subtitles. This project makes its catalogue searchable through the standard Torznab API that Sonarr, Radarr, and Prowlarr understand.

The project has three components that run as a single process:

### 1. Scraper

Continuously monitors and indexes all torrent releases from toloka.to.

**What it does:**
- Fetches the topic list from all relevant categories (Ukrainian dub, Ukrainian subs, HD Ukrainian, etc.)
- Downloads the HTML page and `.torrent` file for each topic
- Parses each release to extract:
  - Video files and episode mapping (`S##E##`)
  - Quality: source (BluRay, WEB-DL, WEBRip…), resolution, video codec
  - Audio: voiceover type (DUB, MVO, DVO, SVO, ORIGINAL), language(s), dubbing studio/channel
  - Subtitle languages
  - IMDB ID (matched against a local IMDB titles database)
  - TVDB ID and series title/year via Skyhook (for TV)
  - Release group and uploader
- Stores everything in SQLite or PostgreSQL

**Tasks that run in parallel:**

| Task | Description |
|---|---|
| `CheckNewTopicsTask` | Polls toloka.to for new or updated torrents |
| `RefreshTopicsTask` | Periodically re-checks all known topics for seeder/size changes |
| `DownloadTopicsTask` | Downloads HTML + `.torrent` for topics that need (re-)parsing |
| `RefreshImdbTask` | Downloads and keeps the IMDB title database up to date |
| `ParseTopicsTask` | Parses downloaded pages into structured release records |

**Remote scraper (ElectricSQL sync):**

Running the full scraper requires toloka.to credentials, uses OpenAI API calls for title parsing, and downloads the full IMDB database. As an alternative, one person running the scraper with PostgreSQL can expose the database via [ElectricSQL](https://electric-sql.com/). Other users can then set `ELECTRIC_URL` to subscribe to that endpoint and receive pre-scraped data locally — without running the scraper themselves.

### 2. Torznab API

A FastAPI app that exposes the scraped data as a Torznab-compatible feed on port `8000`.

**Endpoints:**
- `GET /api?t=caps` — capabilities declaration
- `GET /api?t=search&q=...` — full-text search
- `GET /api?t=tvsearch&tvdbid=...&season=1&ep=5` — TV search with TVDB ID, season, episode
- `GET /api?t=movie&imdbid=tt1234567` — movie search by IMDB ID
- `GET /download/{download_id}` — proxies the `.torrent` file from toloka.to

**Release naming:**

All release titles follow a tracker-style format that Sonarr and Radarr can parse for quality detection:

```
Title Year [S##E##] Source Resolution VCodec AudioType AudioLang [Sub.SubLang] [Studio]-Group-ID#####
```

Examples:
```
The Bear 2022 S02E06 WEB-DL 1080p x265 DUB Ukrainian Sub.Ukrainian STB-username-ID98765
Dune 2021 BluRay 2160p x265 DUB+MVO Ukrainian+English Sub.Ukrainian Postmodern-author-ID12345
```

**Handling multi-season and incomplete season packs:**

toloka.to commonly uses rolling season packs (episodes added to an existing torrent over time) and multi-season packs. The API handles these as follows:

- **Multi-season pack** — treated as a single-season release using the season with the most files.
- **Incomplete season pack** — exposed as a single-episode release using the highest episode number present. This allows Sonarr to grab each updated version as new episodes are added.

### 3. Renamer

Renames files downloaded by qBittorrent to proper tracker-style names and resumes them.

**Workflow:**
1. Sonarr/Radarr are configured to add new downloads as **paused** in qBittorrent
2. `RenameTorrentsTask` polls qBittorrent every 60 seconds for paused torrents
3. It matches them against the `release` table by infohash (SHA1 → SHA256)
4. Files are renamed according to the naming scheme, then the torrent is resumed

**Naming rules:**
- **TV episodes** — each file renamed to `Title Year S##E## Source Resolution VCodec AudioType AudioLang Sub.SubLang Studio-Group.mkv`; torrent folder renamed to `Title (Year) S##-ID#####` (single season) or `Title (Year)-ID#####` (multi-season)
- **Movies** — file renamed to the full tracker name; folder (if present) gets the same base name without extension
- Files not found in the episode map (extras, samples) are left untouched

---

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and fill in the required values.

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | SQLAlchemy async URL — `sqlite+aiosqlite:///toloka.db` or `postgresql+asyncpg://...` |
| `TOLOKA_USERNAME` | Yes | toloka.to login |
| `TOLOKA_PASSWORD` | Yes | toloka.to password |
| `API_PORT` | No | Torznab API port (default: `8000`) |
| `ELECTRIC_URL` | No | ElectricSQL endpoint for remote scraper mode |
| `OPENAI_API_KEY` | No | Enables LLM-based episode mapping fallback during parsing |
| `QBITTORRENT_URL` | No | qBittorrent Web API URL — enables the renamer |
| `QBITTORRENT_USERNAME` | No | qBittorrent username (default: `admin`) |
| `QBITTORRENT_PASSWORD` | No | qBittorrent password (default: `adminadmin`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

`TOLOKA_USERNAME` and `TOLOKA_PASSWORD` have no defaults — the process exits immediately on startup if either is missing.

---

## Running with Docker Compose

The included `docker-compose.yml` starts the full stack with PostgreSQL and ElectricSQL.

```bash
cp .env.example .env
# Fill in TOLOKA_USERNAME and TOLOKA_PASSWORD
docker compose up
```

Docker Compose automatically loads `.env` from the working directory.

Services:
- **app** — scraper + Torznab API on port `8000`
- **postgres** — PostgreSQL 17 with logical replication enabled
- **electric** — ElectricSQL sync gateway on port `3000`
- **prowlarr** — Prowlarr on port `9696` for testing the indexer

---

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run with SQLite (no Docker required):

```bash
export DATABASE_URL=sqlite+aiosqlite:///toloka.db
export TOLOKA_USERNAME=your_username
export TOLOKA_PASSWORD=your_password
python -m ukr_torznab.main
```

Lint and type-check:

```bash
ruff check .
mypy .
```

---

## Architecture

Data flows through four stages:

```
CheckNew/Refresh ──► DownloadTopics ──► ParseTopics ──► Torznab API
     (poll tracker         (fetch HTML          (extract title,       (serve RSS
      for new/updated       + .torrent           quality, episodes,     to Sonarr/
      topic IDs)            per topic)           IMDB/TVDB IDs)        Radarr)
```

Each stage is an async background task. `CheckNew` and `Refresh` write topic IDs that need downloading; `Download` writes raw HTML and torrent bytes; `Parse` converts those into structured `release` rows that the API queries.

**ElectricSQL consumer mode:** if `ELECTRIC_URL` is set, the first three stages are replaced by `ElectricConsumerTask`, which subscribes to a remote PostgreSQL database over the ElectricSQL sync protocol and writes the same `release` rows locally. This lets users run only the API without toloka.to credentials or OpenAI access.

---

## Database Schema

| Table | Purpose |
|---|---|
| `topic` | Raw torrent metadata from toloka.to (name, size, seeders, hash) |
| `page` | Downloaded HTML and `.torrent` binary for each topic |
| `release` | Parsed release data — the join point for all API queries: title, year, IMDB/TVDB IDs, quality, codec, audio, episode map |
| `imdb_titles` | Local IMDB title database used for ID matching during parsing |
| `skyhook` | Cached Skyhook responses (TVDB series metadata) |
| `electric_offset` | Resume offsets for ElectricSQL shape subscriptions |
