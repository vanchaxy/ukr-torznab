FROM python:3.13-slim AS builder

WORKDIR /app

COPY pyproject.toml .
COPY ukr_torznab/ ukr_torznab/

RUN pip install --no-cache-dir --prefix=/install .


FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY migrations/ migrations/
COPY ukr_torznab/ ukr_torznab/

CMD ["python", "-m", "ukr_torznab.main"]
