import os
import wx
from enum import Enum

from view.controllers import *
from model import State
from typing import List, Dict, Optional
from res import Colors


class ScreenName(Enum):
    HomePage = HomePage
    NoContent = NoContent
    ContentSelector = ContentSelector
    ContentDescription = ContentDescription
    PointerSelector = PointerSelector
    NoCamera = NoCamera
    CameraSelector = CameraSelector
    CalibrationFound = CalibrationFound
    Calibration = Calibration
    ContentUsage = ContentUsage
    # ContentVideoTutorial = ContentVideoTutorial
    # CalibrationVideoTutorial = CalibrationVideoTutorial


class MainFrame(wx.Frame):
    DEFAULT_SIZE = wx.Size(880, 660)

    def __init__(self) -> None:
        wx.Frame.__init__(
            self,
            None,
            id=wx.ID_ANY,
            title="CamIO",
            pos=wx.DefaultPosition,
            size=MainFrame.DEFAULT_SIZE,
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL,
        )

        self.SetSizeHints(wx.DefaultSize, wx.DefaultSize)
        self.Centre(wx.BOTH)
        self.SetBackgroundColour(Colors.background)

        self.__state = State(os.path.expanduser("~/Documents/CamIO Config"))

        self.stack: List[str] = []
        self.frames: Dict[str, Screen] = dict()

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.sizer)

        for page in ScreenName:
            frame = page.value(self, self)
            self.frames[page.name] = frame
            frame.Hide()

        self.current_frame: Optional[Screen] = None
        self.show_screen(ScreenName.HomePage)

        self.Bind(wx.EVT_SIZE, self.on_resize)

    def on_resize(self, event: wx.SizeEvent) -> None:
        w, h = event.GetSize()

        if w < MainFrame.DEFAULT_SIZE[0] and h < MainFrame.DEFAULT_SIZE[1]:
            self.SetSize(MainFrame.DEFAULT_SIZE)
        elif self.Size[0] < MainFrame.DEFAULT_SIZE[0]:
            self.SetSize(wx.Size(MainFrame.DEFAULT_SIZE[0], h))
        elif self.Size[1] < MainFrame.DEFAULT_SIZE[1]:
            self.SetSize(wx.Size(w, MainFrame.DEFAULT_SIZE[1]))

        if self.current_frame is not None:
            self.current_frame.SetSize(self.GetSize())

        self.Layout()
        event.Skip()

    @property
    def current_state(self) -> State:
        return self.__state

    @property
    def last_screen(self) -> ScreenName:
        if len(self.stack) == 0:
            return ScreenName.HomePage
        return ScreenName[self.stack[-1]]

    def show_screen(self, screen: ScreenName, stack: bool = True) -> None:
        if screen.name not in self.frames:
            raise Exception(f"Unknown screen {screen}")

        new_frame = self.frames[screen.name]

        if self.current_frame is not None:
            self.current_frame.SetFocus(False)
            if stack:
                self.stack.append(self.current_frame.name)
            self.sizer.Replace(self.current_frame, new_frame)
        else:
            self.sizer.Add(new_frame, 1, wx.EXPAND)

        self.current_frame = new_frame
        self.current_frame.SetFocus(True)

        self.Layout()

    def Destroy(self) -> bool:
        if self.current_frame is not None:
            self.current_frame.on_unfocus()

        for frame in self.frames.values():
            frame.Destroy()

        return super().Destroy()

    def back(self, to: Optional[ScreenName] = None) -> None:
        if len(self.stack) == 0:
            return

        if to is not None and to.name in self.stack:
            i = self.stack.index(to.name)
            self.stack = self.stack[:i]
        else:
            to = ScreenName[self.stack.pop()]

        self.show_screen(to, stack=False)


class GUI(wx.App):
    def __init__(self) -> None:
        wx.App.__init__(self)

        self.frame = MainFrame()
        self.frame.Show()

    def start(self, screen: Optional[ScreenName]) -> None:
        if screen is not None:
            self.frame.show_screen(screen)
        self.MainLoop()

    def Destroy(self) -> None:
        self.frame.Destroy()


gui: Optional[GUI] = None


def create_gui() -> GUI:
    global gui
    if gui is not None:
        raise Exception("Gui already started")
    gui = GUI()
    return gui


def get_gui() -> GUI:
    if gui is None:
        return create_gui()
    return gui
