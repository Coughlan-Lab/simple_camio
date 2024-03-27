import customtkinter as tk  # type: ignore
from tkinter import DISABLED, NORMAL, Label, CENTER, SE, SW
from model import Content
from res import Colors, Fonts, ImgsManager
from controllers.screen import Screen
from PIL import ImageTk, Image
import gui
from typing import Union
from model.utils import open_file


class ContentDescription(Screen):
    def __init__(self, gui: "gui.GUI", parent: Union[tk.CTkFrame, tk.CTk]) -> None:
        Screen.__init__(self, gui, parent, show_back=True)

        self.title = tk.CTkLabel(
            self, text="", font=Fonts.title, text_color=Colors.text
        )
        self.title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)

        self.description = tk.CTkLabel(
            self, justify=CENTER, font=Fonts.subtitle, text_color=Colors.text
        )
        self.description.place(relx=0.5, rely=0.21, relwidth=0.75, anchor=CENTER)

        instructions = tk.CTkLabel(
            self,
            text="Print a copy of the content and proceed",
            justify=CENTER,
            font=Fonts.subtitle,
            text_color=Colors.text,
        )
        instructions.place(relx=0.5, rely=0.26, relwidth=0.6, anchor=CENTER)

        self.proceed = tk.CTkButton(
            self,
            text="Proceed",
            font=Fonts.button,
            text_color=Colors.button_text,
            height=50,
            width=120,
        )
        self.proceed.place(relx=0.7, rely=0.9, anchor=SE)
        self.proceed.configure(command=self.on_proceed)

        icon = tk.CTkImage(light_image=Image.open(ImgsManager.printer), size=(25, 25))
        self.print = tk.CTkButton(
            self,
            text="Content",
            image=icon,
            height=50,
            width=120,
            font=Fonts.button,
            text_color=Colors.button_text,
        )
        self.print.place(relx=0.3, rely=0.9, anchor=SW)
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
            fg=Colors.text,
        )

    def on_focus(self) -> None:
        self.title.configure(text=self.content.name)
        self.description.configure(text=self.content.description)
        preview = self.content.preview
        if preview is None:
            self.show_preview_error()
        else:
            self.show_preview(preview)

    def show_preview_error(self) -> None:
        self.preview_error.place(relx=0.5, rely=0.55, anchor=CENTER)
        self.preview.place_forget()
        self.print.configure(state=DISABLED)

    def show_preview(self, preview: str) -> None:
        img = Image.open(preview)
        self.reshape_preview(img.size[0], img.size[1])

        img = img.resize((self.image_size[0], self.image_size[1]), Image.LANCZOS)
        self.imgtk = ImageTk.PhotoImage(image=img)

        self.preview.configure(image=self.imgtk)
        self.preview.place(relx=0.5, rely=0.55, anchor=CENTER)
        self.preview_error.place_forget()
        self.print.configure(state=NORMAL)

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
        return self.gui.current_state.content

    def print_content(self) -> None:
        open_file(self.content.to_print)

    def on_proceed(self) -> None:
        if self.gui.current_state.content_tutorial_watched:
            next_screen = gui.ScreenName.PointerSelector
        else:
            next_screen = gui.ScreenName.ContentVideoTutorial
        self.gui.show_screen(next_screen)
