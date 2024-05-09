import gui
from res import Fonts, Colors
from ..screen import Screen
from view.utils import Camera
from view.utils import FrameViewer
import cv2
import numpy as np
from model import utils
import wx


class CameraPreview(wx.Panel):
    def __init__(
        self,
        parent: Screen,
        camera_info: utils.CameraInfo,
    ):
        wx.Panel.__init__(
            self, parent, wx.ID_ANY, size=(100, 100), name=f"{camera_info.name} preview"
        )

        self.parent = parent
        self.camera = camera_info

        self.button = wx.Button(self, wx.ID_ANY, label=f"{camera_info.name}")
        self.button.SetForegroundColour(Colors.button_text)
        self.button.SetFont(Fonts.button)
        self.button.Bind(wx.EVT_BUTTON, self.on_click)

        self.preview = FrameViewer(
            self, size=(250, 250), name=f"{camera_info.name} preview"
        )

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(self.button, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddSpacer(10)
        sizer.Add(self.preview, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)

        self.SetSizerAndFit(sizer)

        self.frame_producer = Camera()

        self.frame_producer.set_on_error_listener(self.show_error)
        self.frame_producer.set_frame_listener(self.show_frame)

        self.frame_received = False

    @property
    def gui(self) -> "gui.MainFrame":
        return self.parent.gui

    @property
    def camera_index(self) -> int:
        return self.camera.index

    @property
    def camera_name(self) -> str:
        return self.camera.name

    @property
    def running(self) -> bool:
        return self.frame_received and self.frame_producer.running

    def start(self) -> None:
        self.frame_producer.start_by_index(self.camera_index)

    def show_error(self) -> None:
        self.button.Disable()
        self.preview.show_error(msg=f"Error getting frames\nfrom {self.camera_name}")
        self.frame_received = False

    def show_frame(self, img: np.ndarray) -> None:
        self.button.Enable()
        self.preview.show_frame(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        self.frame_received = True

    def stop(self) -> None:
        self.frame_producer.stop()

    def on_click(self, event) -> None:
        g = self.gui
        state = g.current_state

        state.set_camera(self.camera, self.frame_producer.acquire_capture())

        if state.pointer == state.Pointer.FINGER and state.content.is_2D():
            next_screen = gui.ScreenName.ContentUsage
        elif state.is_calibrated(self.camera_name):
            if utils.SYSTEM == utils.OS.MACOS:
                next_screen = gui.ScreenName.CalibrationFound
            else:
                next_screen = gui.ScreenName.ContentUsage
        elif state.calibration_tutorial_watched:
            next_screen = gui.ScreenName.Calibration
        else:
            next_screen = gui.ScreenName.CalibrationVideoTutorial
            #next_screen = gui.ScreenName.Calibration
        g.show_screen(next_screen)
