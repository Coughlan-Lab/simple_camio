from PIL import Image
from res import Colors, ImgsManager
from typing import Optional, Union
import gui
import wx


class Screen(wx.Panel):
    @property
    def name(self) -> str:
        return self.__class__.__qualname__

    @property
    def back_screen(self) -> Optional["gui.ScreenName"]:
        return None

    def __init__(
        self,
        gui: "gui.MainFrame",
        parent: wx.Frame,
        show_back: bool = False,
    ) -> None:
        wx.Panel.__init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition)
        self.gui = gui
        """
        self.m_button2 = wx.Button(
            self, wx.ID_ANY, "BACK", wx.DefaultPosition, wx.DefaultSize, 0
        )
        bSizer5.Add(self.m_button2, 0, wx.ALL, 5)
        self.SetSizer(bSizer5)
        self.Layout()
        self.m_button2.Bind(wx.EVT_BUTTON, self.back)

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
        """
        if show_back:
            self.show_back()

    def on_focus(self) -> None:
        pass

    def on_unfocus(self) -> None:
        pass

    def show_back(self) -> None:
        self.back_button.place(x=40, y=30, anchor=CENTER)

    def hide_back(self) -> None:
        self.back_button.place_forget()

    def back(self, event) -> None:
        self.gui.back(self.back_screen)
