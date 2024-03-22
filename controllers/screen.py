import customtkinter as tk  # type: ignore
from tkinter.constants import CENTER
from PIL import Image
from res import Colors, ImgsManager
from typing import Optional, Union
import gui


class Screen(tk.CTkFrame):
    @property
    def back_screen(self) -> Optional["gui.ScreenName"]:
        return None

    def __init__(
        self,
        gui: "gui.GUI",
        parent: Union[tk.CTkFrame, tk.CTk],
        show_back: bool = False,
    ) -> None:
        tk.CTkFrame.__init__(self, parent)
        self.gui = gui

        self.configure(fg_color=Colors.background)

        self.back_button = tk.CTkButton(
            self,
            text="",
            image=tk.CTkImage(
                light_image=Image.open(ImgsManager.back_arrow), size=(25, 25)
            ),
            anchor=CENTER,
            width=10,
            height=30,
            corner_radius=50,
            fg_color=Colors.transparent,
        )
        self.back_button.configure(command=self.back)

        if show_back and self.back_screen is not None:
            self.show_back()

    def focus(self) -> None:
        pass

    def unfocus(self) -> None:
        pass

    def show_back(self) -> None:
        self.back_button.place(x=40, y=30, anchor=CENTER)

    def hide_back(self) -> None:
        self.back_button.place_forget()

    def back(self) -> None:
        if not self.back_screen:
            return
        self.gui.show_screen(self.back_screen)
