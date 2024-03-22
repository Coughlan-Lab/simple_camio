from tkinter import CENTER, DISABLED, SE, SW
from ..components import Camera, FrameViewer
from controllers.screen import Screen
import gui
import customtkinter as tk  # type: ignore
from typing import Union
from res import Fonts, ImgsManager, DocsManager
from PIL import Image
import cv2
import os
import numpy as np


class Calibration(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.CameraSelector

    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, parent, show_back=True)

        title = tk.CTkLabel(
            self,
            text="Print the calibration map, frame it with you camera and\nmatch its corners with the on-screen preview",
            font=Fonts.subtitle,
            height=44,
            compound="left",
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        self.confirm = tk.CTkButton(
            self, text="Confirm", font=Fonts.button, height=50, width=120
        )
        self.confirm.place(relx=0.7, rely=0.9, anchor=SE)
        self.confirm.configure(
            command=lambda: gui.get_gui().show_screen(gui.ScreenName.CamIO)
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

        self.camera = Camera(self)
        self.camera.set_on_error_listener(self.on_error)
        self.camera.set_frame_listener(self.on_frame)

        self.preview = FrameViewer(self, (500, 320))
        self.preview.place(relx=0.5, rely=0.5, anchor=CENTER)

        self.template = cv2.imread(ImgsManager.template, cv2.IMREAD_COLOR)

    def focus(self) -> None:
        camera_index = gui.get_gui().current_state.camera_index
        self.camera.start(camera_index)

    def on_error(self) -> None:
        self.confirm.configure(state=DISABLED)
        self.preview.show_error()

    def unfocus(self) -> None:
        self.camera.stop()

    def print_calibration_map(self) -> None:
        os.startfile(DocsManager.calibration_map)

    def on_frame(self, img: np.ndarray) -> None:
        self.preview.show_frame(img)
