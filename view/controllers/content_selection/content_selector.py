import os
from res import Colors
from ..screen import Screen
import gui
from res import Fonts
from model import ContentManager
from typing import List
import wx
from view.accessibility import AccessibleText, AccessibleDescription
from model import utils


class ContentSelector(Screen):
    @property
    def back_screen(self) -> "gui.ScreenName":
        return gui.ScreenName.HomePage

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(self, gui, parent, show_back=True, name="Content list screen")

        self.content: List[str] = list()

        self.title = AccessibleText(self, wx.ID_ANY, label="Select a content:")
        self.title.SetForegroundColour(Colors.text)
        self.title.SetFont(Fonts.title)

        header_style = wx.ItemAttr()
        header_style.SetFont(Fonts.row_item)

        self.container = wx.ListCtrl(
            self,
            style=wx.LC_REPORT
            | wx.LC_SINGLE_SEL
            | wx.LC_HRULES
            | wx.LC_VRULES
            | wx.LC_SORT_ASCENDING
            | wx.SIMPLE_BORDER,
            size=(602, 200),
        )
        self.container.SetBackgroundColour(Colors.background)
        self.container.SetTextColour(Colors.text)

        if utils.SYSTEM == utils.OS.WINDOWS:
            self.container.SetAccessible(
                AccessibleDescription(description="Content list")
            )
        self.container.AppendColumn("Content", format=wx.LIST_FORMAT_CENTRE, width=200)
        self.container.AppendColumn(
            "Description", format=wx.LIST_FORMAT_CENTRE, width=400
        )
        self.container.SetHeaderAttr(header_style)
        self.container.SortItems(self.sort_contents)
        self.container.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_content_selected)

        self.no_content = wx.StaticBox(self, wx.ID_ANY, size=(600, 200))
        no_content_text = AccessibleText(
            self.no_content,
            wx.ID_ANY,
            label="No content found in the content directory",
            style=wx.ALIGN_CENTER,
            size=(self.no_content.GetSize()[0] - 2, wx.DefaultSize[1]),
        )
        no_content_text.CenterOnParent()
        no_content_text.SetForegroundColour(Colors.text)
        no_content_text.SetFont(Fonts.subtitle)
        self.no_content.Hide()

        change_content_dir = wx.Button(self, wx.ID_ANY, label="Change directory")
        change_content_dir.SetForegroundColour(Colors.button_text)
        change_content_dir.SetFont(Fonts.button)
        change_content_dir.Bind(wx.EVT_BUTTON, self.change_content_dir)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.AddSpacer(50)
        sizer.Add(self.title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddStretchSpacer(2)
        sizer.Add(self.container, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.no_content, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(change_content_dir, 0, wx.ALL | wx.ALIGN_RIGHT, 50)

        self.SetSizerAndFit(sizer)

    def on_focus(self) -> None:
        self.gui.current_state.clear()
        ContentManager.load_content()
        self.init_content()
        self.title.SetFocus()

    def init_content(self) -> None:
        self.container.DeleteAllItems()
        self.content.clear()

        for i, content in enumerate(ContentManager.content):
            data = ContentManager.get_content_data(content)

            item = wx.ListItem()
            item.SetId(i)
            item.SetText(content)
            item.SetFont(Fonts.row_item)
            item.SetMask(wx.LIST_MASK_TEXT)

            self.container.InsertItem(item)
            self.container.SetItem(i, 1, f"{data.description}")

            self.content.append(content)

        if len(self.content) == 0:
            self.show_no_content()
        else:
            self.show_content()

    def show_content(self) -> None:
        self.container.Show()
        self.no_content.Hide()
        self.Layout()

    def show_no_content(self) -> None:
        self.container.Hide()
        self.no_content.Show()
        self.Layout()

    def sort_contents(self, first, second):
        if first == second:
            return 0
        elif first < second:
            return -1
        return 1

    def on_content_selected(self, event):
        content = self.content[event.GetIndex()]
        self.gui.current_state.content = ContentManager.get_content_data(content)
        self.gui.show_screen(gui.ScreenName.ContentDescription)

    def change_content_dir(self, event) -> None:
        with wx.DirDialog(
            self,
            "Select content directory",
            defaultPath=os.path.expanduser("~"),
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return

            content_dir = dialog.GetPath()

        if content_dir is None or content_dir == "":
            return

        self.gui.current_state.set_content_dir(content_dir)
        self.on_focus()
