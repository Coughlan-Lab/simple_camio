from ..screen import Screen
import gui
from res import Fonts, Colors
import wx
from view.accessibility import AccessibleText


class NoCamera(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(self, gui, parent, show_back=True, name="No camera detected")

        self.title = AccessibleText(self, wx.ID_ANY, label="No camera detected")
        self.title.SetForegroundColour(Colors.text)
        self.title.SetFont(Fonts.title)

        description = AccessibleText(
            self,
            wx.ID_ANY,
            label="Please, connect one via USB",
            style=wx.ALIGN_CENTRE_HORIZONTAL,
        )
        description.SetForegroundColour(Colors.text)
        description.SetFont(Fonts.subtitle)

        retry = wx.Button(self, wx.ID_ANY, "Retry")
        retry.SetForegroundColour(Colors.button_text)
        retry.SetFont(Fonts.button)
        retry.Bind(wx.EVT_BUTTON, self.on_retry)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddStretchSpacer(1)
        sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        sizer.Add(description, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        sizer.Add(retry, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 50)
        sizer.AddStretchSpacer(2)

        self.SetSizerAndFit(sizer)

    def on_focus(self) -> None:
        self.title.SetFocus()

    def on_retry(self, event) -> None:
        self.gui.back()
