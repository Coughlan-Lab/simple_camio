from view.screen import Screen
import gui
import customtkinter as tk


class ContentVideoTutorial(Screen):
    def __init__(self, parent: tk.CTkFrame | tk.CTk):
        Screen.__init__(self, parent, show_back=True)
