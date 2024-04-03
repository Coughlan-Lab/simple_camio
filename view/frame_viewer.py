import customtkinter as tk
from tkinter import Label
from PIL import Image, ImageTk
from typing import Optional, Tuple, Union
from res import Fonts, Colors
import numpy as np


class FrameViewer(Label):
    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk], frame_size: Tuple[int, int]):
        Label.__init__(self, parent)

        self.default_frame_size = frame_size
        self.frame_size = frame_size

        self.configure(
            width=self.frame_size[0], height=self.frame_size[1], background="black"
        )

        self.imgtk: Optional[ImageTk.PhotoImage] = None

    def show_error(self) -> None:
        self.configure(
            text="Error getting image",
            image="",
            font=Fonts.button,
            width=20,
            height=9,
            borderwidth=2,
            relief="solid",
            fg=Colors.text,
            bg=Colors.background,
        )

    def show_frame(self, img: np.ndarray) -> None:
        if self.imgtk is None:
            self.__reshape_preview(img.shape[1], img.shape[0])

        pilImage = Image.fromarray(img).resize(
            (self.frame_size[0], self.frame_size[1]), Image.LANCZOS
        )

        self.imgtk = ImageTk.PhotoImage(image=pilImage)
        self.configure(text="", image=self.imgtk)

    def __reshape_preview(self, w: int, h: int) -> None:
        if w > h:
            self.frame_size = (
                self.default_frame_size[0],
                int(h * self.default_frame_size[0] / w),
            )
            if self.frame_size[1] > self.default_frame_size[1]:
                self.frame_size = (
                    int(w * self.default_frame_size[1] / h),
                    self.default_frame_size[1],
                )
        else:  # h > w
            self.frame_size = (
                int(w * self.default_frame_size[1] / h),
                self.default_frame_size[1],
            )
            if self.frame_size[0] > self.default_frame_size[0]:
                self.frame_size = (
                    self.default_frame_size[0],
                    int(h * self.default_frame_size[0] / w),
                )

        self.configure(
            width=self.frame_size[0], height=self.frame_size[1], background="black"
        )
