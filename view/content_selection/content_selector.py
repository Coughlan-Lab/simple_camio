from tkinter import E, HORIZONTAL, LEFT, TOP, W, X
import customtkinter as tk
from tkinter.constants import CENTER, S
import tkinter.ttk as ttk
from model.content_manager import Content
from res.colors import Colors

from view.screen import Screen
import gui

from res import Fonts
from model import ContentManager
from typing import Union


class ContentSelector(Screen):
    @property
    def back_screen(self):
        return gui.ScreenName.HomePage

    def __init__(self, parent: Union[tk.CTkFrame, tk.CTk]) -> None:
        Screen.__init__(self, parent, show_back=True)

        title = tk.CTkLabel(self, text="Select a content:", height=44)
        title.place(relx=0.5, rely=0.15, relwidth=1, anchor=CENTER)
        title.configure(compound="left")
        title.configure(font=Fonts.title)

        self.__error_msg = tk.CTkFrame(
            self, fg_color=Colors.transparent, border_color="black", border_width=2)
        error = tk.CTkLabel(
            self.__error_msg, text="No content found in the content directory", height=44, justify=CENTER)
        error.place(relx=0.5, rely=0.5, anchor=CENTER)
        error.configure(font=Fonts.subtitle)

        self.__container = tk.CTkScrollableFrame(
            self, fg_color=Colors.transparent, border_color="black", border_width=2)
        self.__container.columnconfigure(0, weight=1)
        self.show_content()
        ContentHeader(self.__container)

        self.content: list[ContentRow] = list()

    def focus(self) -> None:
        ContentManager.reload()
        self.init_content()

    def init_content(self) -> None:
        names = {c.content_name for c in self.content}

        for content in ContentManager.content:
            if content in names:
                continue
            row = ContentRow(self.__container, content)
            self.content.append(row)

        if len(self.content) == 0:
            self.show_no_content()
        else:
            self.show_content()

        for i, row in enumerate(self.content):
            row.grid(row=i+1, pady=1)

    def show_content(self) -> None:
        self.__container.place(
            relx=0.5, rely=0.8, relheight=0.4, relwidth=0.95, anchor=S
        )
        self.__error_msg.place_forget()

    def show_no_content(self) -> None:
        self.__container.place_forget()
        self.__error_msg.place(
            relx=0.5, rely=0.8, relheight=0.4, relwidth=0.95, anchor=S
        )


class ContentHeader(tk.CTkFrame):
    HEIGHT = 48

    def __init__(self, parent) -> None:
        tk.CTkFrame.__init__(
            self, parent, height=ContentRow.HEIGHT)
        self.grid(row=0, column=0, sticky=W+E)

        self.name = tk.CTkLabel(
            self,
            text="Content",
            justify=CENTER,
            height=ContentRow.HEIGHT,
            width=200,
            bg_color=Colors.transparent
        )
        self.name.pack(side=LEFT)
        self.name.configure(font=Fonts.subtitle)

        self.description = tk.CTkLabel(
            self,
            text="Description", justify=CENTER,
            height=ContentRow.HEIGHT,
            bg_color=Colors.transparent
        )
        self.description.pack(fill="x")
        self.description.configure(font=Fonts.subtitle)


class ContentRow(tk.CTkFrame):
    HEIGHT = 48

    def __init__(self, parent, content_name: str) -> None:
        tk.CTkFrame.__init__(
            self, parent, height=ContentRow.HEIGHT, fg_color=Colors.transparent)
        self.content = ContentManager.get_content_data(content_name)
        self.grid(column=0, sticky=W+E)

        styl = ttk.Style()
        styl.configure('black.TSeparator', background='black')
        self.separator = ttk.Separator(
            self, orient=HORIZONTAL, style="black.TSeparator")
        self.separator.pack(side=TOP, fill="x")

        self.name = tk.CTkLabel(
            self,
            text=self.content.name,
            justify=CENTER,
            height=ContentRow.HEIGHT,
            width=200,
        )
        self.name.pack(side=LEFT, )
        self.name.configure(font=Fonts.subtitle)

        self.description = tk.CTkLabel(
            self,
            text=self.content.description, justify=CENTER,
            height=ContentRow.HEIGHT,
        )
        self.description.pack(fill=X)
        self.description.configure(font=Fonts.subtitle)

        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

    @property
    def content_name(self) -> str:
        return self.content.full_name

    def bind(self, event, callback):
        self.name.bind(event, callback)
        self.description.bind(event, callback)

    def on_click(self, event):
        gui.get_gui().current_state.content = self.content
        gui.get_gui().show_screen(gui.ScreenName.ContentDescription)

    def on_enter(self, event):
        self.name.configure(bg_color=Colors.hover)
        self.description.configure(bg_color=Colors.hover)

    def on_leave(self, event):
        self.name.configure(bg_color=Colors.transparent)
        self.description.configure(bg_color=Colors.transparent)
