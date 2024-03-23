from typing import Union
import customtkinter as tk  # type: ignore
from tkinter import Label
from PIL import Image, ImageTk
from itertools import count, cycle
import numpy as np
from res import Colors, ImgsManager


class LoadingSpinner(Label):
    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]) -> None:
        Label.__init__(self, parent)
        self.configure(background=Colors.background)

        img = Image.open(ImgsManager.loading_spinner)

        frames = []
        try:
            for i in count(1):
                frames.append(ImageTk.PhotoImage(img.copy()))
                img.seek(i)
        except EOFError:
            pass

        self.frames = cycle(frames)
        try:
            self.delay = img.info["duration"]
        except:
            self.delay = 1000 // 60

    def show(self) -> None:
        self.__next_frame()

    def hide(self) -> None:
        self.configure(
            image=ImageTk.PhotoImage(
                Image.fromarray(np.zeros((1, 1, 3), dtype=np.uint8))
            )
        )

    def __next_frame(self) -> None:
        self.configure(image=next(self.frames))
        self.after(self.delay, self.__next_frame)
