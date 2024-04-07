import os


class ImgManager:
    IMGS_DIR = os.path.dirname(__file__)

    def __init__(self) -> None:
        self.back_arrow = os.path.join(ImgManager.IMGS_DIR, "back_arrow.png")
        self.left_arrow = os.path.join(ImgManager.IMGS_DIR, "left_arrow.png")
        self.right_arrow = os.path.join(ImgManager.IMGS_DIR, "right_arrow.png")
        self.printer = os.path.join(ImgManager.IMGS_DIR, "printer.png")
        self.question_mark = os.path.join(ImgManager.IMGS_DIR, "question_mark.png")
        self.template = os.path.join(ImgManager.IMGS_DIR, "template.png")
        self.loading_spinner = os.path.join(ImgManager.IMGS_DIR, "loading_spinner.gif")


singleton: ImgManager = ImgManager()
