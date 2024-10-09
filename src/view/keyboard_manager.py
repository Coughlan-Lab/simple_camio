from typing import Callable, Mapping, Optional, Union, Set, Dict

from pynput.keyboard import Key, KeyCode
from pynput.keyboard import Listener as KeyboardListener

from src.modules_repository import Module
from .user_action import UserAction

import os
import json


class Shortcuts:
    def __init__(self, file: str) -> None:
        if not os.path.exists(file):
            raise FileNotFoundError(f"Shortcuts file not found: {file}")

        self.__shortcuts: Dict[Union[Key, KeyCode], UserAction] = dict()

        with open(file, "r") as f:
            shortcuts = json.load(f)

        for action, key in shortcuts.items():
            self.__shortcuts[self.__get_key(key)] = UserAction[action]

    def __get_key(self, key: str) -> Union[Key, KeyCode]:
        if len(key) == 1:
            return KeyCode.from_char(key)
        return Key[key]

    def __contains__(self, key: Union[Key, KeyCode]) -> bool:
        return key in self.__shortcuts

    def __getitem__(self, key: Union[Key, KeyCode]) -> UserAction:
        return self.__shortcuts[key]


class KeyboardManager(Module):
    def __init__(
        self,
        shortcuts_file: str,
        on_action: Callable[[UserAction, bool], None],
    ) -> None:
        super().__init__()

        self.keyboard: Optional[KeyboardListener] = None
        self.on_action = on_action
        self.paused = False

        self.shortcuts = Shortcuts(shortcuts_file)
        self.__pressed_keys: Set[Union[Key, KeyCode]] = set()

    def init_shortcuts(self) -> None:
        def on_press(key: Optional[Union[Key, KeyCode]]) -> None:
            if not key or key in self.__pressed_keys:
                return

            if key in self.shortcuts and not self.paused:
                self.on_action(self.shortcuts[key], True)
                self.__pressed_keys.add(key)

        def on_release(key: Optional[Union[Key, KeyCode]]) -> None:
            if key in self.__pressed_keys:
                self.on_action(self.shortcuts[key], False)
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
