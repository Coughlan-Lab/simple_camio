import os

from matplotlib import style
from res import Colors
from controllers.screen import Screen
import gui
from res import Fonts
from model import ContentManager
from typing import Any, Callable, Union, List
import wx


class ContentSelector(Screen):

    def __init__(self, gui: "gui.MainFrame", parent: wx.Frame):
        Screen.__init__(self, gui, parent, show_back=True)

        self.content: List[str] = list()

        title = wx.StaticText(self, wx.ID_ANY, label="Select a content:")
        title.SetForegroundColour(Colors.text)
        title.SetFont(Fonts.title)

        header_style = wx.ItemAttr()
        header_style.SetFont(Fonts.row_item)

        self.container = wx.ListCtrl(
            self,
            style=wx.LC_REPORT
            | wx.LC_SINGLE_SEL
            | wx.LC_HRULES
            | wx.LC_VRULES
            | wx.LC_SORT_ASCENDING,
            size=(600, 200),
        )
        self.container.AppendColumn("Content", format=wx.LIST_FORMAT_CENTRE, width=200)
        self.container.AppendColumn(
            "Description", format=wx.LIST_FORMAT_CENTRE, width=400
        )
        self.container.SetHeaderAttr(header_style)
        self.container.SortItems(self.sortContent)
        self.container.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_content_selected)

        self.error_msg = wx.StaticBox(self, wx.ID_ANY, size=(600, 200))
        error = wx.StaticText(
            self.error_msg,
            wx.ID_ANY,
            label="No content found in the content directory",
            style=wx.ALIGN_CENTER,
            size=(self.error_msg.GetSize()[0] - 2, wx.DefaultSize[1]),
        )
        error.CenterOnParent()
        error.SetForegroundColour(Colors.text)
        error.SetFont(Fonts.subtitle)
        self.error_msg.Hide()

        change_content_dir = wx.Button(
            self,
            wx.ID_ANY,
            label="Change directory",
            size=(200, 50),
        )
        change_content_dir.SetFont(Fonts.button)
        change_content_dir.SetBackgroundColour(Colors.button)
        change_content_dir.SetForegroundColour(Colors.button_text)
        change_content_dir.Bind(wx.EVT_BUTTON, self.change_content_dir)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 50)
        sizer.AddStretchSpacer(2)
        sizer.Add(self.container, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.Add(self.error_msg, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL)
        sizer.AddStretchSpacer(1)
        sizer.Add(change_content_dir, 0, wx.ALL | wx.ALIGN_RIGHT, 50)

        self.SetSizerAndFit(sizer)

    def on_focus(self) -> None:
        self.gui.current_state.clear()
        ContentManager.load_content()
        self.init_content()

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
        self.error_msg.Hide()
        self.Layout()

    def show_no_content(self) -> None:
        self.container.Hide()
        self.error_msg.Show()
        self.Layout()

    def sortContent(self, first, second):
        if first == second:
            return 0
        elif first < second:
            return -1
        return 1

    def on_content_selected(self, event):
        content = self.content[event.GetIndex()]
        self.gui.current_state.content = ContentManager.get_content_data(content)
        # self.gui.show_screen(gui.ScreenName.ContentDescription)

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
