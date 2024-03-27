import json


class Colors:
    COLORS_FILE = "res/colors.json"

    def __init__(self) -> None:
        with open(Colors.COLORS_FILE, "r") as file:
            colors = json.load(file)
        self.background = colors["background"]
        self.hover = colors["hover"]
        self.button = colors["button"]
        self.text = colors["text"]
        self.button_text = colors["button_text"]
        self.transparent = "transparent"

singleton: Colors = Colors()
