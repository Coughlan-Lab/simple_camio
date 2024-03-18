from tkinter import CENTER, S
from view.screen import Screen
import gui
import customtkinter as tk
from res import Fonts, VideosManager
from PIL import Image, ImageTk
import cv2
from tkinter import Label
from tkVideoPlayer import TkinterVideo
from typing import Union


class ContentVideoTutorial(Screen):
    VIDEO_RES = (640, 360)

    @property
    def back_screen(self):
        return gui.ScreenName.ContentSelector

    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]):
        Screen.__init__(self, parent, show_back=True)

        title = tk.CTkLabel(
            self,
            text="Watch the tutorial before proceeding",
            font=Fonts.subtitle,
            height=44,
            compound="left"
        )
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        proceed = tk.CTkButton(
            self,
            text="Proceed", font=Fonts.button,
            height=50, width=120
        )
        proceed.place(relx=0.5, rely=0.9, anchor=S)
        proceed.configure(
            command=lambda: gui.get_gui().show_screen(
                gui.ScreenName.ContentVideoTutorial)
        )

        factor = 100
        self.video = TkinterVideo(
            self,
            background="black"
        )
        self.video.set_size(ContentVideoTutorial.VIDEO_RES, keep_aspect=True)
        self.video.place(
            relx=0.5, rely=0.5,
            width=ContentVideoTutorial.VIDEO_RES[0],
            height=ContentVideoTutorial.VIDEO_RES[1],
            anchor=CENTER
        )

    def focus(self):
        self.video.load(VideosManager.content_tutorial)
        self.video.play()

    def video_loop(self):
        ret, image = self.capture.read()

        if not ret:
            print("No frame returned")
            return
        else:
            self.show_frame(image)
        self.video.after(33, self.video_loop)

    def show_frame(self, frame):
        # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        img_resized = Image.fromarray(frame).resize(
            ContentVideoTutorial.VIDEO_RES, Image.LANCZOS
        )

        self.imgtk = ImageTk.PhotoImage(image=img_resized)
        self.video.configure(image=self.imgtk)
