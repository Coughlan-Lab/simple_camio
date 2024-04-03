from tkinter import CENTER, N, RIGHT
from controllers.screen import Screen
import gui
import customtkinter as tk

from ..components import Camera
from typing import Optional, Union
from res import Fonts, Colors, ImgsManager
from PIL import Image
from model import State, get_frame_processor, FrameProcessor
from view import FrameViewer
import cv2
import numpy as np
import threading


class ContentUsage(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, gui, parent, show_back=True)

        self.title = tk.CTkLabel(
            self,
            font=Fonts.subtitle,
            height=44,
            text_color=Colors.text,
        )
        self.title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        icon = tk.CTkImage(
            light_image=Image.open(ImgsManager.question_mark), size=(25, 25)
        )
        self.tutorial = tk.CTkButton(
            self, text="", image=icon, anchor=CENTER, width=10, height=30
        )
        self.tutorial.pack(side=RIGHT, padx=(0, 40), pady=(30, 0), anchor=N)
        self.tutorial.configure(command=self.show_tutorial)

        self.preview = FrameViewer(self, (600, 350))
        self.preview.place(relx=0.5, rely=0.5, anchor=CENTER)

        self.camera = Camera(self)
        self.camera.set_on_error_listener(self.preview.show_error)
        self.camera.set_frame_listener(self.on_frame)

        self.semaphore = threading.Semaphore()
        self.frame_processor: Optional[FrameProcessor] = None

    def on_focus(self) -> None:
        self.set_title()

        state = self.gui.current_state
        self.frame_processor = get_frame_processor(
            state.content, state.pointer, state.get_calibration_filename()
        )
        self.camera.start(state.camera.index)

    def set_title(self) -> None:
        title_pointer: str
        if self.gui.current_state.pointer == State.Pointer.FINGER:
            title_pointer = "your finger"
        else:
            title_pointer = "the drop marker"
        self.title.configure(
            text=f"Frame the content with your camera and\nuse {title_pointer} to select an object"
        )

    def on_unfocus(self) -> None:
        self.camera.stop()
        if self.frame_processor is not None:
            self.frame_processor.destroy()
        del self.frame_processor

    def on_frame(self, img: np.ndarray) -> None:
        if self.frame_processor is None or self.semaphore.acquire(blocking=False):
            return

        img = self.frame_processor.process(img)
        self.preview.show_frame(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

        self.semaphore.release()

    def show_tutorial(self) -> None:
        self.gui.show_screen(gui.ScreenName.ContentVideoTutorial)
