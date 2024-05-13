from model import State
from res import Fonts, Colors, ImgsManager, DocsManager
from ..screen import Screen
import gui
from model.utils import open_file
import wx
from view.accessibility import AccessibleText, AccessibleDescription
from model import utils


class PointerSelector(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(
            self, gui, parent, show_back=True, name="Pointer selection screen"
        )

        self.title = AccessibleText(self, wx.ID_ANY, label="Choose pointing option:")
        self.title.SetForegroundColour(Colors.text)
        self.title.SetFont(Fonts.title)

        description = AccessibleText(
            self,
            wx.ID_ANY,
            label="If you want to use the stylus, print it before proceeding",
        )
        description.SetForegroundColour(Colors.text)
        description.SetFont(Fonts.subtitle)

        finger_btn = wx.Button(self, wx.ID_ANY, "Finger")
        finger_btn.SetForegroundColour(Colors.button_text)
        finger_btn.SetFont(Fonts.button)
        finger_btn.Bind(wx.EVT_BUTTON, lambda _: self.on_select(State.Pointer.FINGER))

        stylus_box = wx.Panel(self, wx.ID_ANY)
        stylus_box_sizer = wx.BoxSizer(wx.HORIZONTAL)

        stylus_btn = wx.Button(
            stylus_box,
            wx.ID_ANY,
            label="Stylus",
        )
        stylus_btn.SetForegroundColour(Colors.button_text)
        stylus_btn.SetFont(Fonts.button)
        stylus_btn.Bind(wx.EVT_BUTTON, lambda _: self.on_select(State.Pointer.STYLUS))
        stylus_box_sizer.Add(stylus_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 1)

        printer_icon = wx.Bitmap(ImgsManager.printer, wx.BITMAP_TYPE_ANY)
        wx.Bitmap.Rescale(printer_icon, (25, 25))
        self.print_stylus_btn = wx.BitmapButton(
            stylus_box,
            wx.ID_ANY,
            bitmap=printer_icon,
        )
        if utils.SYSTEM == utils.OS.WINDOWS:
            self.print_stylus_btn.SetAccessible(
                AccessibleDescription(name="Print stylus")
            )
        self.print_stylus_btn.Bind(wx.EVT_BUTTON, self.print_marker)
        stylus_box_sizer.Add(
            self.print_stylus_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 1
        )

        stylus_box.SetSizerAndFit(stylus_box_sizer)
        """
        icon = wx.Bitmap(ImgsManager.question_mark, wx.BITMAP_TYPE_ANY)
        wx.Bitmap.Rescale(icon, (25, 25))
        tutorial = wx.BitmapButton(
            self,
            wx.ID_HELP,
            size=(40, 40),
            bitmap=icon,
        )
        if utils.SYSTEM == utils.OS.WINDOWS:
            tutorial.SetAccessible(AccessibleDescription(name="Rewatch tutorial"))

        tutorial.Bind(wx.EVT_BUTTON, self.show_tutorial)
        """

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        buttons_sizer.Add(finger_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 50)
        buttons_sizer.Add(stylus_box, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 50)

        sizer = wx.BoxSizer(wx.VERTICAL)

        tutorial_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # tutorial_sizer.Add(tutorial, 0, wx.RIGHT)
        tutorial_sizer.AddSpacer(40)

        sizer.AddSpacer(30)
        sizer.Add(tutorial_sizer, 0, wx.ALL | wx.ALIGN_RIGHT)
        sizer.AddStretchSpacer(1)
        sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        sizer.Add(description, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        sizer.Add(buttons_sizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 50)
        sizer.AddStretchSpacer(2)

        self.SetSizerAndFit(sizer)

    def on_focus(self) -> None:
        state = self.gui.current_state
        state.clear_pointer()
        self.title.SetFocus()

    def on_select(self, pointer: State.Pointer) -> None:
        self.gui.current_state.pointer = pointer
        self.gui.show_screen(gui.ScreenName.CameraSelector)

    def print_marker(self, event) -> None:
        open_file(DocsManager.marker_pointer)

    def show_tutorial(self, event) -> None:
        self.gui.show_screen(gui.ScreenName.ContentVideoTutorial)
