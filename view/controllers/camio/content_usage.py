from ..screen import Screen
import gui
from view.utils import Camera, FrameViewer
from typing import Optional
from res import Fonts, Colors, ImgsManager
from model import utils, State, get_frame_processor, FrameProcessor
import cv2
import numpy as np
import threading
import wx
from view.accessibility import AccessibleText, AccessibleDescription


class ContentUsage(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(self, gui, parent, show_back=True, name="Content usage screen")

        self.title = AccessibleText(self, wx.ID_ANY, style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.title.SetForegroundColour(Colors.text)
        self.title.SetFont(Fonts.title)

        self.preview = FrameViewer(self, (600, 350))

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

        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title_sizer.AddSpacer(80)
        title_sizer.AddStretchSpacer(1)
        title_sizer.Add(
            self.title, 1, wx.TOP | wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 50
        )
        title_sizer.AddStretchSpacer(1)
        title_sizer.Add(tutorial, 0, wx.TOP | wx.ALIGN_TOP, 30)
        title_sizer.AddSpacer(40)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(title_sizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(
            self.preview,
            1,
            wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_HORIZONTAL | wx.SHAPED,
            10,
        )
        sizer.AddSpacer(50)

        self.SetSizerAndFit(sizer)

        self.camera = Camera()
        self.camera.set_on_error_listener(self.preview.show_error)
        self.camera.set_frame_listener(self.on_frame)

        self.semaphore = threading.Semaphore()
        self.frame_processor: Optional[FrameProcessor] = None

    def on_focus(self) -> None:
        self.set_title()

        state = self.gui.current_state

        try:
            self.frame_processor = get_frame_processor(
                state.content, state.pointer, state.get_calibration_filename()
            )
            self.camera.start_by_capture(state.camera.capture)
        except:
            self.preview.show_error("Error reading content\nconfiguration file")

        self.title.SetFocus()
        utils.prevent_sleep()

    def set_title(self) -> None:
        pointer_text: str
        if self.gui.current_state.pointer == State.Pointer.FINGER:
            pointer_text = "your finger"
        else:
            pointer_text = "the drop stylus"

        self.title.SetLabel(
            f"Frame the content with your camera and\nuse {pointer_text} to select an object"
        )

        self.Layout()

    def on_unfocus(self) -> None:
        self.camera.stop()

        if self.frame_processor is not None:
            self.frame_processor.destroy()
        del self.frame_processor

        utils.allow_sleep()

    def on_frame(self, img: np.ndarray) -> None:
        if self.frame_processor is None or self.semaphore.acquire(blocking=False):
            return

        try:
            img = self.frame_processor.process(img)
            self.preview.show_frame(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        except:
            self.preview.show_error("Error reading content configuration file")

        self.semaphore.release()

    def show_tutorial(self) -> None:
        self.gui.show_screen(gui.ScreenName.ContentVideoTutorial)
