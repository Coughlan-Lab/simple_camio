import os


class ImgsManager:
    IMGS_DIR = os.path.dirname(__file__)

    def __init__(self):
        self.back_arrow = os.path.join(ImgsManager.IMGS_DIR, "back_arrow.png")
        self.printer = os.path.join(ImgsManager.IMGS_DIR, "printer.png")


ImgsManager = ImgsManager()
