import wx
import json
from typing import Dict, TypedDict
import os


class FontJson(TypedDict):
    family: str
    size: int


class Fonts:
    FONTS_FILE = os.path.join(
        os.sep.join(os.path.abspath(__file__).split(os.sep)[:-1]), "fonts.json"
    )

    def __init__(self) -> None:
        with open(Fonts.FONTS_FILE, "r") as file:
            fonts: Dict[str, FontJson] = json.load(file)

        self.title_params = fonts["title"]
        self.subtitle_params = fonts["subtitle"]
        self.button_params = fonts["button"]

    @property
    def title(self) -> wx.Font:
        return self.__get_font(self.title_params)

    @property
    def subtitle(self) -> wx.Font:
        return self.__get_font(self.subtitle_params)

    @property
    def button(self) -> wx.Font:
        return self.__get_font(self.button_params)

    def __get_font(self, params: FontJson) -> wx.Font:
        return wx.Font(wx.FontInfo(params["size"]))


singleton: Fonts = Fonts()
