from enum import Enum


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

    def __str__(self):
        return LANG_FULL.get(self, "").capitalize()

    def code(self):
        return LANG_CODE.get(self, "")


LANG_FULL: dict[Lang, str] = {
    Lang.UKRAINIAN: "ukrainian",
    Lang.ENGLISH: "english",
    Lang.RUSSIAN: "russian",
    Lang.SPANISH: "spanish",
    Lang.FRENCH: "french",
    Lang.CHINESE: "chinese",
    Lang.JAPANESE: "japanese",
    Lang.KOREAN: "korean",
    Lang.GERMAN: "german",
    Lang.ITALIAN: "italian",
    Lang.DUTCH: "dutch",
    Lang.POLISH: "polish",
    Lang.PORTUGUESE: "portuguese",
    Lang.CZECH: "czech",
    Lang.SLOVAK: "slovak",
    Lang.BULGARIAN: "bulgarian",
    Lang.ROMANIAN: "romanian",
    Lang.CROATIAN: "croatian",
    Lang.SERBIAN: "serbian",
    Lang.SWEDISH: "swedish",
    Lang.DANISH: "danish",
    Lang.FINNISH: "finnish",
    Lang.NORWEGIAN: "norwegian",
    Lang.HUNGARIAN: "hungarian",
    Lang.GREEK: "greek",
    Lang.TURKISH: "turkish",
    Lang.ARABIC: "arabic",
    Lang.HINDI: "hindi",
    Lang.PERSIAN: "persian",
    Lang.INDONESIAN: "indonesian",
    Lang.ICELANDIC: "icelandic",
    Lang.ESTONIAN: "estonian",
    Lang.SLOVENIAN: "slovenian",
    Lang.MOLDOVAN: "moldovan",
    Lang.AFRIKAANS: "afrikaans",
    Lang.THAI: "thai",
    Lang.VIETNAMESE: "vietnamese",
    Lang.HEBREW: "hebrew",
    Lang.LITHUANIAN: "lithuanian",
    Lang.MALAYALAM: "malayalam",
    Lang.LATVIAN: "latvian",
    Lang.CATALAN: "catalan",
    Lang.BOSNIAN: "bosnian",
    Lang.TAMIL: "tamil",
    Lang.MACEDONIAN: "macedonian",
}
LANG_FULL_REVERSE: dict[str, Lang] = {
    **{v: k for k, v in LANG_FULL.items()},
    "cantonese": Lang.CHINESE,
    "mandarin": Lang.CHINESE,
    "flemish": Lang.DUTCH,
}


LANG_CODE: dict[Lang, str] = {
    Lang.UKRAINIAN: "UKR",
    Lang.ENGLISH: "ENG",
    Lang.RUSSIAN: "RUS",
    Lang.SPANISH: "SPA",
    Lang.FRENCH: "FRE",
    Lang.CHINESE: "CHI",
    Lang.JAPANESE: "JPN",
    Lang.KOREAN: "KOR",
    Lang.GERMAN: "GER",
    Lang.ITALIAN: "ITA",
    Lang.DUTCH: "DUT",
    Lang.POLISH: "POL",
    Lang.PORTUGUESE: "POR",
    Lang.CZECH: "CZE",
    Lang.SLOVAK: "SLO",
    Lang.BULGARIAN: "BUL",
    Lang.ROMANIAN: "ROM",
    Lang.CROATIAN: "HRV",
    Lang.SERBIAN: "SRP",
    Lang.SWEDISH: "SWE",
    Lang.DANISH: "DAN",
    Lang.FINNISH: "FIN",
    Lang.NORWEGIAN: "NOR",
    Lang.HUNGARIAN: "HUN",
    Lang.GREEK: "GRE",
    Lang.TURKISH: "TUR",
    Lang.ARABIC: "ARA",
    Lang.HINDI: "HIN",
    Lang.PERSIAN: "PER",
    Lang.INDONESIAN: "IND",
    Lang.ICELANDIC: "ICE",
    Lang.ESTONIAN: "EST",
    Lang.SLOVENIAN: "SLV",
    Lang.MOLDOVAN: "MOL",
    Lang.AFRIKAANS: "AFR",
    Lang.THAI: "THA",
    Lang.VIETNAMESE: "VIE",
    Lang.HEBREW: "HEB",
    Lang.LITHUANIAN: "LIT",
    Lang.MALAYALAM: "MAL",
    Lang.LATVIAN: "LAV",
    Lang.CATALAN: "CAT",
    Lang.BOSNIAN: "BOS",
    Lang.TAMIL: "TAM",
    Lang.MACEDONIAN: "MAC",
}

LANG_CODE_REVERSE: dict[str, Lang] = {
    **{v.lower(): k for k, v in LANG_CODE.items()},
    "ces": Lang.CZECH,
    "deu": Lang.GERMAN,
    "ell": Lang.GREEK,
    "fas": Lang.PERSIAN,
    "fra": Lang.FRENCH,
    "isl": Lang.ICELANDIC,
    "nld": Lang.DUTCH,
    "ron": Lang.ROMANIAN,
    "rum": Lang.ROMANIAN,
    "slk": Lang.SLOVAK,
    "zho": Lang.CHINESE,
}
