import json


class Colors:
    COLORS_FILE = "res/colors.json"

    def __init__(self):
        with open(Colors.COLORS_FILE, "r") as file:
            colors = json.load(file)
        self.background = colors["background"]
        self.hover = colors["hover"]
        self.transparent = "transparent"


Colors = Colors()
