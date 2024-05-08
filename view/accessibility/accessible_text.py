import wx


class AccessibleText(wx.StaticText):
    def __init__(self, *arg, **kwargs):
        wx.StaticText.__init__(self, *arg, **kwargs)
        self.SetCanFocus(not self.isEmpty())
        self.EnableVisibleFocus(not self.isEmpty())

    def isEmpty(self) -> bool:
        return self.GetLabel() == ""

    def AcceptsFocus(self) -> bool:
        return not self.isEmpty()

    def AcceptsFocusFromKeyboard(self) -> bool:
        return not self.isEmpty()

    def AcceptsFocusRecursively(self) -> bool:
        return not self.isEmpty()

    def SetLabel(self, label: str) -> None:
        super().SetLabel(label)

        self.SetCanFocus(not self.isEmpty())
        self.EnableVisibleFocus(not self.isEmpty())
