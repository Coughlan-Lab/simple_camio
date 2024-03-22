import customtkinter as tk
from tkinter import Label
from controllers.screen import Screen
from PIL import Image, ImageTk
from typing import Callable, Optional, Tuple, Union
import cv2
from res import Fonts
import numpy as np


class Webcam(Label):
    def __init__(
        self,
        parent: Union[tk.CTkFrame, tk.CTk],
        frame_size: Tuple[int, int],
    ):
        Label.__init__(self, parent)

        self.frame_size = frame_size

        self.configure(
            width=self.frame_size[0],
            height=self.frame_size[1],
            background="black",
        )

        self.imgtk: Optional[ImageTk.PhotoImage] = None
        self.capture: Optional[cv2.VideoCapture] = None
        self.on_error_listener: Optional[Callable[[], None]] = None
        self.frame_handler: Optional[Callable[[np.ndarray], np.ndarray]] = None

    def set_on_error_listener(self, listener: Callable[[], None]) -> None:
        self.on_error_listener = listener

    def set_frame_handler(self, listener: Callable[[np.ndarray], np.ndarray]) -> None:
        self.frame_handler = listener

    @property
    def running(self) -> bool:
        return self.capture is not None and self.capture.isOpened()

    def start(self, camera_index: int) -> None:
        if self.running:
            return
        self.capture = cv2.VideoCapture(camera_index)
        self.capture.set(cv2.CAP_PROP_FOCUS, 0)
        self.__camera_loop()

    def __camera_loop(self) -> None:
        if not self.running:
            return
        ret, image = self.capture.read()
        if not ret:
            self.__on_error()
        else:
            self.__on_frame(image)
            self.after(33, self.__camera_loop)

    def __on_error(self) -> None:
        self.configure(
            text="Error getting image",
            font=Fonts.button,
            width=20,
            height=9,
            borderwidth=2,
            relief="solid",
        )
        self.__release_camera()
        if self.on_error_listener is not None:
            self.on_error_listener()

    def __on_frame(self, img: np.ndarray) -> None:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if self.frame_handler is not None:
            img = self.frame_handler(img)

        if self.imgtk is None:
            self.__reshape_preview(img.shape[1], img.shape[0])

        pilImage = Image.fromarray(img).resize(
            (self.frame_size[0], self.frame_size[1]), Image.LANCZOS
        )

        self.imgtk = ImageTk.PhotoImage(image=pilImage)
        self.configure(text="", image=self.imgtk)

    def __reshape_preview(self, w: int, h: int) -> None:
        if w > h:
            self.frame_size = (self.frame_size[0], int(h * self.frame_size[0] / w))
        else:  # h > w
            self.frame_size = (int(w * self.frame_size[1] / h), self.frame_size[1])

        self.configure(
            width=self.frame_size[0], height=self.frame_size[1], background="black"
        )

    def stop(self) -> None:
        self.__release_camera()

    def __release_camera(self) -> None:
        if not self.running:
            return
        self.capture.release()
        self.capture = None
