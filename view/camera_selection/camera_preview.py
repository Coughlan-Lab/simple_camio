import customtkinter as tk  # type: ignore
from tkinter import DISABLED, Label

from cv2_enumerate_cameras import CameraInfo  # type: ignore
from res import Colors
import gui

import cv2
from PIL import Image, ImageTk
from res import Fonts
from typing import Any, Optional, Union


class CameraPreview:
    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk], camera_info: CameraInfo):
        self.camera_name = camera_info.name
        self.camera_index = camera_info.index

        self.button = tk.CTkButton(parent, text=f"{camera_info.name}", width=50)
        self.button.configure(font=Fonts.button)
        self.button.configure(command=self.on_click)

        self.image_size = (250, 250)
        self.preview = Label(
            parent, width=self.image_size[0], height=self.image_size[1]
        )
        self.preview.configure(background=Colors.background)

        self.imgtk: Optional[ImageTk.PhotoImage] = None
        self.capture: Optional[cv2.VideoCapture] = None

    def grid(self, row: int, column: int, **kwargs: Any) -> None:
        self.button.grid(row=row, column=column, **kwargs)
        self.preview.grid(row=row + 1, column=column, pady=5, **kwargs)

    @property
    def running(self) -> bool:
        return self.capture is not None and self.capture.isOpened()

    def focus(self) -> None:
        if self.running:
            return
        self.capture = cv2.VideoCapture(self.camera_index)
        self.capture.set(cv2.CAP_PROP_FOCUS, 0)
        self.camera_loop()

    def camera_loop(self) -> None:
        if not self.running:
            return
        ret, image = self.capture.read()
        if not ret:
            self.show_error()
        else:
            self.show_image(image)
            self.preview.after(33, self.camera_loop)

    def show_error(self) -> None:
        self.preview.configure(
            text="Error getting image",
            font=Fonts.button,
            width=20,
            height=9,
            borderwidth=2,
            relief="solid",
        )
        self.button.configure(state=DISABLED)
        self.__release_camera()

    def show_image(self, img: cv2.typing.MatLike) -> None:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if self.imgtk is None:
            self.reshape_preview(img.shape[1], img.shape[0])

        pilImage = Image.fromarray(img).resize(
            (self.image_size[0], self.image_size[1]), Image.LANCZOS
        )

        self.imgtk = ImageTk.PhotoImage(image=pilImage)
        self.preview.configure(text="", image=self.imgtk)

    def reshape_preview(self, w: int, h: int) -> None:
        if w > h:
            self.image_size = (self.image_size[0], int(h * self.image_size[0] / w))
        else:  # h > w
            self.image_size = (int(w * self.image_size[1] / h), self.image_size[1])

        self.preview.configure(
            width=self.image_size[0], height=self.image_size[1], background="black"
        )

    def unfocus(self) -> None:
        if not self.running:
            return
        self.__release_camera()

    def __release_camera(self) -> None:
        self.capture.release()
        self.capture = None

    def on_click(self) -> None:
        g = gui.get_gui()
        state = g.current_state

        if state.pointer == state.Pointer.FINGER and state.content.is_2D():
            next_screen = gui.ScreenName.CamIO
        elif state.is_calibrated(self.camera_name):
            next_screen = gui.ScreenName.CamIO
        elif state.calibration_tutorial_watched:
            next_screen = gui.ScreenName.Calibration
        else:
            next_screen = gui.ScreenName.CalibrationVideoTutorial

        g.show_screen(next_screen)
