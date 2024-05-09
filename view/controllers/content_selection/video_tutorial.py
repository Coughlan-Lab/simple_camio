from ..screen import Screen
import gui
from res import *
import wx
from view.accessibility import AccessibleText
from wx import media


class ContentVideoTutorial(Screen):
    VIDEO_RES = (640, 360)

    @property
    def back_screen(self) -> "gui.ScreenName":
        return self.gui.last_screen

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(
            self, gui, parent, show_back=True, name="Calibration tutorial screen"
        )

        self.title = AccessibleText(
            self,
            wx.ID_ANY,
            label="Watch the tutorial before proceeding",
            style=wx.ALIGN_CENTRE_HORIZONTAL,
        )
        self.title.SetForegroundColour(
            Colors.text,
        )
        self.title.SetFont(Fonts.title)

        self.video = media.MediaCtrl(
            self,
            wx.ID_ANY,
            size=ContentVideoTutorial.VIDEO_RES,
            name="Content usage video tutorial. Press space to start or pause",
        )

        proceed = wx.Button(self, wx.ID_ANY, "Proceed")
        proceed.SetForegroundColour(Colors.button_text)
        proceed.SetFont(Fonts.button)
        proceed.Bind(wx.EVT_BUTTON, self.show_next_screen)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddSpacer(50)
        sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.video, 1, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL | wx.SHAPED, 10)
        sizer.Add(proceed, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddSpacer(50)

        self.SetSizerAndFit(sizer)

        self.video.Bind(media.EVT_MEDIA_FINISHED, self.on_video_ended)
        self.video.Bind(media.EVT_MEDIA_LOADED, self.on_video_loaded)
        self.video.Bind(wx.EVT_KEY_DOWN, self.on_interaction)

    def on_focus(self) -> None:
        self.video.Load(VideosManager.content_tutorial)
        self.video.ShowPlayerControls()

        self.title.SetFocus()

    def on_unfocus(self) -> None:
        self.video.Stop()

    def on_video_loaded(self, event) -> None:
        print("video loaded")
        self.video.Seek(0)
        self.video.SetVolume(1)
        self.video.Play()

    def on_interaction(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() != wx.WXK_SPACE:
            return

        if self.video.GetState() == media.MEDIASTATE_PLAYING:
            self.video.Pause()
        else:
            self.video.Play()

    def on_video_ended(self, event) -> None:
        self.gui.current_state.set_content_tutorial_watched()

    def show_next_screen(self, event) -> None:
        state = self.gui.current_state
        if state.pointer is None:
            self.gui.show_screen(gui.ScreenName.PointerSelector)
        elif state.camera is None:
            self.gui.show_screen(gui.ScreenName.Calibration)
        else:
            self.gui.show_screen(gui.ScreenName.ContentUsage)
