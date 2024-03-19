import customtkinter as tk  # type: ignore
from tkinter import Label, CENTER, SE, SW
from model import Content
from res import Colors, Fonts, ImgsManager
from view.screen import Screen
from PIL import ImageTk, Image
import gui
import os
from typing import Union


class ContentDescription(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]) -> None:
        Screen.__init__(self, parent, show_back=True)

        self.name = tk.CTkLabel(self, text="")
        self.name.place(relx=0.5, rely=0.12, relwidth=1, anchor=CENTER)
        self.name.configure(font=Fonts.title)

        self.description = tk.CTkLabel(self, justify=CENTER)
        self.description.place(relx=0.5, rely=0.19, relwidth=0.75, anchor=CENTER)
        self.description.configure(font=Fonts.subtitle)

        instructions = tk.CTkLabel(
            self, text="Print a copy of the content and proceed", justify=CENTER
        )
        instructions.place(relx=0.5, rely=0.26, relwidth=0.6, anchor=CENTER)
        instructions.configure(font=Fonts.subtitle)

        self.proceed = tk.CTkButton(self, text="Proceed", height=50, width=120)
        self.proceed.place(relx=0.7, rely=0.9, anchor=SE)
        self.proceed.configure(font=Fonts.button)
        self.proceed.configure(command=self.on_proceed)

        icon = tk.CTkImage(light_image=Image.open(ImgsManager.printer), size=(25, 25))
        self.print = tk.CTkButton(
            self,
            text="Content",
            image=icon,
            height=50,
            width=120,
        )
        self.print.place(relx=0.3, rely=0.9, anchor=SW)
        self.print.configure(font=Fonts.button)
        self.print.configure(command=self.print_content)

        self.image_size = (250, 250)
        self.preview = Label(
            self, text="", width=self.image_size[0], height=self.image_size[1]
        )
        self.preview.place(relx=0.5, rely=0.55, anchor=CENTER)

        self.preview_error = Label(
            self,
            text="No preview found",
            font=Fonts.subtitle,
            background=Colors.background,
            borderwidth=2,
            relief="solid",
            width=20,
            height=10,
        )

    def focus(self) -> None:
        self.name.configure(text=self.content.name)
        self.description.configure(text=self.content.description)
        preview = self.content.preview
        if preview is None:
            self.show_preview_error()
        else:
            self.show_preview(preview)

    def show_preview_error(self) -> None:
        self.preview_error.place(relx=0.5, rely=0.55, anchor=CENTER)
        self.preview.place_forget()

    def show_preview(self, preview: str) -> None:
        img = Image.open(preview)
        self.reshape_preview(img.size[0], img.size[1])

        img = img.resize((self.image_size[0], self.image_size[1]), Image.LANCZOS)
        self.imgtk = ImageTk.PhotoImage(image=img)

        self.preview.configure(image=self.imgtk)
        self.preview.place(relx=0.5, rely=0.55, anchor=CENTER)
        self.preview_error.place_forget()

    def reshape_preview(self, w: int, h: int) -> None:
        if w > h:
            self.image_size = (self.image_size[0], int(h * self.image_size[0] / w))
        else:  # h > w
            self.image_size = (int(w * self.image_size[1] / h), self.image_size[1])

        self.preview.configure(
            background="black", width=self.image_size[0], height=self.image_size[1]
        )

    @property
    def content(self) -> Content:
        return gui.get_gui().current_state.content

    def print_content(self) -> None:
        os.startfile(self.content.to_print)

    def on_proceed(self) -> None:
        gui_instance: gui.GUI = gui.get_gui()

        if gui_instance.current_state.content_tutorial_watched:
            next_screen = gui.ScreenName.PointerSelector
        else:
            next_screen = gui.ScreenName.ContentVideoTutorial
        gui_instance.show_screen(next_screen)
