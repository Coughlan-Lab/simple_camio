from enum import Enum
from typing import Callable, Dict, Optional, Union

from pynput.keyboard import Key, KeyCode
from pynput.keyboard import Listener as KeyboardListener


class InputListener(Enum):
    STOP_INTERACTION = 0
    SAY_MAP_DESCRIPTION = 1
    TOGGLE_TTS = 2
    STOP = 3
    QUESTION = 4


class InputHandler:
    def __init__(self, listeners: Dict[InputListener, Callable[[], None]]) -> None:
        self.keyboard: Optional[KeyboardListener] = None
        self.listeners = listeners

    def init_shortcuts(self) -> None:
        def on_press(key: Optional[Union[Key, KeyCode]]) -> None:

            if key == Key.space:
                self.__call_listener(InputListener.QUESTION)
            elif key == Key.enter:
                self.__call_listener(InputListener.TOGGLE_TTS)
            elif key == Key.esc:
                self.__call_listener(InputListener.STOP_INTERACTION)
            elif key == KeyCode.from_char("d"):
                self.__call_listener(InputListener.SAY_MAP_DESCRIPTION)
            elif key == KeyCode.from_char("q"):
                self.__call_listener(InputListener.STOP)

        self.keyboard = KeyboardListener(on_press=on_press)
        self.keyboard.start()

    def disable_shortcuts(self) -> None:
        if self.keyboard is not None:
            self.keyboard.stop()

    def __call_listener(self, listener: InputListener) -> None:
        if listener in self.listeners:
            self.listeners[listener]()
