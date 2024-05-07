from res import ImgsManager
from typing import Optional
import gui
import wx
from view.accessibility import AccessibleDescription


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
        name: str = "",
        show_back: bool = False,
    ) -> None:
        wx.Panel.__init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, name=name)
        self.gui = gui

        back_arrow = wx.Bitmap(ImgsManager.back_arrow, wx.BITMAP_TYPE_ANY)
        wx.Bitmap.Rescale(back_arrow, (25, 25))
        self.back_button = wx.BitmapButton(
            self,
            wx.ID_BACKWARD,
            pos=(40, 30),
            size=(40, 40),
            bitmap=back_arrow,
        )
        self.back_button.SetAccessible(AccessibleDescription(name="Back"))

        self.back_button.Bind(wx.EVT_BUTTON, self.back)

        if show_back:
            self.show_back()
        else:
            self.hide_back()

        self.Bind(wx.EVT_KILL_FOCUS, self.on_unfocus)

    def SetFocus(self, focus: bool) -> None:
        if focus:
            self.on_focus()
            self.Show()
        else:
            self.on_unfocus()
            self.Hide()
    
    def on_focus(self) -> None:
        pass

    def on_unfocus(self) -> None:
        pass

    def show_back(self) -> None:
        self.back_button.Show()

    def hide_back(self) -> None:
        self.back_button.Hide()

    def back(self, event) -> None:
        self.gui.back(self.back_screen)
