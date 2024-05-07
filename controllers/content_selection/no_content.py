import os
import gui
from controllers.screen import Screen
from res import Fonts, Colors
import wx


class NoContent(Screen):
    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(self, gui, parent, show_back=True)

        title = wx.StaticText(
            self, wx.ID_ANY, label="CamIO Content directory not found"
        )
        title.SetForegroundColour(Colors.text)
        title.SetFont(Fonts.title)

        description = wx.StaticText(
            self,
            wx.ID_ANY,
            label="Please, select its location",
            style=wx.ALIGN_CENTRE_HORIZONTAL,
        )
        description.SetForegroundColour(Colors.text)
        description.SetFont(Fonts.subtitle)

        select = wx.Button(
            self, wx.ID_ANY, "Select", wx.DefaultPosition, wx.DefaultSize, 0
        )
        select.SetBackgroundColour(Colors.button)
        select.SetForegroundColour(Colors.button_text)
        select.SetFont(Fonts.button)
        select.Bind(wx.EVT_BUTTON, self.show_directory_dialog)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddStretchSpacer(1)
        sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 50)
        sizer.Add(description, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10)
        sizer.Add(select, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 50)
        sizer.AddStretchSpacer(2)

        self.SetSizerAndFit(sizer)

    def show_directory_dialog(self, event) -> None:
        with wx.DirDialog(
            self,
            "Select content directory",
            defaultPath=os.path.expanduser("~"),
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return

            content_dir = dialog.GetPath()

        if content_dir is None or content_dir == "":
            return

        self.gui.current_state.set_content_dir(content_dir)

        self.gui.show_screen(gui.ScreenName.ContentSelector)
