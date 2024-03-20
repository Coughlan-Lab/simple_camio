from tkinter import CENTER, S, SE, SW
from view.screen import Screen
import gui
import customtkinter as tk  # type: ignore
from res import *
from tkVideoPlayer import TkinterVideo  # type: ignore
from typing import Any, Union
from PIL import Image
import os


class CalibrationVideoTutorial(Screen):
    VIDEO_RES = (640, 360)

    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.CameraSelector

    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, parent, show_back=True)

        title = tk.CTkLabel(
            self,
            text="New camera selected\nCalibrate it before proceeding",
            font=Fonts.subtitle,
            height=44,
            compound="left",
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        proceed = tk.CTkButton(
            self, text="Proceed", font=Fonts.button, height=50, width=120
        )
        proceed.place(relx=0.7, rely=0.9, anchor=SE)
        proceed.configure(
            command=lambda: gui.get_gui().show_screen(gui.ScreenName.Calibration)
        )

        icon = tk.CTkImage(light_image=Image.open(ImgsManager.printer), size=(25, 25))
        print = tk.CTkButton(
            self,
            text="Calibration map",
            font=Fonts.button,
            image=icon,
            height=50,
            width=120,
        )
        print.place(relx=0.3, rely=0.9, anchor=SW)
        print.configure(command=self.print_calibration_map)

        self.video = TkinterVideo(self, background=Colors.background)
        self.video.set_size(CalibrationVideoTutorial.VIDEO_RES, keep_aspect=True)
        self.video.place(
            relx=0.5,
            rely=0.5,
            width=CalibrationVideoTutorial.VIDEO_RES[0],
            height=CalibrationVideoTutorial.VIDEO_RES[1],
            anchor=CENTER,
        )
        self.video.bind("<<Ended>>", self.on_video_ended)

    def focus(self) -> None:
        self.video.load(VideosManager.calibration_tutorial)
        self.video.seek(0)
        self.video.play()

    def unfocus(self) -> None:
        self.video.stop()

    def on_video_ended(self, event: Any) -> None:
        gui.get_gui().current_state.set_calibration_tutorial_watched()

    def print_calibration_map(self) -> None:
        os.startfile(DocsManager.calibration_map)
