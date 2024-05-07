# from view.utils import LoadingSpinner
from numpy import place
import gui
import cv2
from model.utils import enumerate_cameras
from .camera_preview import CameraPreview
from ..screen import Screen
from res import Fonts, Colors
from typing import List, Tuple
import threading
import wx
from view.accessibility import AccessibleText


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

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(50)
        sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddStretchSpacer(2)
        sizer.Add(self.previewSizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddStretchSpacer(1)

        self.SetSizerAndFit(sizer)

        self.previews: List[CameraPreview] = list()

        # self.loading = LoadingSpinner(self)

    def on_focus(self) -> None:
        self.show_loading()
        state = self.gui.current_state
        state.clear_camera()
        # threading.Thread(target=self.__load_cameras).start()
        self.__load_cameras()

    def __load_cameras(self) -> None:
        self.init_cameras()

        for preview in self.previews:
            preview.start()

        wx.CallAfter(self.show_cameras)

    def init_cameras(self) -> None:
        self.previews.clear()

        for camera_info in enumerate_cameras(cv2.CAP_MSMF):
            if len(self.previews) >= CameraSelector.MAX_CAMERAS:
                break
            preview = CameraPreview(self, camera_info)
            self.previews.append(preview)

        if len(self.previews) == 0:
            self.gui.show_screen(gui.ScreenName.NoContent)

    def show_cameras(self) -> None:
        for preview in self.sort_previews(self.previews):
            self.previewSizer.Add(preview, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)

        self.hide_loading()
        self.title.SetFocus()

    def show_loading(self) -> None:
        # self.loading.Show()
        self.Layout()

    def hide_loading(self) -> None:
        # self.loading.Hide()
        self.Layout()

    def on_unfocus(self) -> None:
        for preview in self.previews:
            preview.stop()
            preview.Destroy()
        self.previews.clear()

    def sort_previews(
        self, previews: List[CameraPreview]
    ) -> Tuple[wx.Window, wx.Window, wx.Window]:
        previews.sort(key=lambda p: p.camera_name)
        placeholder_panel = wx.Panel(self, wx.ID_ANY)
        
        if len(previews) == 0:
            return (placeholder_panel, placeholder_panel, placeholder_panel)
        if len(previews) == 1:
            return (placeholder_panel, previews[0], placeholder_panel)
        if len(previews) == 2:
            return (previews[0], placeholder_panel, previews[1])
        return (previews[0], previews[1], previews[2])
