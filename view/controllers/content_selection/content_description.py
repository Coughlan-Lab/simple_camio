from email.mime import base
import os

from model import Content
from res import Colors, Fonts, ImgsManager
from ..screen import Screen
import gui
from model.utils import open_file
import wx
from view.accessibility import AccessibleText


class ContentDescription(Screen):
    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(
            self, gui, parent, show_back=True, name="Content description screen"
        )

        self.title = AccessibleText(self, wx.ID_ANY)
        self.title.SetForegroundColour(Colors.text)
        self.title.SetFont(Fonts.title)

        self.description = AccessibleText(
            self,
            wx.ID_ANY,
            style=wx.ALIGN_CENTRE_HORIZONTAL | wx.ST_ELLIPSIZE_END,
            size=(self.GetSize()[0] * 3 / 4, wx.DefaultSize[1]),
        )
        self.description.SetForegroundColour(Colors.text)
        self.description.SetFont(Fonts.subtitle)

        instructions = AccessibleText(
            self,
            wx.ID_ANY,
            label="Print a copy of the content and proceed",
        )
        instructions.SetForegroundColour(Colors.text)
        instructions.SetFont(Fonts.subtitle)
        instructions.SetCanFocus(True)

        self.reshaped = False
        self.preview = wx.StaticBitmap(
            self, wx.ID_ANY, name="Content map preview", style=wx.BORDER_SIMPLE
        )

        self.preview_error = wx.StaticBox(self, wx.ID_ANY, size=(600, 200))
        preview_error_text = AccessibleText(
            self.preview_error,
            wx.ID_ANY,
            label="No preview found",
            style=wx.ALIGN_CENTER,
        )
        preview_error_text.CenterOnParent()
        preview_error_text.SetForegroundColour(Colors.text)
        preview_error_text.SetFont(Fonts.subtitle)
        preview_error_sizer = wx.BoxSizer(wx.VERTICAL)
        preview_error_sizer.AddStretchSpacer(1)
        preview_error_sizer.Add(
            preview_error_text, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL
        )
        preview_error_sizer.AddStretchSpacer(1)
        self.preview_error.SetSizer(preview_error_sizer)
        self.preview_error.Hide()

        printer_icon = wx.Bitmap(ImgsManager.printer, wx.BITMAP_TYPE_ANY)
        wx.Bitmap.Rescale(printer_icon, (25, 25))
        self.print = wx.Button(self, wx.ID_ANY, "Content")
        self.print.SetForegroundColour(Colors.button_text)
        self.print.SetFont(Fonts.button)
        self.print.SetBitmap(printer_icon)
        self.print.SetBitmapPosition(wx.LEFT)
        self.print.Bind(wx.EVT_BUTTON, self.print_content)

        self.proceed = wx.Button(self, wx.ID_ANY, "Proceed")
        self.proceed.SetForegroundColour(Colors.button_text)
        self.proceed.SetFont(Fonts.button)
        self.proceed.Bind(wx.EVT_BUTTON, self.on_proceed)

        buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        buttons_sizer.Add(self.print, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 50)
        buttons_sizer.Add(self.proceed, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 50)

        preview_error_sizer = wx.BoxSizer(wx.VERTICAL)

        preview_error_sizer.AddSpacer(50)
        preview_error_sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        preview_error_sizer.Add(
            self.description, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5
        )
        preview_error_sizer.Add(instructions, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        preview_error_sizer.Add(
            self.preview, 1, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10
        )
        preview_error_sizer.Add(
            self.preview_error, 1, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10
        )
        preview_error_sizer.Add(buttons_sizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        preview_error_sizer.AddSpacer(50)

        self.SetSizerAndFit(preview_error_sizer)

        self.preview.Bind(wx.EVT_SIZE, self.on_resize)

    def on_resize(self, event: wx.SizeEvent) -> None:
        if self.reshaped:
            self.reshaped = False
            event.Skip()
            return

        preview = self.content.preview

        if preview is None:
            self.show_preview_error()
        else:
            self.show_preview(preview)

        event.Skip()

    def on_focus(self) -> None:
        self.title.SetLabel(self.content.full_name)
        self.description.SetLabel(self.content.description)

        preview = self.content.preview
        if preview is None:
            self.show_preview_error()
        else:
            self.show_preview(preview)

        if os.path.exists(self.content.to_print):
            self.print.Enable()
        else:
            self.print.Disable()

        self.title.SetFocus()

    def show_preview_error(self) -> None:
        self.preview_error.Show()
        self.preview.Hide()
        self.print.Disable()
        self.Layout()

    def show_preview(self, preview: str) -> None:
        img = wx.Bitmap(preview, wx.BITMAP_TYPE_ANY)
        self.reshape_img(img)
        self.preview.SetBitmap(img)

        self.preview.Show()
        self.preview_error.Hide()

        self.print.Enable()
        self.Layout()

    def reshape_img(self, img: wx.Bitmap) -> None:
        base_size = self.preview.GetSize()
        base_size[0] = self.GetSize()[0] * 3 / 4
        if base_size[1] == 0:
            return

        w, h = img.GetSize()
        if base_size[0] == w and base_size[1] == h:
            return

        if w > h:
            image_size = (
                base_size[0],
                int(h * base_size[0] / w),
            )
            if image_size[1] > base_size[1]:
                image_size = (
                    int(w * base_size[1] / h),
                    base_size[1],
                )
        else:  # h > w
            image_size = (
                int(w * base_size[1] / h),
                base_size[1],
            )
            if image_size[0] > base_size[0]:
                self.image_size = (
                    base_size[0],
                    int(h * base_size[0] / w),
                )

        wx.Bitmap.Rescale(img, image_size)
        self.preview.SetSize(image_size)
        self.reshaped = True

    @property
    def content(self) -> Content:
        return self.gui.current_state.content

    def print_content(self, event) -> None:
        open_file(self.content.to_print)

    def on_proceed(self, event) -> None:
        if self.gui.current_state.content_tutorial_watched:
            next_screen = gui.ScreenName.PointerSelector
        else:
            # next_screen = gui.ScreenName.ContentVideoTutorial
            next_screen = gui.ScreenName.PointerSelector
        self.gui.show_screen(next_screen)
