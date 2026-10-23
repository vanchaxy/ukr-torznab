FROM python:3.13-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml .
COPY ukr_torznab/ ukr_torznab/

RUN pip install --prefix=/install --no-compile .

RUN find /install -type d \( -name '__pycache__' -o -name 'tests' -o -name 'test' -o -name 'examples' \) -prune -exec rm -rf {} + \
 && find /install -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyi' -o -name '*.c' -o -name '*.h' \) -delete \
 && find /install -type f -name '*.so' -exec strip --strip-unneeded {} + 2>/dev/null || true


FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MALLOC_ARENA_MAX=2 \
    MALLOC_TRIM_THRESHOLD_=131072 \
    DATABASE_URL=sqlite+aiosqlite:////data/toloka.db

WORKDIR /app
RUN mkdir /data
VOLUME /data

COPY --from=builder /install /usr/local
COPY migrations/ migrations/
COPY ukr_torznab/ ukr_torznab/

CMD ["python", "-m", "ukr_torznab.main"]
