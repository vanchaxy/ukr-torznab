from __future__ import annotations

import re

from toloka_torznab.enums import AspectRatio, VideoFormat

_HDR_ROW_RE = re.compile(
    r"(?:hdr.format|формат.hdr|commercial.name|комерційна.назва"
    r"|transfer.characteristics|характеристики.трансферу)(.+)",
    re.IGNORECASE,
)


def detect_hdr(text: str) -> VideoFormat:
    has_dv = False
    has_hdr10plus = False
    has_hdr10 = False
    has_hlg = False
    has_pq = False

    for val in _HDR_ROW_RE.findall(text):
        val = val.strip()
        if "dolby vision" in val or "dvhe" in val or "dvh1" in val:
            has_dv = True
        if "hdr10+" in val or "smpte st 2094" in val:
            has_hdr10plus = True
        if "hdr10" in val or "smpte st 2086" in val:
            has_hdr10 = True
        if "hlg" in val:
            has_hlg = True
        if re.search(r"\bpq\b", val) or "smpte st 2084" in val:
            has_pq = True

    if has_dv:
        if has_hdr10plus:
            return VideoFormat.DV_HDR10_PLUS
        if has_hdr10:
            return VideoFormat.DV_HDR
        return VideoFormat.DV
    if has_hdr10plus:
        return VideoFormat.HDR10_PLUS
    if has_hdr10:
        return VideoFormat.HDR
    if has_hlg:
        return VideoFormat.HLG
    if has_pq:
        return VideoFormat.PQ10
    return VideoFormat.SDR


_CUT_ALLOWED_PREFIXES = ("un", "re", "euro")
_CUT_TOKEN = rf"(?:\b(?:{'|'.join(_CUT_ALLOWED_PREFIXES)})?cut\b)"

_CUT_PATTERN = re.compile(
    rf"\[([^\[\]]*{_CUT_TOKEN}[^\[\]]*)\]"
    rf"|\(([^()]*{_CUT_TOKEN}[^()]*)\)"
    r"|((?:Theatrical|Extended|Director'?s|Unrated|Assembly|International|The Super Duper)\s+Cut)"
    r"|(Uncut Version)",
    re.IGNORECASE,
)
_CUT_SPLIT_RE = re.compile(r"\s*[,/|]\s*")


def _clean_cut(s: str) -> str:
    for p in _CUT_SPLIT_RE.split(s):
        if re.search(_CUT_TOKEN, p.lower()):
            p = p.strip()
            if re.search(r"\bdir", p, re.IGNORECASE):
                return "director's cut"
            return p
    return s.strip()


def detect_cut(name: str) -> str | None:
    for m in _CUT_PATTERN.finditer(name):
        inner = next(g for g in m.groups() if g)
        cut = _clean_cut(inner)
        if cut and cut != "theatrical cut":
            return cut
    return None


def detect_ratio(name: str) -> AspectRatio:
    if "IMAX" in name or "Imax" in name:
        return AspectRatio.IMAX
    if "open matte" in name.lower():
        return AspectRatio.OPEN_MATTE
    return AspectRatio.STANDARD


_HYBRID_RE = re.compile(r"(?:19|20)\d\d.+hybrid", re.IGNORECASE)


def detect_hybrid(name: str) -> bool:
    return bool(_HYBRID_RE.search(name))
