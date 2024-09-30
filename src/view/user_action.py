from enum import Enum
from typing import Callable


class UserAction(Enum):
    STOP = 0  # Stop the program
    SAY_MAP_DESCRIPTION = 1  # Say the map description
    COMMAND = 2  # Ask a command
    STOP_INTERACTION = 3  # Interrupt TTS, STT and LLM
    STOP_NAVIGATION = 4  # End navigation mode
    TOGGLE_TTS = 5  # Pause or resume TTS
    DISABLE_POSITION_TTS = 6  # Disable TTS position messages
    ENABLE_POSITION_TTS = 7  # Enable TTS position messages


def ignore_action_end(fn: Callable[[], None]) -> Callable[[bool], None]:
    def wrapper(ended: bool = False) -> None:
        if ended:
            return

        fn()

    return wrapper
