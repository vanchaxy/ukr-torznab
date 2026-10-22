# CLAUDE.md

Torznab indexer for toloka.to (Ukrainian tracker), plus a utp.to proxy and a qBittorrent renamer.
Everything runs in one asyncio process: FastAPI/uvicorn plus background tasks. See README.md for user-facing docs.

## Commands

```bash
pip install -e ".[dev]"                 # or use .venv/bin/python
ruff check .                            # lint (notebooks excluded)
ruff format ukr_torznab                 # format, line length 100
mypy ukr_torznab                        # should report no errors
DATABASE_URL=sqlite+aiosqlite:///toloka.db TOLOKA_USERNAME=... TOLOKA_PASSWORD=... \
  python -m ukr_torznab.main            # run; applies Alembic migrations on start
docker compose up                       # dev stack: postgres, electric, sonarr, prowlarr
```

There is no test suite. Verify changes against a local SQLite DB (see "Verifying changes").
`settings.py` reads `DATABASE_URL`, `TOLOKA_USERNAME` and `TOLOKA_PASSWORD` at import time, so set dummy values
for any script that imports the package.

## Layout

- `main.py`: wiring only. Optional features (UTP, Electric, qBittorrent, OpenAI) are imported lazily and
  their clients are closed through an `AsyncExitStack`.
- `settings.py`: every env var and the toloka category list. Add new config here, not via `os.environ` elsewhere.
- `api/`: `search.py` holds the shared `search_params` dependency and the RSS builder. `toloka.py`/`utp.py` are
  thin routers.
- `clients/`: one class per external service. `_http.make_client` builds rate-limited httpx clients.
  `_cache.py` is the DB-backed TTL cache for Skyhook/Servarr lookups.
- `db/`: SQLAlchemy Core (no ORM). `tables.py` is the schema, `queries.py` holds all non-trivial SQL plus
  `PARSER_VERSION`, and `upsert.py` provides the cross-dialect upsert.
- `models/`: enums with display strings (`__str__` is used in release names) and `Release`, which holds the naming
  rules shared by the API and the renamer.
- `tasks/`: `AbstractTask` subclasses that loop on `run_once()`. Use `interruptible_sleep()` and check
  `self.running` in long loops so shutdown stays fast.
  - `scraper/parse_topics/processor.py::process_single_page` is the parser entry point. It returns
    `ParsedPage` or `SkippedPage(reason)`. The detectors live in `metadata.py`, `extras.py`, `season.py`,
    `episodes.py` and `imdb.py`, and the string tables in `mappings.py`.
- `migrations/`: Alembic, hand-written.

## Rules

- **Parser output changes → bump `PARSER_VERSION`** in `db/queries.py`. That re-parses every page, so don't bump
  it for pure refactors. Check equivalence instead (see below).
- **Schema changes need a hand-written migration** in `migrations/versions/` (next `000N_` number).
  `env.py` uses `target_metadata=None`, so autogenerate doesn't work. Keep `db/tables.py` in sync by hand.
- **Support both SQLite and PostgreSQL.** Use `db.upsert.upsert(table, conn)` for upserts. Branch on
  `conn.engine.dialect.name` for dialect-specific SQL, as `_file_to_episode_matches` does.
- List-like `release` columns (`audio_types`, `audio_lang`, `file_to_episode`, …) are JSON text.
  `audio_sources` stores enum *names* (the values are `auto()`), and the other enum columns store `.value`.
- Mapping lists in `parse_topics/mappings.py` and `clients/utp/mappings.py` are sorted by key length
  (longest first) so the more specific match wins. The two studio tables match different inputs (toloka HTML vs
  UTP mediainfo titles), so don't merge them.
- Adding a new `AudioSource` also requires an entry in `AUDIO_SOURCE_DISPLAY`. `__str__` raises `KeyError` otherwise.
- Times are stored timezone-aware. Toloka shows Kyiv local time, so use `utils.KYIV_TZ`. `utils.EPOCH` is the
  "unknown date" placeholder.
- Version lives in `ukr_torznab/__init__.py`: an `rcN` suffix on branches, none on `main`. CI enforces this.

## Verifying changes

- Parser: run `process_single_page` over a sample of `page` rows from a local DB with stub
  Skyhook/Servarr clients that read the cached `skyhook`/`servarr` tables. Then compare `content_hash` (or the
  skip reason) between the old and new code.
- API: use `fastapi.testclient.TestClient(ukr_torznab.api.app)` with `app.state.engine` set. Search only returns
  topics with `observed_at` within the last 2 days, so bump that column in a scratch copy of the DB.
- Open local DBs read-only (`?mode=ro&immutable=1&uri=true`) or work on a copy. Never write to the user's
  `*.sqlite3` files.
