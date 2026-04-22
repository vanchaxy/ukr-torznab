import dataclasses
import hashlib
from pathlib import Path

from ukr_torznab.tasks.scraper.parse_topics.models import ParsedPage


def hash_video_files(files: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(str(f) for f in files):
        h.update(p.encode())
    return h.hexdigest()


def _normalise(val: object) -> str:
    if isinstance(val, (set, frozenset)):
        return repr(sorted(_normalise(v) for v in val))
    if isinstance(val, list):
        return repr(sorted(_normalise(v) for v in val))
    if isinstance(val, dict):
        return repr(sorted((_normalise(k), _normalise(v)) for k, v in val.items()))
    return repr(val)


def content_hash(page: ParsedPage) -> str:
    h = hashlib.sha256()
    for f in dataclasses.fields(page):
        if f.name == "content_hash":
            continue
        h.update(_normalise(getattr(page, f.name)).encode())
    return h.hexdigest()
