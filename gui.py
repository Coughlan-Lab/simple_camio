import customtkinter as tk
from enum import Enum
from tkinter import BOTH, TOP

from view import *
from view.screen import Screen
from model import State


class ScreenName(Enum):
    HomePage = HomePage
    CameraSelector = CameraSelector
    ContentSelector = ContentSelector
    ContentDescription = ContentDescription
    ContentVideoTutorial = ContentVideoTutorial
    NoCamera = NoCamera
    CalibrationVideoTutorial = CalibrationVideoTutorial


class GUI(tk.CTk):

    def __init__(self, *args, **kwargs):
        tk.CTk.__init__(self, *args, **kwargs)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.__state = State()

        self.title("CamIO")
        self.geometry("966x622+200+48")
        self.minsize(1, 1)
        self.maxsize(1351, 738)
        self.resizable(False, False)

        # the container is where we'll stack a bunch of frames
        # on top of each other, then the one we want visible
        # will be raised above the others
        container = Screen(self)
        container.pack(side=TOP, fill=BOTH, expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        for page in ScreenName:
            frame = page.value(container)
            self.frames[page.name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.current_frame = None
        self.show_screen(ScreenName.HomePage)

    @property
    def current_state(self):
        return self.__state

    def show_screen(self, screen: ScreenName):
        if screen.name not in self.frames:
            raise Exception(f"Unknown screen {screen}")
        if self.current_frame is not None:
            self.current_frame.unfocus()
        self.current_frame = self.frames[screen.name]
        self.current_frame.tkraise()
        self.current_frame.focus()

    def start(self, screen) -> None:
        if screen is not None:
            self.show_screen(screen)
        self.mainloop()

    def destroy(self) -> None:
        self.current_frame.unfocus()
        for frame in self.frames.values():
            frame.destroy()
        return super().destroy()


gui: GUI | None = None


def create_gui():
    global gui
    if gui is not None:
        raise Exception("Gui already started")
    gui = GUI()
    return gui


def get_gui():
    if gui is None:
        create_gui()
    return gui


__all__ = ["create_gui", "get_gui", "ScreenName"]
