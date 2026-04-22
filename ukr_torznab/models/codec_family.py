from enum import Enum


class CodecFamily(Enum):
    AVC = "H.264 / AVC"
    HEVC = "H.265 / HEVC"
    MPEG4 = "MPEG-4 Part 2"
    MPEG2 = "MPEG-2"
    MPEG1 = "MPEG-1"
    VP9 = "VP9"
    VP8 = "VP8"
    AV1 = "AV1"
    VC1 = "VC-1 / WMV"
    UNKNOWN = "Unknown"

    def __str__(self):
        return CODEC_MAP.get(self, "")


CODEC_MAP: dict[CodecFamily, str] = {
    CodecFamily.AVC: "H.264",
    CodecFamily.HEVC: "H.265",
    CodecFamily.MPEG4: "MPEG-4",
    CodecFamily.MPEG2: "MPEG-2",
    CodecFamily.MPEG1: "MPEG-1",
    CodecFamily.VP9: "VP9",
    CodecFamily.VP8: "VP8",
    CodecFamily.AV1: "AV1",
    CodecFamily.VC1: "VC-1",
}
