from enum import Enum


class Resolution(Enum):
    UHD_2160P = "2160p"
    FHD_1080P = "1080p"
    HD_720P = "720p"
    SD_576P = "576p"
    SD_480P = "480p"
    UNKNOWN = "unknown"
