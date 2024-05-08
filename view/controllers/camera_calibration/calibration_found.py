from ..screen import Screen
import gui
from res import Fonts, Colors
import wx
from view.accessibility import AccessibleText


class CalibrationFound(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.CameraSelector

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(
            self, gui, parent, show_back=True, name="Calibration data found"
        )

        self.title = AccessibleText(self, wx.ID_ANY, label="Calibration data found")
        self.title.SetForegroundColour(Colors.text)
        self.title.SetFont(Fonts.title)

        description = AccessibleText(
            self,
            wx.ID_ANY,
            label="Please, run calibration again if this is not the last camera you used",
            style=wx.ALIGN_CENTRE_HORIZONTAL,
        )
        description.SetForegroundColour(Colors.text)
        description.SetFont(Fonts.subtitle)

        calibrate_btn = wx.Button(self, wx.ID_ANY, "Calibrate")
        calibrate_btn.SetForegroundColour(Colors.button_text)
        calibrate_btn.SetFont(Fonts.button)
        calibrate_btn.Bind(wx.EVT_BUTTON, self.on_calibrate)

        proceed_btn = wx.Button(self, wx.ID_ANY, "Proceed")
        proceed_btn.SetForegroundColour(Colors.button_text)
        proceed_btn.SetFont(Fonts.button)
        proceed_btn.Bind(wx.EVT_BUTTON, self.on_proceed)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        buttons_sizer.Add(calibrate_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 50)
        buttons_sizer.Add(proceed_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 50)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddStretchSpacer(1)
        sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        sizer.Add(description, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        sizer.Add(buttons_sizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 50)
        sizer.AddStretchSpacer(2)

        self.SetSizerAndFit(sizer)

    def on_focus(self) -> None:
        self.title.SetFocus()

    def on_calibrate(self, event) -> None:
        self.gui.show_screen(gui.ScreenName.Calibration)

    def on_proceed(self, event) -> None:
        self.gui.show_screen(gui.ScreenName.ContentUsage)
