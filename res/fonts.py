import customtkinter as tk
import json


class Fonts:
    FONTS_FILE = "res/fonts.json"

    def __init__(self):
        with open(Fonts.FONTS_FILE, "r") as file:
            fonts = json.load(file)

        self.title_params = fonts["title"]
        self.subtitle_params = fonts["subtitle"]
        self.button_params = fonts["button"]

    @property
    def title(self):
        return self.__get_font(self.title_params)

    @property
    def subtitle(self):
        return self.__get_font(self.subtitle_params)

    @property
    def button(self):
        return self.__get_font(self.button_params)

    def __get_font(self, params):
        return tk.CTkFont(family=params["family"], size=params["size"])


Fonts = Fonts()
