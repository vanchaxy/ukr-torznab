FROM python:3.13-slim AS builder

WORKDIR /app

COPY pyproject.toml .
COPY toloka_torznab/ toloka_torznab/

RUN pip install --no-cache-dir --prefix=/install .


FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY migrations/ migrations/
COPY toloka_torznab/ toloka_torznab/

CMD ["python", "-m", "toloka_torznab.main"]
