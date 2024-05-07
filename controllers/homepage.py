import gui
from controllers.screen import Screen
from model import ContentManager
from res import Fonts, Colors
import wx


class HomePage(Screen):
    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(self, gui, parent)

        title = wx.StaticText(self, wx.ID_ANY, label="CamIO")
        title.SetForegroundColour(Colors.text)
        title.SetFont(Fonts.title)

        description = wx.StaticText(
            self,
            wx.ID_ANY,
            label="CamIO is an accessibility tool for visually impaired people",
            style=wx.ALIGN_CENTRE_HORIZONTAL,
        )
        description.SetForegroundColour(Colors.text)
        description.SetFont(Fonts.subtitle)

        start = wx.Button(self, wx.ID_ANY, "Start")
        start.SetBackgroundColour(Colors.button)
        start.SetForegroundColour(Colors.button_text)
        start.SetFont(Fonts.button)
        start.Bind(wx.EVT_BUTTON, self.show_content_selector)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddStretchSpacer(1)
        sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 50)
        sizer.Add(description, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10)
        sizer.Add(start, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 50)
        sizer.AddStretchSpacer(2)

        self.SetSizerAndFit(sizer)

    def show_content_selector(self, event) -> None:
        if not ContentManager.has_content_dir():
            next_screen = gui.ScreenName.NoContent
        else:
            next_screen = gui.ScreenName.ContentSelector
        self.gui.show_screen(next_screen)
