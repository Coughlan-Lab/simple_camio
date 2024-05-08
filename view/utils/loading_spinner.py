from typing import Optional
from res import Colors, ImgsManager
import wx
from wx import adv


class LoadingSpinner(wx.Panel):
    def __init__(self, parent: wx.Panel) -> None:
        wx.Panel.__init__(
            self, parent, wx.ID_ANY, name="Loading in progress", size=parent.GetSize()
        )

        self.SetBackgroundColour(Colors.background)

        animation = adv.Animation(ImgsManager.loading_spinner)
        self.spinner = adv.AnimationCtrl(
            self, -1, animation, name="Loading in progress"
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.spinner)
        self.SetSizerAndFit(sizer)

        self.bitmap: Optional[wx.Bitmap] = None

    def Show(self, show=True) -> bool:
        if show:
            self.spinner.Play()
            return super().Show()
        else:
            return self.Hide()

    def Hide(self) -> bool:
        self.spinner.Stop()
        return super().Hide()
