from turtle import title
from view.utils import Camera, FrameViewer
from ..screen import Screen
import gui
from typing import Any, Dict, Optional
from res import Fonts, Colors, ImgsManager, DocsManager
from model.simple_calibration import Calibration as Calibrator
import numpy as np
import threading
import cv2
from model.utils import open_file
import wx
from view.accessibility import AccessibleText, AccessibleDescription
from model import utils


class Calibration(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.CameraSelector

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(self, gui, parent, show_back=True, name="Calibration screen")

        self.title = AccessibleText(
            self,
            wx.ID_ANY,
            label="Frame the calibration map with you camera\nand match its corners with the on-screen preview",
            style=wx.ALIGN_CENTRE_HORIZONTAL,
        )
        self.title.SetForegroundColour(
            Colors.text,
        )
        self.title.SetFont(Fonts.title)

        self.camera = Camera()
        self.camera.set_on_error_listener(self.on_error)
        self.camera.set_frame_listener(self.on_frame)

        self.preview = FrameViewer(self, (500, 320))

        printer_icon = wx.Bitmap(ImgsManager.printer, wx.BITMAP_TYPE_ANY)
        wx.Bitmap.Rescale(printer_icon, (25, 25))
        self.print = wx.Button(self, wx.ID_ANY, "Calibration map")
        self.print.SetForegroundColour(Colors.button_text)
        self.print.SetFont(Fonts.button)
        self.print.SetBitmap(printer_icon)
        self.print.SetBitmapPosition(wx.LEFT)
        self.print.Bind(wx.EVT_BUTTON, self.print_calibration_map)

        self.confirm = wx.Button(self, wx.ID_ANY, "Confirm")
        self.confirm.SetForegroundColour(Colors.button_text)
        self.confirm.SetFont(Fonts.button)
        self.confirm.Bind(wx.EVT_BUTTON, self.on_confirm)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        buttons_sizer.Add(self.print, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 50)
        buttons_sizer.Add(self.confirm, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 50)

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
        sizer.Add(buttons_sizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)

        self.SetSizerAndFit(sizer)

        self.semaphore = threading.Semaphore()

    def on_focus(self) -> None:
        capture = self.gui.current_state.camera.capture
        self.calibrator = Calibrator(get_calibration_map_dict())
        self.camera.start_by_capture(capture)
        self.title.SetFocus()

    def on_error(self) -> None:
        self.confirm.Disable()
        self.preview.show_error()

    def on_unfocus(self) -> None:
        self.camera.stop()

    def print_calibration_map(self) -> None:
        open_file(DocsManager.calibration_map)

    def on_frame(self, img: np.ndarray) -> None:
        if self.semaphore.acquire(blocking=False):
            return

        focal: Optional[float] = None
        center_x: Optional[float] = None
        center_y: Optional[float] = None

        try:
            img, focal, center_x, center_y = self.calibrator.calibrate(img)
        except:
            self.preview.show_error("Error during calibration")
            return

        self.data = {
            "focal_length_x": focal,
            "focal_length_y": focal,
            "camera_center_x": center_x,
            "camera_center_y": center_y,
        }

        if focal is None or center_x is None or center_y is None:
            self.confirm.Disable()
        else:
            self.confirm.Enable()

        self.preview.show_frame(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

        self.semaphore.release()

    def show_tutorial(self, event) -> None:
        self.gui.show_screen(gui.ScreenName.CalibrationVideoTutorial)

    def on_confirm(self, event) -> None:
        self.camera.acquire_capture()
        self.gui.current_state.save_calibration(self.data)
        self.gui.show_screen(gui.ScreenName.ContentUsage)


def get_calibration_map_dict() -> Dict[str, Any]:
    return {
        "positioningData": {
            "arucoType": "DICT_4X4_50",
            "arucoCodes": [
                {"position": [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]], "id": 0},
                {
                    "position": [
                        [17.0, 0, 0],
                        [19.0, 0, 0],
                        [19.0, 2, 0],
                        [17.0, 2, 0],
                    ],
                    "id": 1,
                },
                {"position": [[0, 24, 0], [2, 24, 0], [2, 26, 0], [0, 26, 0]], "id": 2},
                {
                    "position": [
                        [17.0, 24, 0],
                        [19.0, 24, 0],
                        [19.0, 26, 0],
                        [17.0, 26, 0],
                    ],
                    "id": 3,
                },
            ],
        }
    }
