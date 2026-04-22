from enum import Enum


class VideoFormat(Enum):
    SDR = "sdr"
    HDR = "hdr"
    HDR10_PLUS = "hdr10+"
    DV = "dv"
    DV_HDR = "dv-hdr"
    DV_HDR10_PLUS = "dv-hdr10+"
    HLG = "hlg"
    PQ10 = "pq10"
