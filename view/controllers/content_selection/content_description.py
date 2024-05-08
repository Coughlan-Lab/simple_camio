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

        self.image_size = (250, 250)

        self.preview_box = wx.Panel(self, wx.ID_ANY, name="Content map preview")
        self.preview_box.SetBackgroundColour("black")
        self.preview = wx.StaticBitmap(
            self.preview_box, wx.ID_ANY, name="Content map preview"
        )
        preview_sizer = wx.BoxSizer()
        preview_sizer.Add(self.preview, 0, wx.ALL | wx.EXPAND, 2)
        self.preview_box.SetSizer(preview_sizer)
        self.preview.CenterOnParent()

        self.preview_error = wx.StaticBox(self, wx.ID_ANY, size=(600, 200))
        preview_error_text = AccessibleText(
            self.preview_error,
            wx.ID_ANY,
            label="No preview found",
            style=wx.ALIGN_CENTER,
            size=(self.preview_error.GetSize()[0] - 2, wx.DefaultSize[1]),
        )
        preview_error_text.CenterOnParent()
        preview_error_text.SetForegroundColour(Colors.text)
        preview_error_text.SetFont(Fonts.subtitle)
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

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(50)
        sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.description, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        sizer.Add(instructions, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        sizer.AddStretchSpacer(1)
        sizer.Add(self.preview_box, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10)
        sizer.Add(self.preview_error, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10)
        sizer.AddStretchSpacer(1)
        sizer.Add(buttons_sizer, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddSpacer(50)

        self.SetSizerAndFit(sizer)

    def on_focus(self) -> None:
        self.title.SetLabel(self.content.full_name)
        self.description.SetLabel(
            self.content.description
            + self.content.description
            + self.content.description
            + self.content.description
            + self.content.description
            + self.content.description
            + self.content.description
            + self.content.description
            + self.content.description
            + self.content.description
            + self.content.description
        )

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
        self.preview_box.Hide()
        self.print.Disable()
        self.Layout()

    def show_preview(self, preview: str) -> None:
        img = wx.Bitmap(preview, wx.BITMAP_TYPE_ANY)
        self.reshape_img(img)
        self.preview.SetBitmap(img)

        self.preview_box.Show()
        self.preview_error.Hide()

        self.print.Enable()
        self.Layout()

    def reshape_img(self, img: wx.Bitmap) -> None:
        w, h = img.GetSize()
        if w > h:
            self.image_size = (self.image_size[0], int(h * self.image_size[0] / w))
        else:  # h > w
            self.image_size = (int(w * self.image_size[1] / h), self.image_size[1])

        wx.Bitmap.Rescale(img, self.image_size)

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
