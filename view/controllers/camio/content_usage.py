from ..screen import Screen
import gui
from view.utils import Camera, FrameViewer
from typing import Optional
from res import Fonts, Colors
from model import utils, State, get_frame_processor, FrameProcessor
import cv2
import numpy as np
import threading
import wx
from view.accessibility import AccessibleText


class ContentUsage(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.ContentSelector

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(self, gui, parent, show_back=True, name="Content usage screen")

        self.title = AccessibleText(self, wx.ID_ANY, style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.title.SetForegroundColour(Colors.text)
        self.title.SetFont(Fonts.title)

        """
        icon = tk.CTkImage(
            light_image=Image.open(ImgsManager.question_mark), size=(25, 25)
        )
        self.tutorial = tk.CTkButton(
            self, text="", image=icon, anchor=CENTER, width=10, height=30
        )
        self.tutorial.pack(side=RIGHT, padx=(0, 40), pady=(30, 0), anchor=N)
        self.tutorial.configure(command=self.show_tutorial)
        """

        self.preview = FrameViewer(self, (600, 350))

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(50)
        sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(self.preview, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddStretchSpacer(1)
        sizer.AddSpacer(50)

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
