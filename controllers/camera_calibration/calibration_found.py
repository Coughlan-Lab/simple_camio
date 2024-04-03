from tkinter import CENTER, SE, SW
from controllers.screen import Screen
import gui
import customtkinter as tk  # type: ignore
from typing import Union
from res import Fonts, Colors


class CalibrationFound(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.CameraSelector

    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent, show_back=True)

        title = tk.CTkLabel(
            self,
            text="Calibration data found",
            font=Fonts.title,
            text_color=Colors.text,
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        subtitle = tk.CTkLabel(
            self,
            text="Please, run calibration again if this is not the last camera you used",
            font=Fonts.subtitle,
            justify=CENTER,
            text_color=Colors.text,
        )
        subtitle.place(relx=0.5, rely=0.21, relwidth=0.75, anchor=CENTER)

        calibrate = tk.CTkButton(
            self,
            text="Calibrate",
            font=Fonts.button,
            height=42,
            width=120,
            text_color=Colors.button_text,
        )
        calibrate.configure(command=self.on_calibrate)
        calibrate.place(relx=0.3, rely=0.6, anchor=SW)

        proceed = tk.CTkButton(
            self,
            text="Proceed",
            font=Fonts.button,
            height=42,
            width=120,
            text_color=Colors.button_text,
        )
        proceed.configure(command=self.on_proceed)
        proceed.place(relx=0.7, rely=0.6, anchor=SE)

    def on_calibrate(self) -> None:
        self.gui.show_screen(gui.ScreenName.Calibration)

    def on_proceed(self) -> None:
        self.gui.show_screen(gui.ScreenName.ContentUsage)
