import customtkinter as tk  # type: ignore
import json
from typing import TypedDict


class FontJson(TypedDict):
    family: str
    size: int


class Fonts:
    FONTS_FILE = "res/fonts.json"

    def __init__(self) -> None:
        with open(Fonts.FONTS_FILE, "r") as file:
            fonts: dict[str, FontJson] = json.load(file)

        self.title_params = fonts["title"]
        self.subtitle_params = fonts["subtitle"]
        self.button_params = fonts["button"]

    @property
    def title(self) -> tk.CTkFont:
        return self.__get_font(self.title_params)

    @property
    def subtitle(self) -> tk.CTkFont:
        return self.__get_font(self.subtitle_params)

    @property
    def button(self) -> tk.CTkFont:
        return self.__get_font(self.button_params)

    def __get_font(self, params: FontJson) -> tk.CTkFont:
        return tk.CTkFont(family=params["family"], size=params["size"])


singleton: Fonts = Fonts()
