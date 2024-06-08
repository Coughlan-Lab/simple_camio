from enum import Enum
from token import STAR
from view.utils import LoadingSpinner
import gui
import cv2
from model.utils import enumerate_cameras
from .camera_preview import CameraPreview
from ..screen import Screen
from res import Fonts, Colors
from typing import Any, List, Tuple
import threading
import wx
from view.accessibility import AccessibleText
from model import utils


class CameraStatus(Enum):
    LOADING = 0
    LOADED = 1
    STARTED = 2
    ERROR = 3


EVT_CAMERA_ID = wx.NewId()


def EVT_CAMERA(win, func):
    win.Connect(-1, -1, EVT_CAMERA_ID, func)


class CameraEvent(wx.PyEvent):
    def __init__(self, status: CameraStatus, data: Any = None):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_CAMERA_ID)
        self.status = status
        self.data = data


class CameraSelector(Screen):
    MAX_CAMERAS = 3

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(
            self, gui, parent, show_back=True, name="Camera selection screen"
        )

        self.title = AccessibleText(self, wx.ID_ANY, label="Select a camera:")
        self.title.SetForegroundColour(Colors.text)
        self.title.SetFont(Fonts.title)

        self.previewSizer = wx.GridSizer(cols=3, gap=(20, 5))
        self.loading = LoadingSpinner(self)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(50)
        sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddStretchSpacer(2)
        sizer.Add(self.previewSizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.loading, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddStretchSpacer(1)

        self.SetSizerAndFit(sizer)

        self.previews: List[CameraPreview] = list()

        EVT_CAMERA(self, self.on_camera_event)

    def on_focus(self) -> None:
        self.show_loading()
        self.on_unfocus()

        state = self.gui.current_state
        state.clear_camera()
        threading.Thread(target=self.load_cameras).start()

    def on_camera_event(self, event: CameraEvent) -> None:
        if event.status == CameraStatus.LOADING:
            pass
        elif event.status == CameraStatus.LOADED:
            self.on_cameras_loaded(event.data)
        elif event.status == CameraStatus.STARTED:
            self.on_camera_started()
        else:
            self.on_camera_error()

    def load_cameras(self) -> None:
        wx.PostEvent(self, CameraEvent(CameraStatus.LOADING))
        try:
            cameras = enumerate_cameras(cv2.CAP_MSMF)
            wx.PostEvent(self, CameraEvent(CameraStatus.LOADED, cameras))
        except Exception as e:
            wx.PostEvent(self, CameraEvent(CameraStatus.ERROR))

    def on_cameras_loaded(self, cameras: List[utils.CameraInfo]) -> None:
        self.previews.clear()

        if len(cameras) == 0:
            wx.PostEvent(self, CameraEvent(CameraStatus.ERROR))
            return

        for camera_info in cameras:
            if len(self.previews) >= CameraSelector.MAX_CAMERAS:
                break
            preview = CameraPreview(self, camera_info)
            preview.Hide()
            self.previews.append(preview)

        threading.Thread(target=self.start_cameras).start()

    def start_cameras(self) -> None:
        for preview in self.previews:
            preview.start()

        wx.PostEvent(self, CameraEvent(CameraStatus.STARTED))

    def on_camera_started(self) -> None:
        for preview in self.sort_previews(self.previews):
            self.previewSizer.Add(preview, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL)

        if len(self.previews) == 0:
            self.gui.show_screen(gui.ScreenName.NoCamera)
        else:
            self.hide_loading()

    def on_camera_error(self) -> None:
        self.gui.show_screen(gui.ScreenName.NoCamera)

    def show_loading(self) -> None:
        for preview in self.previews:
            preview.Hide()

        self.loading.Show()
        self.loading.SetFocus()

        self.Layout()

    def hide_loading(self) -> None:
        self.loading.Hide()
        for preview in self.previews:
            preview.Show()

        self.title.SetFocus()
        self.Layout()

    def on_unfocus(self) -> None:
        for preview in self.previews:
            preview.stop()
            preview.Destroy()
        self.previewSizer.Clear()
        self.previews.clear()

    def sort_previews(
        self, previews: List[CameraPreview]
    ) -> Tuple[wx.Window, wx.Window, wx.Window]:
        previews.sort(key=lambda p: p.camera_name)

        if len(previews) == 0:
            return (
                self.getPlaceholderView(),
                self.getPlaceholderView(),
                self.getPlaceholderView(),
            )
        if len(previews) == 1:
            return (self.getPlaceholderView(), previews[0], self.getPlaceholderView())
        if len(previews) == 2:
            return (previews[0], self.getPlaceholderView(), previews[1])
        return (previews[0], previews[1], previews[2])

    def getPlaceholderView(self):
        return wx.Panel(self, wx.ID_ANY)
