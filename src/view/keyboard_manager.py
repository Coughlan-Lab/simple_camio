from enum import Enum
from typing import Callable, Mapping, Optional, Union, Set

from pynput.keyboard import Key, KeyCode
from pynput.keyboard import Listener as KeyboardListener

from src.modules_repository import Module


class InputListener(Enum):
    STOP_INTERACTION = Key.esc
    SAY_MAP_DESCRIPTION = KeyCode.from_char("d")
    TOGGLE_TTS = Key.enter
    STOP = KeyCode.from_char("q")
    QUESTION = Key.space
    STOP_NAVIGATION = KeyCode.from_char("n")

    @staticmethod
    def from_key(key: Union[Key, KeyCode]) -> Optional["InputListener"]:
        return InputListener(key)

    @staticmethod
    def has_listener(key: Union[Key, KeyCode]) -> bool:
        return key in InputListener._value2member_map_


class KeyboardManager(Module):
    def __init__(
        self, listeners: Mapping[InputListener, Callable[[bool], None]]
    ) -> None:
        super().__init__()

        self.keyboard: Optional[KeyboardListener] = None
        self.listeners = listeners
        self.paused = False

        self.__pressed_keys: Set[Union[Key, KeyCode]] = set()

    def init_shortcuts(self) -> None:
        def on_press(key: Optional[Union[Key, KeyCode]]) -> None:
            if not key or key in self.__pressed_keys:
                return

            if InputListener.has_listener(key):
                self.__call_listener(InputListener.from_key(key), pressed=True)
                self.__pressed_keys.add(key)

        def on_release(key: Optional[Union[Key, KeyCode]]) -> None:
            if key in self.__pressed_keys:
                self.__call_listener(InputListener.from_key(key), pressed=False)
                self.__pressed_keys.remove(key)

        self.keyboard = KeyboardListener(on_press=on_press, on_release=on_release)
        self.keyboard.start()

    def disable_shortcuts(self) -> None:
        if self.keyboard is not None:
            self.keyboard.stop()

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def __call_listener(self, listener: InputListener, pressed: bool) -> None:
        if not self.paused and listener in self.listeners:
            self.listeners[listener](pressed)


def ignore_unpress(fn: Callable[[], None]) -> Callable[[bool], None]:
    def wrapper(pressed: bool) -> None:
        if not pressed:
            return

        fn()

    return wrapper
