from enum import Enum


class UserAction(Enum):
    STOP = 0
    SAY_MAP_DESCRIPTION = 1
    TOGGLE_TTS = 2
    STOP_INTERACTION = 3
    QUESTION = 4
    STOP_NAVIGATION = 5
