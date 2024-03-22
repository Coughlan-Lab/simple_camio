from tkinter import CENTER, S
from controllers.screen import Screen
import gui
import customtkinter as tk  # type: ignore
from res import *
from tkVideoPlayer import TkinterVideo  # type: ignore
from typing import Any, Union


class ContentVideoTutorial(Screen):
    VIDEO_RES = (640, 360)

    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent, show_back=True)

        title = tk.CTkLabel(
            self,
            text="Watch the tutorial before proceeding",
            font=Fonts.subtitle,
            height=44,
            compound="left",
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        proceed = tk.CTkButton(
            self, text="Proceed", font=Fonts.button, height=50, width=120
        )
        proceed.place(relx=0.5, rely=0.9, anchor=S)
        proceed.configure(command=self.show_pointer_selector)

        self.video = TkinterVideo(self, background=Colors.background)
        self.video.set_size(ContentVideoTutorial.VIDEO_RES, keep_aspect=True)
        self.video.place(
            relx=0.5,
            rely=0.5,
            width=ContentVideoTutorial.VIDEO_RES[0],
            height=ContentVideoTutorial.VIDEO_RES[1],
            anchor=CENTER,
        )
        self.video.bind("<<Ended>>", self.on_video_ended)

    def focus(self) -> None:
        self.video.load(VideosManager.content_tutorial)
        self.video.seek(0)
        self.video.play()

    def unfocus(self) -> None:
        self.video.stop()

    def on_video_ended(self, event: Any) -> None:
        self.gui.current_state.set_content_tutorial_watched()

    def show_pointer_selector(self) -> None:
        self.gui.show_screen(gui.ScreenName.PointerSelector)
