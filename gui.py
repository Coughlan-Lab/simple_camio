import os
import customtkinter as tk  # type: ignore
from enum import Enum
from tkinter import BOTH, E, N, S, TOP, W

from controllers import *
from model import State, utils
from typing import List, Dict, Optional


class ScreenName(Enum):
    HomePage = HomePage
    CameraSelector = CameraSelector
    ContentSelector = ContentSelector
    ContentDescription = ContentDescription
    ContentVideoTutorial = ContentVideoTutorial
    PointerSelector = PointerSelector
    NoCamera = NoCamera
    CalibrationVideoTutorial = CalibrationVideoTutorial
    Calibration = Calibration
    CalibrationFound = CalibrationFound
    ContentUsage = ContentUsage


class GUI(tk.CTk):
    CONFIG_FOLDER = os.path.join(utils.getcwd(), "config")

    def __init__(self) -> None:
        tk.CTk.__init__(self)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.__state = State(GUI.CONFIG_FOLDER)

        self.title("CamIO")
        self.geometry("966x622+200+48")
        self.minsize(1, 1)
        self.maxsize(1351, 738)
        self.resizable(False, False)

        # the container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        self.container = Screen(self, self)
        self.container.pack(side=TOP, fill=BOTH, expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.stack: List[str] = []
        self.frames: Dict[str, Screen] = dict()

        for page in ScreenName:
            frame = page.value(self, self.container)
            self.frames[page.name] = frame
            frame.grid(row=0, column=0, sticky=N + S + E + W)

        self.current_frame: Optional[Screen] = None
        self.show_screen(ScreenName.HomePage)

    @property
    def current_state(self) -> State:
        return self.__state

    @property
    def last_screen(self) -> ScreenName:
        if len(self.stack) == 0:
            return ScreenName.HomePage
        return ScreenName[self.stack[-1]]

    def show_screen(self, screen: ScreenName, stack: bool = True) -> None:
        if screen.name not in self.frames:
            raise Exception(f"Unknown screen {screen}")

        if self.current_frame is not None:
            self.current_frame.on_unfocus()
            if stack:
                self.stack.append(self.current_frame.name)

        self.current_frame = self.frames[screen.name]
        self.current_frame.tkraise()
        self.current_frame.on_focus()

    def start(self, screen: Optional[ScreenName]) -> None:
        if screen is not None:
            self.show_screen(screen)
        self.mainloop()

    def destroy(self) -> None:
        if self.current_frame is not None:
            self.current_frame.on_unfocus()

        for frame in self.frames.values():
            frame.destroy()

        self.container.destroy()
        super().destroy()

    def back(self, to: Optional[ScreenName] = None) -> None:
        if len(self.stack) == 0:
            return

        if to is not None and to.name in self.stack:
            i = self.stack.index(to.name)
            self.stack = self.stack[:i]
        else:
            to = ScreenName[self.stack.pop()]

        self.show_screen(to, stack=False)


gui: Optional[GUI] = None


def create_gui() -> GUI:
    global gui
    if gui is not None:
        raise Exception("Gui already started")
    gui = GUI()
    return gui


def get_gui() -> GUI:
    if gui is None:
        return create_gui()
    return gui
