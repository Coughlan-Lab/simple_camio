from typing import Optional, Tuple, Union
from res import Fonts, Colors
import numpy as np
import wx
import cv2
from view.accessibility import AccessibleText


class FrameViewer(wx.Panel):
    def __init__(
        self,
        parent: wx.Panel,
        size: Tuple[int, int],
        name: str = "Camera preview",
    ):
        wx.Panel.__init__(self, parent, wx.ID_ANY, size=size, name=name)

        self.default_frame_size = size
        self.frame_size = size

        self.bitmap: Optional[wx.Bitmap] = None
        self.img_size: Optional[Tuple[int, int]] = None
        self.erase_background: bool = True

        self.error_box = wx.StaticBox(self, wx.ID_ANY, size=size)

        self.error_text = AccessibleText(
            self.error_box,
            wx.ID_ANY,
            style=wx.ALIGN_CENTER,
            size=(self.error_box.GetSize()[0] - 2, wx.DefaultSize[1]),
        )
        self.error_text.CenterOnParent()
        self.error_text.SetForegroundColour(Colors.text)
        error_font = Fonts.subtitle
        error_font.SetPointSize(error_font.GetPointSize() - 2)
        self.error_text.SetFont(error_font)
        self.error_box.Hide()

        self.CenterOnParent()

        self.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)

    def on_size(self, event: wx.SizeEvent) -> None:
        self.default_frame_size = event.GetSize()

        if self.img_size is None:
            return

        self.__init_bitmap(self.img_size[0], self.img_size[1])
        self.erase_background = True
        event.Skip()

    def show_error(self, msg: str = "Error getting frames") -> None:
        self.bitmap = None
        self.error_text.SetLabel(msg)
        self.error_text.Wrap(self.error_box.GetSize()[0] - 2)
        self.error_text.CenterOnParent()
        self.error_box.Show()

    def show_frame(self, img: np.ndarray) -> None:
        if self.bitmap is None:
            self.__init_bitmap(img.shape[1], img.shape[0])
            self.error_box.Hide()

        img = cv2.resize(img, self.frame_size)

        self.bitmap.CopyFromBuffer(img)
        self.Refresh()

    def on_paint(self, event: wx.PaintEvent) -> None:
        if self.bitmap is not None:
            dc = wx.PaintDC(self)
            dc.DrawBitmap(
                self.bitmap,
                (self.GetSize()[0] - self.bitmap.GetWidth()) / 2,
                (self.GetSize()[1] - self.bitmap.GetHeight()) / 2,
                True,
            )

    def __init_bitmap(self, w: int, h: int) -> None:
        self.img_size = (w, h)

        self.__init_frame_size(w, h)

        self.image = wx.Image(self.frame_size[0], self.frame_size[1])
        self.bitmap = wx.Bitmap(self.image)

    def __init_frame_size(self, w: int, h: int) -> None:
        if w > h:
            self.frame_size = (
                self.default_frame_size[0],
                int(h * self.default_frame_size[0] / w),
            )
            if self.frame_size[1] > self.default_frame_size[1]:
                self.frame_size = (
                    int(w * self.default_frame_size[1] / h),
                    self.default_frame_size[1],
                )
        else:  # h > w
            self.frame_size = (
                int(w * self.default_frame_size[1] / h),
                self.default_frame_size[1],
            )
            if self.frame_size[0] > self.default_frame_size[0]:
                self.frame_size = (
                    self.default_frame_size[0],
                    int(h * self.default_frame_size[0] / w),
                )

    def on_erase_background(self, event):
        """Intentionally empty to reduce flickering."""
        if self.erase_background:
            self.erase_background = False
            event.Skip()
