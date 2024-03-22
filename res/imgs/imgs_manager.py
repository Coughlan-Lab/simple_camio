import os


class ImgsManager:
    IMGS_DIR = os.path.dirname(__file__)

    def __init__(self) -> None:
        self.back_arrow = os.path.join(ImgsManager.IMGS_DIR, "back_arrow.png")
        self.printer = os.path.join(ImgsManager.IMGS_DIR, "printer.png")
        self.question_mark = os.path.join(ImgsManager.IMGS_DIR, "question_mark.png")
        self.template = os.path.join(ImgsManager.IMGS_DIR, "template.png")
        self.loading_spinner = os.path.join(ImgsManager.IMGS_DIR, "loading_spinner.gif")


singleton: ImgsManager = ImgsManager()
