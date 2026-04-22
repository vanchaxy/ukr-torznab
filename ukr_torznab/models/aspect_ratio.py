from enum import Enum


class AspectRatio(Enum):
    STANDARD = "standard"
    OPEN_MATTE = "open-matte"
    IMAX = "imax"

    def __str__(self):
        if self is AspectRatio.OPEN_MATTE:
            return "Open Matte"
        if self is AspectRatio.IMAX:
            return "IMAX"
        return ""
