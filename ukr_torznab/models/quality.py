from enum import Enum


class Quality(Enum):
    UNKNOWN = "unknown"
    SDTV = "sdtv"
    WEBRIP = "webrip"
    WEBDL = "webdl"
    DVD = "dvd"
    HDTV = "hdtv"
    RAW_HD = "raw-hd"
    BLURAY = "bluray"
    REMUX = "remux"
    WORKPRINT = "workprint"
    CAM = "cam"
    TELESYNC = "telesync"
    TELECINE = "telecine"
    REGIONAL = "regional"
    DVDSCR = "dvdscr"
    DVD_R = "dvd-r"
    BR_DISK = "br-disk"

    def __str__(self):
        return SOURCE_MAP.get(self, "")


SOURCE_MAP: dict[Quality, str] = {
    Quality.SDTV: "SDTV",
    Quality.WEBRIP: "WEBRip",
    Quality.WEBDL: "WEB-DL",
    Quality.DVD: "DVD",
    Quality.HDTV: "HDTV",
    Quality.RAW_HD: "Raw-HD",
    Quality.BLURAY: "BluRay",
    Quality.REMUX: "BluRay REMUX",
    Quality.WORKPRINT: "WORKPRINT",
    Quality.CAM: "CAM",
    Quality.TELESYNC: "TS",
    Quality.TELECINE: "TC",
    Quality.REGIONAL: "REGIONAL",
    Quality.DVDSCR: "SCR",
    Quality.DVD_R: "DVD-R",
    Quality.BR_DISK: "BR-DISK",
}
