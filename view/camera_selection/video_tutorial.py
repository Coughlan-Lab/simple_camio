from res import ImgsManager
from res import VideosManager
from view.screen import Screen
import gui
import customtkinter as tk  # type: ignore
from res import Fonts
from tkinter.constants import CENTER, SW, SE
from PIL import Image
import os
from model import ContentManager
from tkinter import Label
import cv2
from PIL import Image, ImageTk
from typing import Union


class CalibrationVideoTutorial(Screen):
    VIDEO_RES = (640, 360)

    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.CameraSelector

    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, parent, show_back=True)

        self.title = tk.CTkLabel(
            self, text="New camera selected\nCalibrate it before proceeding", height=44
        )
        self.title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)
        self.title.configure(compound="left")
        self.title.configure(font=Fonts.subtitle)

        self.proceed = tk.CTkButton(self, text="Proceed", height=50, width=120)
        self.proceed.place(relx=0.7, rely=0.8, anchor=SE)
        self.proceed.configure(font=Fonts.button)
        self.proceed.configure(
            command=lambda: gui.get_gui().show_screen(
                gui.ScreenName.CalibrationVideoTutorial
            )
        )

        icon = tk.CTkImage(light_image=Image.open(ImgsManager.printer), size=(25, 25))
        self.print = tk.CTkButton(
            self,
            text="Calibration map",
            image=icon,
            height=50,
            width=120,
        )
        self.print.place(relx=0.3, rely=0.8, anchor=SW)
        self.print.configure(font=Fonts.button)
        self.print.configure(command=self.print_calibration_map)

        self.video = Label(
            parent,
            width=CalibrationVideoTutorial.VIDEO_RES[0],
            height=CalibrationVideoTutorial.VIDEO_RES[1],
        )
        self.video.place(relx=0.5, rely=0.5, anchor=CENTER)
        self.video.configure(background="black")

    def print_calibration_map(self) -> None:
        os.startfile(ContentManager.calibration_map)

    def focus(self) -> None:
        self.capture = cv2.VideoCapture(VideosManager.calibration_tutorial)
        self.capture.set(cv2.CAP_PROP_FOCUS, 0)
        # self.video_loop()

    def video_loop(self) -> None:
        ret, image = self.capture.read()
        print(ret, image)
        if not ret:
            print("No frame returned")
            return
        else:
            self.show_frame(image)
        self.video.after(33, self.video_loop)

    def show_frame(self, frame: cv2.typing.MatLike) -> None:
        # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        img_resized = Image.fromarray(frame).resize(
            CalibrationVideoTutorial.VIDEO_RES, Image.LANCZOS
        )

        self.imgtk = ImageTk.PhotoImage(image=img_resized)
        self.video.configure(image=self.imgtk)
