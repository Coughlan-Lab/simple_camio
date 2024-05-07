from typing import Optional
import wx


class AccessibleDescription(wx.Accessible):
    def __init__(
        self, name: Optional[str] = None, description: Optional[str] = None
    ) -> None:
        wx.Accessible.__init__(self)

        self.name = name
        self.description = description

    def GetDescription(self, childId: int) -> tuple:
        if self.description is not None:
            return wx.ACC_OK, self.description
        return super().GetDescription(childId)

    def GetName(self, childId: int) -> tuple:
        if self.name is not None:
            return wx.ACC_OK, self.name
        return super().GetName(childId)

    def GetHelpText(self, childId: int) -> tuple:
        return wx.ACC_OK, "romeo"

    def GetClassInfo(self) -> wx.ClassInfo:
        return super().GetClassInfo()

    def DoDefaultAction(self, childId: int) -> int:
        print("QUI")
        return super().DoDefaultAction(childId)
