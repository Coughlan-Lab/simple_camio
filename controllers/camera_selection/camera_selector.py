import customtkinter as tk  # type: ignore
from tkinter.constants import CENTER, S
from view import LoadingSpinner
import gui

import cv2
from model.utils import enumerate_cameras

from .camera_preview import CameraPreview
from controllers.screen import Screen
from res import Fonts, Colors
from typing import List, Tuple, Union

import threading


class CameraSelector(Screen):
    MAX_CAMERAS = 3

    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent, show_back=True)

        self.title = tk.CTkLabel(
            self, text="Select a camera:", height=44, text_color=Colors.text
        )
        self.title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)
        self.title.configure(font=Fonts.title)

        self.__container = Screen(self.gui, self)
        self.__container.place(
            relx=0.5, rely=0.8, relheight=0.4, relwidth=0.95, anchor=S
        )

        self.previews: list[CameraPreview] = list()

        for i in range(CameraSelector.MAX_CAMERAS):
            self.__container.grid_columnconfigure(i, weight=1)
        self.__container.grid_rowconfigure(0, weight=1)
        self.__container.grid_rowconfigure(1, weight=3)

        self.loading = LoadingSpinner(self)

    def on_focus(self) -> None:
        self.show_loading()
        threading.Thread(target=self.__load_cameras).start()

    def show_loading(self) -> None:
        self.loading.show()
        self.loading.place(relx=0.5, rely=0.5, anchor=CENTER)

    def hide_loading(self) -> None:
        self.loading.hide()
        self.loading.place_forget()

    def __load_cameras(self) -> None:
        if len(self.previews) == 0:
            self.init_cameras()

        if len(self.previews) == 1 and self.previews[0].running:
            self.previews[0].on_click()

        for preview in self.previews:
            preview.start()

        for i, preview in zip(self.__get_sorting(self.previews), self.previews):
            preview.grid(row=0, column=i, padx=5)

        self.hide_loading()

    def on_unfocus(self) -> None:
        for preview in self.previews:
            preview.stop()
            preview.grid_forget()
        self.loading.hide()

    def init_cameras(self) -> None:
        names = {preview.camera_name for preview in self.previews}

        for camera_info in enumerate_cameras(cv2.CAP_MSMF):
            if len(self.previews) >= CameraSelector.MAX_CAMERAS:
                break
            if camera_info.name in names:
                continue
            preview = CameraPreview(self.gui, self.__container, camera_info)
            self.previews.append(preview)

        if len(self.previews) == 0:
            self.gui.show_screen(gui.ScreenName.NoCamera)

    def __get_sorting(self, previews: List[CameraPreview]) -> Tuple[int, ...]:
        previews.sort(key=lambda p: p.camera_name)
        if len(previews) == 0:
            return ()
        if len(previews) == 1:
            return (1,)
        if len(previews) == 2:
            return (0, 2)
        return (0, 1, 2)
