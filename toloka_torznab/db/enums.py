"""Domain enumerations that define valid values stored in the database."""

from enum import Enum, auto


class SkipReason(Enum):
    """Why a page was not parsed into a release."""

    UNEXPECTED_PAGE_STRUCTURE = auto()
    INVALID_TORRENT = auto()
    DISALLOWED_FILE_EXTENSION = auto()
    NO_VIDEO_FILES = auto()
    NO_IMDB_LINK = auto()
    IMDB_NOT_IN_DATABASE = auto()
    TV_NO_SKYHOOK_METADATA = auto()
    MOVIE_NO_SERVARR_METADATA = auto()
    MOVIE_MULTIPLE_VIDEO_FILES = auto()
    INCONSISTENT_FOLDER_STRUCTURE = auto()
    CANNOT_DETERMINE_SEASON = auto()


class ContentType(Enum):
    MOVIE = "movie"
    TV = "tv"


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


class Resolution(Enum):
    UHD_2160P = "2160p"
    FHD_1080P = "1080p"
    HD_720P = "720p"
    SD_576P = "576p"
    SD_480P = "480p"
    UNKNOWN = "unknown"


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


class AudioType(Enum):
    ORIGINAL = "original"
    MVO = "mvo"  # multi-voice over (багатоголосий)
    DVO = "dvo"  # dual-voice over (двоголосий)
    SVO = "svo"  # single-voice over (одноголосий)
    DUB = "dub"  # professional / amateur dub
    UNKNOWN = "unknown"


class AudioSource(Enum):
    INTER = auto()
    K1 = auto()
    NOVYI_KANAL = auto()
    PLUS_PLUS = auto()
    TET = auto()
    NTN = auto()
    ICTV = auto()
    TVI = auto()
    UKRAINA = auto()
    NLO_TV = auto()
    STB = auto()
    TWO_PLUS_TWO = auto()
    ONE_PLUS_ONE = auto()
    PIXEL = auto()
    PARAMOUNT_COMEDY = auto()
    AMC = auto()
    VOLYA_CINE_PLUS = auto()
    VOLYA_CINE_PLUS_KIDS_HD = auto()
    SUSPILNE_KULTURA = auto()
    TVOYE_KINO_RELAX_HD = auto()
    HUMOR_TB = auto()
    UAFLIX = auto()
    MEGOGO = auto()
    HBO_MAX = auto()
    APPLE_TV = auto()
    ORIGINAL_BLURAY = auto()
    ORIGINAL_DVD = auto()
    V_ODNE_RYLO = auto()
    HAIDA_MIKE = auto()
    SWEET_SOUND_STUDIO = auto()
    YANIAM = auto()
    DNIPROFILM = auto()
    TSIKAVA_IDEYA = auto()
    MATSURA_UA = auto()
    POSTMODERN = auto()
    AND5 = auto()
    LE_DOYEN = auto()
    TAK_TREBA_PRODUCTION = auto()
    KINOTA = auto()
    CLOVER_DUB = auto()
    GWEAN_AND_MASLINKA = auto()
    OMIKRON = auto()
    TEREVENI_STUDIO = auto()
    VOLTS_48 = auto()
    MARIAM_PROJECT = auto()
    NE_ZUPYNYAY_PRODUCTION = auto()
    TRETYAKOFF = auto()
    AAA_SOUND = auto()
    MELODIC_VOICE_STUDIO = auto()
    DZUSKI = auto()
    QUAM_PROJECT = auto()
    SUB_AUTUMN = auto()
    UFDUB = auto()
    STRUGACHKA = auto()
    GURTOM_STUDIO = auto()
    TRY_KRAPKY = auto()
    KOLODIY_TRAYLERIV = auto()
    HERMAN_LUKYCH = auto()
    SIMPSONS_UA = auto()
    UKRDUB_NET = auto()
    ARTHAUS_TRAFFIC = auto()
    KWA_SOUND_PRODUCTION = auto()
    AMANOGAWA = auto()
    GLASS_MOON = auto()
    FANVOX_UA = auto()
    INARI = auto()
    SHIWA = auto()
    ENEYV = auto()
    LOGOS71 = auto()
    LINE_IN = auto()
    ROBOTA_GOLOSOM = auto()

    UNKNOWN = auto()


class Lang(Enum):
    UKRAINIAN = "uk"
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    CHINESE = "zh"
    THAI = "th"
    JAPANESE = "ja"
    KOREAN = "ko"
    GERMAN = "de"
    NORWEGIAN = "no"
    ITALIAN = "it"
    FINNISH = "fi"
    SERBIAN = "sr"
    DUTCH = "nl"
    SWEDISH = "sv"
    ROMANIAN = "ro"
    RUSSIAN = "ru"
    ARABIC = "ar"
    DANISH = "da"
    CROATIAN = "hr"
    POLISH = "pl"
    PORTUGUESE = "pt"
    CZECH = "cs"
    HINDI = "hi"
    ESTONIAN = "et"
    BULGARIAN = "bg"
    GREEK = "el"
    HUNGARIAN = "hu"
    MOLDOVAN = "mo"
    SLOVENIAN = "sl"
    TURKISH = "tr"
    PERSIAN = "fa"
    ICELANDIC = "is"
    SLOVAK = "sk"
    INDONESIAN = "id"
    AFRIKAANS = "af"
    NONE = "none"
    UNKNOWN = "unknown"
