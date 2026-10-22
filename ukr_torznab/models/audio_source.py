from enum import Enum, auto


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

    def __str__(self):
        return AUDIO_SOURCE_DISPLAY[self]


AUDIO_SOURCE_DISPLAY: dict[AudioSource, str] = {
    AudioSource.AAA_SOUND: "AAASound",
    AudioSource.ADRIAN_ZP: "AdrianZP",
    AudioSource.AMANOGAWA: "Amanogawa",
    AudioSource.AMC: "AMC",
    AudioSource.AND5: "And5",
    AudioSource.ANI_UA: "AniUA",
    AudioSource.ARTHAUS_TRAFFIC: "ArthouseTraffic",
    AudioSource.ARTYMKO: "ArtymKo",
    AudioSource.BAIBAKO: "BaibaKo",
    AudioSource.CINEMAKER: "Cinemaker",
    AudioSource.CINEMA_SOUND_PRODUCTION: "CinemaSoundProduction",
    AudioSource.CINETYPE: "CineType",
    AudioSource.CLAN_KAIZOKU: "Clan Kaizoku",
    AudioSource.CLOVER_DUB: "CloverDUB",
    AudioSource.COMEDY_CENTRAL: "СomedyСentral",
    AudioSource.DIDKO_STUDIO: "DidkoStudio",
    AudioSource.DIMUA: "DimUA",
    AudioSource.DNIPROFILM: "DniproFilm",
    AudioSource.DZUSKI: "Dzuski",
    AudioSource.ENEYV: "Eneyv",
    AudioSource.ENTER_FILM: "EnterFilm",
    AudioSource.ENYKY_BENYKY: "EnikiBeniki",
    AudioSource.FANVOX_UA: "FanVoxUA",
    AudioSource.GARNI_LUDY: "HarniLiudy",
    AudioSource.GLASS_MOON: "GlassMoon",
    AudioSource.GURTOM_STUDIO: "GurtomStudio",
    AudioSource.GWEAN_AND_MASLINKA: "GweanMaslinka",
    AudioSource.HAIDA_MIKE: "HaidaMike",
    AudioSource.HBO_MAX: "HBOMax",
    AudioSource.HERMAN_LUKYCH: "HermanLukych",
    AudioSource.HIVENTY: "Hiventy",
    AudioSource.HUMOR_TB: "HumorTV",
    AudioSource.ICTV: "ICTV",
    AudioSource.INARI: "Inari",
    AudioSource.INDIGO: "Indigo",
    AudioSource.INTER: "Inter",
    AudioSource.ITUNES: "AppleTV",
    AudioSource.K1: "K1",
    AudioSource.KINO: "Kino",
    AudioSource.KINOTA: "Kinota",
    AudioSource.KIOTO_ANIME: "KiotoAnime",
    AudioSource.KIT: "Kit",
    AudioSource.KOLODIY_TRAYLERIV: "KolodiyTrayleriv",
    AudioSource.KWA_SOUND_PRODUCTION: "KWASound",
    AudioSource.KYIVSTAR_TV: "KyivstarTV",
    AudioSource.LE_DOYEN: "LeDoyen",
    AudioSource.LINE_IN: "LineIn",
    AudioSource.LOGOS71: "Logos71",
    AudioSource.MARIAM_PROJECT: "MariAmProject",
    AudioSource.MATSURA_UA: "MatsuraUA",
    AudioSource.MAXWELL_KENNEDY: "MaxwellKennedy",
    AudioSource.MEGA_TV: "MegaTV",
    AudioSource.MEGOGO: "Megogo",
    AudioSource.MELODIC_VOICE_STUDIO: "MelodicVoice",
    AudioSource.NETFLIX: "Netflix",
    AudioSource.NE_ZUPYNYAY_PRODUCTION: "DontStopPoduction",
    AudioSource.NLO_TV: "NloTV",
    AudioSource.NOVYI_KANAL: "NovyiKanal",
    AudioSource.NTN: "NTN",
    AudioSource.OMIKRON: "Omikron",
    AudioSource.ONE_PLUS_ONE: "1plus1",
    AudioSource.ORIGINAL_BLURAY: "OriginalBluRay",
    AudioSource.ORIGINAL_DVD: "OriginalDVD",
    AudioSource.OZZ_TV: "OzzTV",
    AudioSource.PARAMOUNT_COMEDY: "ParamountComedy",
    AudioSource.PERSHYI: "Pershyi",
    AudioSource.PIE_POST_PRODUCTION: "PiePostProduction",
    AudioSource.PIXEL: "PixelTV",
    AudioSource.PLUS_PLUS: "PlusPlus",
    AudioSource.POSTMODERN: "Postmodern",
    AudioSource.QTV: "QTV",
    AudioSource.QUAM_PROJECT: "QuamProject",
    AudioSource.RAKUTEN: "Rakuten",
    AudioSource.ROBOTA_GOLOSOM: "RobotaGolosom",
    AudioSource.SATURN_UNION: "SaturnUnion",
    AudioSource.SHIWA: "Shiwa",
    AudioSource.SIMPSONS_UA: "SimpsonsUA",
    AudioSource.SLAVA_RADYK: "SlavaRadyk",
    AudioSource.STARFALL: "Starfall",
    AudioSource.STB: "STB",
    AudioSource.STRUGACHKA: "Strugachka",
    AudioSource.STUDIO_15K3: "15K3",
    AudioSource.SUB_AUTUMN: "SubAutumn",
    AudioSource.SUNNYSIDERS: "Sunnysiders",
    AudioSource.SUSPILNE_KULTURA: "SuspilneKultura",
    AudioSource.SWEET_SOUND_STUDIO: "SweetSoundStudio",
    AudioSource.TAK_TREBA_PRODUCTION: "TakTrebaProduction",
    AudioSource.TEREVENI_STUDIO: "TereveniStudio",
    AudioSource.TET: "TET",
    AudioSource.TRETYAKOFF: "Tretyakoff",
    AudioSource.TRY_KRAPKY: "TryKrapky",
    AudioSource.TSIKAVA_IDEYA: "TsikavaIdeya",
    AudioSource.TV5: "TV5",
    AudioSource.TVI: "TVI",
    AudioSource.TVIY_PRODUCTION: "ЕviyProduction",
    AudioSource.TVOYE_KINO_RELAX_HD: "TvoyeKino",
    AudioSource.TWO_PLUS_TWO: "2plus2",
    AudioSource.UAFLIX: "UAFlix",
    AudioSource.UATEAM: "UATeam",
    AudioSource.UAVOICE: "UAVoice",
    AudioSource.UFDUB: "UFDUB",
    AudioSource.UKRAINA: "Ukraina",
    AudioSource.UKRDUB_NET: "UkrDubNet",
    AudioSource.VHS_RECORD: "VHSRECORD",
    AudioSource.VOLTS_48: "48Volts",
    AudioSource.VOLYA_CINE_PLUS: "VolyaCinePlus",
    AudioSource.VOLYA_CINE_PLUS_KIDS_HD: "VolyaKidsHD",
    AudioSource.V_ODNE_RYLO: "VOdneRylo",
    AudioSource.YANIAM: "Yaniam",
}
