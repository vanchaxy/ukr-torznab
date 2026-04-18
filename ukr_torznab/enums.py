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
    AAA_SOUND = auto()
    ADRIAN_ZP = auto()
    AMANOGAWA = auto()
    AMC = auto()
    AND5 = auto()
    ANI_UA = auto()
    ARTHAUS_TRAFFIC = auto()
    ARTYMKO = auto()
    BAIBAKO = auto()
    CINEMAKER = auto()
    CINEMA_SOUND_PRODUCTION = auto()
    CINETYPE = auto()
    CLAN_KAIZOKU = auto()
    CLOVER_DUB = auto()
    COMEDY_CENTRAL = auto()
    DIDKO_STUDIO = auto()
    DIMUA = auto()
    DNIPROFILM = auto()
    DZUSKI = auto()
    ENEYV = auto()
    ENTER_FILM = auto()
    ENYKY_BENYKY = auto()
    FANVOX_UA = auto()
    GARNI_LUDY = auto()
    GLASS_MOON = auto()
    GURTOM_STUDIO = auto()
    GWEAN_AND_MASLINKA = auto()
    HAIDA_MIKE = auto()
    HBO_MAX = auto()
    HERMAN_LUKYCH = auto()
    HIVENTY = auto()
    HUMOR_TB = auto()
    ICTV = auto()
    INARI = auto()
    INDIGO = auto()
    INTER = auto()
    ITUNES = auto()
    K1 = auto()
    KINO = auto()
    KINOTA = auto()
    KIOTO_ANIME = auto()
    KIT = auto()
    KOLODIY_TRAYLERIV = auto()
    KWA_SOUND_PRODUCTION = auto()
    KYIVSTAR_TV = auto()
    LE_DOYEN = auto()
    LINE_IN = auto()
    LOGOS71 = auto()
    MARIAM_PROJECT = auto()
    MATSURA_UA = auto()
    MAXWELL_KENNEDY = auto()
    MEGA_TV = auto()
    MEGOGO = auto()
    MELODIC_VOICE_STUDIO = auto()
    NETFLIX = auto()
    NE_ZUPYNYAY_PRODUCTION = auto()
    NLO_TV = auto()
    NOVYI_KANAL = auto()
    NTN = auto()
    OMIKRON = auto()
    ONE_PLUS_ONE = auto()
    ORIGINAL_BLURAY = auto()
    ORIGINAL_DVD = auto()
    OZZ_TV = auto()
    PARAMOUNT_COMEDY = auto()
    PERSHYI = auto()
    PIE_POST_PRODUCTION = auto()
    PIXEL = auto()
    PLUS_PLUS = auto()
    POSTMODERN = auto()
    QTV = auto()
    QUAM_PROJECT = auto()
    RAKUTEN = auto()
    ROBOTA_GOLOSOM = auto()
    SATURN_UNION = auto()
    SHIWA = auto()
    SIMPSONS_UA = auto()
    SLAVA_RADYK = auto()
    STARFALL = auto()
    STB = auto()
    STRUGACHKA = auto()
    STUDIO_15K3 = auto()
    SUB_AUTUMN = auto()
    SUNNYSIDERS = auto()
    SUSPILNE_KULTURA = auto()
    SWEET_SOUND_STUDIO = auto()
    TAK_TREBA_PRODUCTION = auto()
    TEREVENI_STUDIO = auto()
    TET = auto()
    TRETYAKOFF = auto()
    TRY_KRAPKY = auto()
    TSIKAVA_IDEYA = auto()
    TV5 = auto()
    TVI = auto()
    TVIY_PRODUCTION = auto()
    TVOYE_KINO_RELAX_HD = auto()
    TWO_PLUS_TWO = auto()
    UAFLIX = auto()
    UATEAM = auto()
    UAVOICE = auto()
    UFDUB = auto()
    UKRAINA = auto()
    UKRDUB_NET = auto()
    VHS_RECORD = auto()
    VOLTS_48 = auto()
    VOLYA_CINE_PLUS = auto()
    VOLYA_CINE_PLUS_KIDS_HD = auto()
    V_ODNE_RYLO = auto()
    YANIAM = auto()


class VideoFormat(Enum):
    SDR = "sdr"
    HDR = "hdr"
    HDR10_PLUS = "hdr10+"
    DV = "dv"
    DV_HDR = "dv-hdr"
    DV_HDR10_PLUS = "dv-hdr10+"
    HLG = "hlg"
    PQ10 = "pq10"


class AspectRatio(Enum):
    STANDARD = "standard"
    OPEN_MATTE = "open-matte"
    IMAX = "imax"


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
    VIETNAMESE = "vi"
    HEBREW = "he"
    LITHUANIAN = "lt"
    MALAYALAM = "ml"
    LATVIAN = "lv"
    CATALAN = "ca"
    BOSNIAN = "bs"
    TAMIL = "ta"
    MACEDONIAN = "mk"
    NONE = "none"
    UNKNOWN = "unknown"
