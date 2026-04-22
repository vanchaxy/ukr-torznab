from enum import Enum


class AudioType(Enum):
    ORIGINAL = "original"
    MVO = "mvo"  # multi-voice over (багатоголосий)
    DVO = "dvo"  # dual-voice over (двоголосий)
    SVO = "svo"  # single-voice over (одноголосий)
    DUB = "dub"  # professional / amateur dub
    UNKNOWN = "unknown"

    def __str__(self):
        return AUDIO_TYPE_MAP.get(self, "")


AUDIO_TYPE_MAP: dict[AudioType, str] = {
    AudioType.MVO: "MVO",
    AudioType.DVO: "DVO",
    AudioType.SVO: "SVO",
    AudioType.DUB: "DUB",
}
