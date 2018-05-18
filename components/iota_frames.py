from __future__ import division

"""
Author      : Lyubimov, A.Y.
Created     : 01/17/2017
Last Changed: 05/11/2018
Description : IOTA GUI Windows / frames
"""

import os
import wx
from wxtbx import bitmaps
import wx.lib.buttons as btn
from wx import richtext as rt
from wx.lib.scrolledpanel import ScrolledPanel

import numpy as np
import time
import warnings
import multiprocessing

import matplotlib.gridspec as gridspec
from matplotlib import pyplot as plt
from matplotlib import colorbar, colors
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as mpatches
import matplotlib.path as path
from mpl_toolkits.mplot3d import Axes3D

assert Axes3D

from libtbx import easy_run
from libtbx import easy_pickle as ep
from libtbx.utils import to_unicode
from cctbx import miller, crystal
from cctbx.array_family import flex

from iota.components.iota_utils import InputFinder
from iota.components.iota_analysis import Analyzer, Plotter
from iota.components.iota_misc import WxFlags, noneset
import iota.components.iota_controls as ct
import iota.components.iota_threads as thr
import iota.components.iota_dialogs as dlg

f = WxFlags()
ginp = InputFinder()

# Platform-specific stuff
# TODO: Will need to test this on Windows at some point
if wx.Platform == "__WXGTK__":
    plot_font_size = 10
    norm_font_size = 10
    button_font_size = 12
    LABEL_SIZE = 14
    CAPTION_SIZE = 12
    python = "python"
elif wx.Platform == "__WXMAC__":
    plot_font_size = 9
    norm_font_size = 12
    button_font_size = 14
    LABEL_SIZE = 14
    CAPTION_SIZE = 12
    python = "Python"
elif wx.Platform == "__WXMSW__":
    plot_font_size = 9
    norm_font_size = 9
    button_font_size = 11
    LABEL_SIZE = 11
    CAPTION_SIZE = 9
    python = "Python"  # TODO: make sure it's right!

# ------------------------------ Input Window -------------------------------- #


class BasePanel(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent=parent, id=wx.ID_ANY, size=(800, 500))

        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.main_sizer)


class InputWindow(BasePanel):
    """ Input window - data input, description of project """

    def __init__(self, parent, phil):
        BasePanel.__init__(self, parent=parent)

        # Generate default parameters
        self.input_phil = phil
        self.target_phil = None
        self.gparams = self.input_phil.extract()
        self.imageset = None

        if str(self.gparams.advanced.integrate_with).lower() == "cctbx":
            target = self.gparams.cctbx.target
        elif str(self.gparams.advanced.integrate_with).lower() == "dials":
            target = self.gparams.dials.target

        if str(target).lower != "none":
            try:
                with open(target, "r") as pf:
                    self.target_phil = pf.read()
            except Exception:
                self.target_phil = None

        self.int_box = ct.ChoiceCtrl(
            self,
            label="Integrate with:",
            label_size=(150, -1),
            choices=["cctbx", "DIALS"],
            ctrl_size=(200, -1),
        )
        self.int_box.ctr.SetSelection(0)

        self.project_folder = ct.InputCtrl(
            self,
            label="Project Folder: ",
            label_size=(150, -1),
            label_style="bold",
            value=os.path.abspath(os.curdir),
            buttons=True,
        )

        self.project_title = ct.InputCtrl(
            self, label="Description", label_size=(150, -1), label_style="normal"
        )

        # List control to add / manage input items
        self.input = FileListCtrl(self)

        # Put everything into main sizer
        self.main_sizer.Add(self.int_box, flag=f.expand, border=10)
        self.main_sizer.Add(self.project_title, flag=f.expand, border=10)
        self.main_sizer.Add(self.project_folder, flag=f.expand, border=10)
        self.main_sizer.Add(self.input, 1, flag=wx.EXPAND | wx.ALL, border=10)
        self.main_sizer.Add(wx.StaticLine(self), flag=wx.EXPAND)

        # Options
        opt_box = wx.FlexGridSizer(1, 5, 0, 15)
        total_procs = multiprocessing.cpu_count()
        self.opt_spc_nprocs = ct.SpinCtrl(
            self,
            label="No. Processors: ",
            label_size=(120, -1),
            ctrl_min=1,
            ctrl_value=str(int(total_procs / 2)),
        )
        self.opt_btn_import = wx.Button(self, label="Import options...")
        self.opt_btn_process = wx.Button(self, label="Processing options...")
        self.opt_btn_analysis = wx.Button(self, label="Analysis options...")
        opt_box.AddMany(
            [
                (self.opt_spc_nprocs),
                (0, 0),
                (self.opt_btn_import),
                (self.opt_btn_process),
                (self.opt_btn_analysis),
            ]
        )
        opt_box.AddGrowableCol(1)
        self.main_sizer.Add(opt_box, flag=f.expand, border=10)

        # Button bindings
        self.project_folder.btn_browse.Bind(wx.EVT_BUTTON, self.onOutputBrowse)
        self.project_folder.btn_mag.Bind(wx.EVT_BUTTON, self.onMagButton)
        self.Bind(wx.EVT_BUTTON, self.onImportOptions, self.opt_btn_import)
        self.Bind(wx.EVT_BUTTON, self.onProcessOptions, self.opt_btn_process)
        self.Bind(wx.EVT_BUTTON, self.onAnalysisOptions, self.opt_btn_analysis)

    def onMagButton(self, e):
        dirview = dlg.DirView(self, title="Current Folder")
        if dirview.ShowModal() == wx.ID_OK:
            dirview.Destroy()

    def onImportOptions(self, e):
        e.Skip()

    def onProcessOptions(self, e):
        e.Skip()

    def onAnalysisOptions(self, e):
        e.Skip()

    def onInfo(self, e):
        """ On clicking the info button """
        info_txt = """Input diffraction images here. IOTA accepts either raw images (mccd, cbf, img, etc.) or image pickles. Input can be either a folder with images, or a text file with a list of images."""
        info = wx.MessageDialog(None, info_txt, "Info", wx.OK)
        info.ShowModal()

    def onOutputBrowse(self, e):
        """ On clicking the Browse button: show the DirDialog and populate 'Output'
        box w/ selection """
        dlg = wx.DirDialog(
            self, "Choose the output directory:", style=wx.DD_DEFAULT_STYLE
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.project_folder.ctr.SetValue(dlg.GetPath())
        dlg.Destroy()
        e.Skip()


class FileListCtrl(ct.CustomListCtrl):
    """ File list window for the input tab """

    def __init__(self, parent, size=(-1, 300)):
        ct.CustomListCtrl.__init__(self, parent=parent, size=size)

        self.parent = parent
        self.main_window = parent.GetParent()

        # Initialize dictionaries for imported data types
        self.all_data_images = {}
        self.all_img_objects = {}
        self.all_proc_pickles = {}
        self.image_count = 0

        # Generate columns
        self.ctr.InsertColumn(0, "")
        self.ctr.InsertColumn(1, "Input Path")
        self.ctr.InsertColumn(2, "Input Type")
        self.ctr.InsertColumn(3, "Action")
        self.ctr.setResizeColumn(2)

        # Add file / folder buttons
        # self.button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.button_sizer = wx.FlexGridSizer(1, 3, 0, 10)
        self.btn_add_file = wx.Button(self, label="Add File...")
        self.btn_add_dir = wx.Button(self, label="Add Folder...")
        self.txt_total_images = wx.StaticText(self, label="")
        self.button_sizer.Add(self.btn_add_file)
        self.button_sizer.Add(self.btn_add_dir)
        self.button_sizer.Add(self.txt_total_images)
        self.button_sizer.AddGrowableCol(1)

        self.sizer.Add(
            self.button_sizer, flag=wx.EXPAND | wx.TOP | wx.BOTTOM, border=10
        )

        # Event bindings
        self.Bind(wx.EVT_BUTTON, self.onAddFile, self.btn_add_file)
        self.Bind(wx.EVT_BUTTON, self.onAddFolder, self.btn_add_dir)

    def onAddFile(self, e):
        file_dlg = wx.FileDialog(
            self,
            message="Load File",
            defaultDir=os.curdir,
            defaultFile="*",
            wildcard="*",
            style=wx.OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        )
        if file_dlg.ShowModal() == wx.ID_OK:
            files = file_dlg.GetPaths()
            for item in files:
                self.add_item(item)
        file_dlg.Destroy()
        e.Skip()

    def onAddFolder(self, e):
        dlg = wx.DirDialog(self, "Load Folder:", style=wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            self.add_item(dlg.GetPath())
        dlg.Destroy()
        e.Skip()

    def set_type_choices(self, path):
        # Determine what type of input this is and present user with choices
        # (this so far works for images ONLY)
        type_choices = ["[  SELECT INPUT TYPE  ]"]
        preferred_selection = 0
        inputs, input_type = ginp.get_input(path)

        if os.path.isdir(path):
            type_choices.extend(["raw image folder", "image pickle folder"])
            if input_type in type_choices:
                preferred_selection = type_choices.index(input_type)
        elif os.path.isfile(path):
            if input_type in ("image pickle file", "raw image file"):
                type_choices.extend(["raw image file", "image pickle file"])
                if input_type in type_choices:
                    preferred_selection = type_choices.index(input_type)
            elif input_type in ("raw image list", "image pickle list"):
                type_choices.extend(["raw image list", "image pickle list"])
                if input_type in type_choices:
                    preferred_selection = type_choices.index(input_type)
        return inputs, type_choices, preferred_selection

    def add_item(self, path):
        # Generate item
        inputs, inp_choices, inp_sel = self.set_type_choices(path)
        type_choice = ct.DataTypeChoice(self.ctr, choices=inp_choices)
        item = ct.InputListItem(
            path=path, type=type_choice, buttons=ct.MiniButtonBoxInput(self.ctr)
        )

        self.Bind(wx.EVT_CHOICE, self.onTypeChoice, item.type.type)
        self.Bind(wx.EVT_BUTTON, self.onMagButton, item.buttons.btn_mag)
        self.Bind(wx.EVT_BUTTON, self.onDelButton, item.buttons.btn_delete)
        self.Bind(wx.EVT_BUTTON, self.onInfoButton, item.buttons.btn_info)

        # Insert list item
        idx = self.ctr.InsertStringItem(self.ctr.GetItemCount() + 1, "")
        self.ctr.SetStringItem(idx, 1, item.path)
        self.ctr.SetItemWindow(idx, 2, item.type, expand=True)
        self.ctr.SetItemWindow(idx, 3, item.buttons, expand=True)

        # Set drop-down selection, check it for data and open other tabs
        item.type.type.SetSelection(inp_sel)
        if item.type.type.GetString(inp_sel) in [
            "raw image folder",
            "image pickle folder",
            "image pickle file",
            "raw image file",
            "raw image list",
            "image pickle list",
        ]:
            self.main_window.toolbar.EnableTool(
                self.main_window.tb_btn_run.GetId(), True
            )
            self.all_data_images[item.path] = inputs

            # Calculate # of images and display w/ item
            self.ctr.SetStringItem(idx, 0, str(len(inputs)))

            if "image" in item.type.type.GetString(inp_sel):
                view_bmp = bitmaps.fetch_custom_icon_bitmap("image_viewer16")
                item.buttons.btn_mag.SetBitmapLabel(view_bmp)
        else:
            warn_bmp = bitmaps.fetch_icon_bitmap("actions", "status_unknown", size=16)
            item.buttons.btn_info.SetBitmapLabel(warn_bmp)
            item.warning = True

        # Record index in all relevant places
        item.id = idx
        item.buttons.index = idx
        item.type.index = idx
        item.type_selection = inp_sel

        # Resize columns to fit content
        self.ctr.SetColumnWidth(0, width=-1)
        self.ctr.SetColumnWidth(2, width=-1)
        self.ctr.SetColumnWidth(3, width=-1)
        self.ctr.SetColumnWidth(1, width=-3)

        # Make sure all the choice lists are the same size
        if item.type.type.GetSize()[0] < self.ctr.GetColumnWidth(2) - 5:
            item.type.type.SetSize((self.ctr.GetColumnWidth(2) - 5, -1))

        # Attach data object to item
        self.ctr.SetItemData(item.id, item)

        if len(inputs) > 0:
            self.image_count += len(inputs)
            if self.image_count > 0:
                self.update_total_image_count()

        self.main_window.Layout()

    def onTypeChoice(self, e):
        type = e.GetEventObject().GetParent()
        item_data = self.ctr.GetItemData(type.index)
        item_data.type.type.SetSelection(type.type.GetSelection())
        item_data.type_selection = type.type.GetSelection()

        # Evaluate whether data folders / files are present
        data_items = 0
        for idx in range(self.ctr.GetItemCount()):
            if self.ctr.GetItemData(idx).type_selection != 0:
                data_items += 1
        if data_items > 0:
            self.main_window.toolbar.EnableTool(
                self.main_window.tb_btn_run.GetId(), True
            )
        else:
            self.main_window.toolbar.EnableTool(
                self.main_window.tb_btn_run.GetId(), False
            )
        e.Skip()

    def onMagButton(self, e):
        idx = e.GetEventObject().GetParent().index
        item_obj = self.ctr.GetItemData(idx)
        path = item_obj.path
        type = item_obj.type.type.GetString(item_obj.type_selection)

        if os.path.isfile(path):
            if type in ("raw image file", "image pickle file"):
                self.view_images([path], img_type=type)
            elif type in ("raw image list", "image pickle list"):
                with open(path, "r") as f:
                    file_list = [i.replace("\n", "") for i in f.readlines()]
                    self.view_images(file_list, img_type=type)
            elif type == "text":
                with open(path, "r") as f:
                    file_list = f.readlines()
                    msg = " ".join(file_list)
                    textview = dlg.TextFileView(self, title=path, contents=msg)
                    textview.ShowModal()
            else:
                wx.MessageBox(
                    "Unknown file format", "Warning", wx.OK | wx.ICON_EXCLAMATION
                )
        elif os.path.isdir(path):
            file_list, _ = ginp.get_input(path, filter=True)
            self.view_images(file_list, img_type=type)

    def view_images(self, img_list, img_type=None):
        """ Launches image viewer (depending on backend) """
        viewer = self.parent.gparams.advanced.image_viewer
        if viewer == "cxi.view" and "pickle" not in img_type:
            wx.MessageBox(
                "cxi.view only accepts image pickles",
                "Warning",
                wx.OK | wx.ICON_EXCLAMATION,
            )
        else:
            if len(img_list) > 10:
                view_warning = dlg.ViewerWarning(self, len(img_list))
                if view_warning.ShowModal() == wx.ID_OK:
                    # parse 'other' entry
                    img_no_string = str(view_warning.no_images).split(",")
                    filenames = []
                    for n in img_no_string:
                        if "-" in n:
                            img_limits = [int(i) for i in n.split("-")]
                            start = min(img_limits)
                            end = max(img_limits)
                            if start <= len(img_list) and end <= len(img_list):
                                filenames.extend(img_list[start:end])
                        else:
                            if int(n) <= len(img_list):
                                filenames.append(img_list[int(n)])
                    file_string = " ".join(filenames)
                else:
                    return
                view_warning.Close()
            elif viewer == "distl.image_viewer" and len(img_list) > 1:
                wx.MessageBox(
                    "distl.image_viewer can show only one image",
                    "Warning",
                    wx.OK | wx.ICON_EXCLAMATION,
                )
                file_string = img_list[0]
            else:
                file_string = " ".join(img_list)

            viewer = thr.ImageViewerThread(
                self, viewer=viewer, file_string=file_string, img_type=img_type
            )
            viewer.start()

    def onDelButton(self, e):
        item = e.GetEventObject().GetParent()
        self.delete_button(item.index)

    def delete_all(self):
        for idx in range(self.ctr.GetItemCount()):
            self.delete_button(index=0)

    def delete_button(self, index):
        self.image_count -= int(self.ctr.GetItemText(index))
        self.all_data_images.pop(self.ctr.GetItemData(index).path, None)
        self.update_total_image_count()
        self.ctr.DeleteItem(index)

        # Refresh widget and list item indices
        for i in range(self.ctr.GetItemCount()):
            item_data = self.ctr.GetItemData(i)
            item_data.id = i
            item_data.buttons.index = i
            item_data.type.index = i
            type_choice = self.ctr.GetItemWindow(i, col=2)
            type_selection = item_data.type.type.GetSelection()
            type_choice.type.SetSelection(type_selection)
            self.ctr.SetItemData(i, item_data)

    def onInfoButton(self, e):
        """ Info / alert / error button (will change depending on circumstance) """
        idx = e.GetEventObject().GetParent().index
        item_obj = self.ctr.GetItemData(idx)
        item_type = item_obj.type.type.GetString(item_obj.type_selection)

        if item_obj.warning:
            wx.MessageBox(
                item_obj.info["WARNING"], "Warning", wx.OK | wx.ICON_EXCLAMATION
            )
        else:
            wx.MessageBox(item_obj.info[item_type], "Info", wx.OK | wx.ICON_INFORMATION)

    def update_total_image_count(self):
        self.txt_total_images.SetLabel("{} total images".format(self.image_count))


# ----------------------------  Processing Window ---------------------------  #


class LogTab(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent=parent, id=wx.ID_ANY)

        self.log_sizer = wx.BoxSizer(wx.VERTICAL)
        # self.log_window = wx.TextCtrl(self,
        #                               style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP)
        self.log_window = rt.RichTextCtrl(
            self, style=rt.RE_MULTILINE | rt.RE_READONLY | wx.TE_DONTWRAP
        )
        self.log_window.SetFont(wx.Font(9, wx.TELETYPE, wx.NORMAL, wx.NORMAL, False))
        self.log_sizer.Add(
            self.log_window, proportion=1, flag=wx.EXPAND | wx.ALL, border=10
        )

        self.find_string = ct.TextCtrlWithButtons(
            self, buttons=[("Forward", -1), ("Reverse", -1)], ctrl_label="Find String:"
        )
        self.log_sizer.Add(self.find_string, flag=wx.EXPAND | wx.ALL, border=10)
        self.SetSizer(self.log_sizer)

        self.Bind(wx.EVT_BUTTON, self.onSearchForward, self.find_string.btn_forward)
        self.Bind(wx.EVT_BUTTON, self.onSearchReverse, self.find_string.btn_reverse)

    def onSearchForward(self, e):
        if self.log_window.GetCaretPosition() == -1:
            self.log_window.SetCaretPosition(0)
        pos = self.log_window.GetCaretPosition()
        search_string = self.find_string.txt_ctrl.GetValue().lower()
        log_string = self.log_window.GetValue()[pos:-1].lower()
        if search_string.replace(" ", "") not in ("", None):
            found_pos = log_string.find(search_string)
            if found_pos == -1:
                if pos > 0:
                    msg_text = "String Not Found! Search From the Top?"
                    msg = wx.MessageDialog(
                        None, msg_text, "Not Found!", wx.YES_NO | wx.ICON_QUESTION
                    )
                    if msg.ShowModal() == wx.ID_YES:
                        log_string = self.log_window.GetValue()[0:pos].lower()
                        found_pos = log_string.find(search_string)
                        if found_pos == -1:
                            wx.MessageBox(
                                "String Not Found!",
                                "Not Found!",
                                wx.OK | wx.ICON_EXCLAMATION,
                            )
                            return
                    else:
                        return
                else:
                    wx.MessageBox(
                        "String Not Found!", "Not Found!", wx.OK | wx.ICON_EXCLAMATION
                    )
                    return
            else:
                found_pos += pos
            sel_range = (found_pos, found_pos + len(search_string))
            self.log_window.SetSelectionRange(sel_range)
        else:
            found_pos = 0
        self.log_window.SetCaretPosition(found_pos + len(search_string))
        if not self.log_window.IsPositionVisible(found_pos):
            self.log_window.ShowPosition(found_pos)

    def onSearchReverse(self, e):
        if self.log_window.GetCaretPosition() == -1:
            self.log_window.SetCaretPosition(0)
        pos = self.log_window.GetCaretPosition()
        search_string = self.find_string.txt_ctrl.GetValue().lower()
        full_log = self.log_window.GetValue()
        log_string = full_log[0:pos].lower()
        log_end = len(full_log)
        if search_string.replace(" ", "") not in ("", None):
            found_pos = log_string.rfind(search_string)
            if found_pos == -1:
                if pos < log_end:
                    msg_text = "String Not Found! Search From the Bottom?"
                    msg = wx.MessageDialog(
                        None, msg_text, "Not Found!", wx.YES_NO | wx.ICON_QUESTION
                    )
                    if msg.ShowModal() == wx.ID_YES:
                        log_string = full_log[pos:-1].lower()
                        found_pos = log_string.rfind(search_string)
                        if found_pos == -1:
                            wx.MessageBox(
                                "String Not Found!",
                                "Not Found!",
                                wx.OK | wx.ICON_EXCLAMATION,
                            )
                            return
                        else:
                            found_pos += pos
                    else:
                        return
                else:
                    wx.MessageBox(
                        "String Not Found!", "Not Found!", wx.OK | wx.ICON_EXCLAMATION
                    )
                    return
            sel_range = (found_pos, found_pos + len(search_string))
            self.log_window.SetSelectionRange(sel_range)
        else:
            found_pos = 0
        self.log_window.SetCaretPosition(found_pos - len(search_string))
        if not self.log_window.IsPositionVisible(found_pos):
            self.log_window.ShowPosition(found_pos)


class ProcessingTab(ScrolledPanel):
    def __init__(self, parent):
        self.gparams = None
        self.init = None
        self.parent = parent

        self.finished_objects = []
        self.img_list = []
        self.nref_list = []
        self.res_list = []
        self.indices = []
        self.spacegroup = None
        self.idx_array = None

        self.hkl_view_axis = "l"
        self.pick = {"image": None, "index": 0, "axis": None, "picked": False}
        self.proc_fnames = None

        ScrolledPanel.__init__(self, parent)
        self.main_fig_sizer = wx.GridBagSizer(0, 0)

        # Set regular font
        plt.rc("font", family="sans-serif", size=plot_font_size)
        plt.rc("mathtext", default="regular")

        # Integration figure (resolution & reflections / frame)
        self.int_panel = wx.Panel(self)
        int_sizer = wx.BoxSizer(wx.VERTICAL)
        self.int_panel.SetSizer(int_sizer)
        self.int_figure = Figure(figsize=(1, 2.5))
        self.int_figure.patch.set_visible(False)  # create transparent background

        # Image info sizer
        self.info_sizer = wx.GridBagSizer(0, 5)
        self.info_txt = wx.TextCtrl(self.int_panel, style=wx.TE_READONLY)
        view_bmp = bitmaps.fetch_custom_icon_bitmap("image_viewer16")
        r_bmp = bitmaps.fetch_icon_bitmap("actions", "1rightarrow", size=16)
        l_bmp = bitmaps.fetch_icon_bitmap("actions", "1leftarrow", size=16)
        self.btn_right = btn.GenBitmapButton(self, bitmap=r_bmp)
        self.btn_left = btn.GenBitmapButton(self, bitmap=l_bmp)
        self.btn_viewer = btn.GenBitmapButton(self, bitmap=view_bmp)
        self.info_sizer.Add(self.info_txt, pos=(0, 1), flag=wx.EXPAND)
        self.info_sizer.Add(self.btn_left, pos=(0, 2))
        self.info_sizer.Add(self.btn_right, pos=(0, 3))
        self.info_sizer.Add(self.btn_viewer, pos=(0, 4))
        self.info_sizer.AddGrowableCol(1)
        int_sizer.Add(self.info_sizer, flag=wx.EXPAND)
        self.info_txt.Hide()
        self.btn_right.Hide()
        self.btn_left.Hide()
        self.btn_viewer.Hide()

        self.btn_right.Disable()
        self.btn_left.Disable()
        self.btn_viewer.Disable()

        self.Bind(wx.EVT_BUTTON, self.onImageView, self.btn_viewer)
        self.Bind(wx.EVT_BUTTON, self.onArrow, self.btn_right)
        self.Bind(wx.EVT_BUTTON, self.onArrow, self.btn_left)

        # Charts
        int_gsp = gridspec.GridSpec(2, 1, wspace=0, hspace=0)

        # Resolution / No. strong reflections chart
        self.res_axes = self.int_figure.add_subplot(int_gsp[0])
        self.res_axes.set_ylabel("Resolution")
        self.res_axes.yaxis.get_major_ticks()[0].label1.set_visible(False)
        self.res_axes.yaxis.get_major_ticks()[-1].label1.set_visible(False)
        plt.setp(self.res_axes.get_xticklabels(), visible=False)
        self.nsref_axes = self.int_figure.add_subplot(int_gsp[1])
        self.nsref_axes.set_xlabel("Frame")
        self.nsref_axes.set_ylabel("Strong Spots")
        self.nsref_axes.yaxis.get_major_ticks()[0].label1.set_visible(False)
        self.nsref_axes.yaxis.get_major_ticks()[-1].label1.set_visible(False)

        self.info_txt.Show()
        self.btn_right.Show()
        self.btn_left.Show()
        self.btn_viewer.Show()

        self.int_figure.set_tight_layout(True)
        self.int_canvas = FigureCanvas(self.int_panel, -1, self.int_figure)
        int_sizer.Add(self.int_canvas, 1, flag=wx.EXPAND)

        # UC Histogram / cluster figure
        self.uc_panel = wx.Panel(self)
        uc_sizer = wx.BoxSizer(wx.VERTICAL)
        self.uc_panel.SetSizer(uc_sizer)
        self.uc_figure = Figure(figsize=(1, 2.5))
        self.uc_figure.patch.set_visible(False)  # create transparent background

        uc_gsub = gridspec.GridSpec(2, 3, wspace=0, hspace=0)
        self.a_axes = self.uc_figure.add_subplot(uc_gsub[0])
        self.a_axes.xaxis.get_major_ticks()[0].label1.set_visible(False)
        self.a_axes.xaxis.get_major_ticks()[-1].label1.set_visible(False)
        self.b_axes = self.uc_figure.add_subplot(uc_gsub[1], sharey=self.a_axes)
        self.b_axes.xaxis.get_major_ticks()[0].label1.set_visible(False)
        self.b_axes.xaxis.get_major_ticks()[-1].label1.set_visible(False)
        plt.setp(self.b_axes.get_yticklabels(), visible=False)
        self.c_axes = self.uc_figure.add_subplot(uc_gsub[2], sharey=self.a_axes)
        self.c_axes.xaxis.get_major_ticks()[0].label1.set_visible(False)
        self.c_axes.xaxis.get_major_ticks()[-1].label1.set_visible(False)
        plt.setp(self.c_axes.get_yticklabels(), visible=False)
        self.alpha_axes = self.uc_figure.add_subplot(uc_gsub[3])
        self.alpha_axes.xaxis.get_major_ticks()[0].label1.set_visible(False)
        self.alpha_axes.xaxis.get_major_ticks()[-1].label1.set_visible(False)
        self.beta_axes = self.uc_figure.add_subplot(uc_gsub[4], sharey=self.alpha_axes)
        self.beta_axes.xaxis.get_major_ticks()[0].label1.set_visible(False)
        self.beta_axes.xaxis.get_major_ticks()[-1].label1.set_visible(False)
        plt.setp(self.beta_axes.get_yticklabels(), visible=False)
        self.gamma_axes = self.uc_figure.add_subplot(uc_gsub[5], sharey=self.alpha_axes)
        self.gamma_axes.xaxis.get_major_ticks()[0].label1.set_visible(False)
        self.gamma_axes.xaxis.get_major_ticks()[-1].label1.set_visible(False)
        plt.setp(self.gamma_axes.get_yticklabels(), visible=False)

        self.uc_figure.set_tight_layout(True)
        self.uc_canvas = FigureCanvas(self.uc_panel, -1, self.uc_figure)
        uc_sizer.Add(self.uc_canvas, 1, flag=wx.EXPAND)

        # HKL (or slice) plot
        self.hkl_panel = wx.Panel(self)
        hkl_sizer = wx.BoxSizer(wx.VERTICAL)
        self.hkl_panel.SetSizer(hkl_sizer)
        self.hkl_figure = Figure(figsize=(0.25, 0.25))
        self.hkl_figure.patch.set_visible(False)  # create transparent background

        self.hkl_axes = self.hkl_figure.add_subplot(111, frameon=False)
        # self.hkl_axes.set_aspect('equal')
        self.hkl_axes.set_xticks([])
        self.hkl_axes.set_yticks([])

        self.hkl_figure.set_tight_layout(True)
        self.hkl_canvas = FigureCanvas(self.hkl_panel, -1, self.hkl_figure)
        hkl_sizer.Add(self.hkl_canvas, 1, flag=wx.EXPAND)

        self.hkl_sg = ct.OptionCtrl(
            self.hkl_panel,
            items=[("sg", "P1")],
            checkbox=True,
            checkbox_state=False,
            checkbox_label="Space Group: ",
            label_size=wx.DefaultSize,
            ctrl_size=wx.DefaultSize,
        )
        hkl_sizer.Add(self.hkl_sg, flag=wx.ALL | wx.ALIGN_CENTER, border=5)
        self.Bind(wx.EVT_TEXT_ENTER, self.onSGTextEnter, self.hkl_sg.sg)
        self.Bind(wx.EVT_CHECKBOX, self.onSGCheckbox, self.hkl_sg.toggle)

        # Processing summary figure
        self.proc_panel = wx.Panel(self, size=(-1, 120))
        proc_sizer = wx.BoxSizer(wx.VERTICAL)
        self.proc_panel.SetSizer(proc_sizer)

        self.proc_figure = Figure(figsize=(0.5, 2.5))
        self.proc_figure.patch.set_visible(False)
        self.sum_axes = self.proc_figure.add_subplot(111)
        self.sum_axes.axis("off")
        self.proc_figure.set_tight_layout(True)
        self.proc_canvas = FigureCanvas(self.proc_panel, -1, self.proc_figure)
        proc_sizer.Add(self.proc_canvas, flag=wx.EXPAND | wx.BOTTOM, border=10)

        self.main_fig_sizer.Add(self.int_panel, pos=(0, 0), span=(2, 6), flag=wx.EXPAND)
        self.main_fig_sizer.Add(self.uc_panel, pos=(2, 0), span=(2, 4), flag=wx.EXPAND)
        self.main_fig_sizer.Add(self.hkl_panel, pos=(2, 4), span=(2, 2), flag=wx.EXPAND)
        self.main_fig_sizer.Add(
            self.proc_panel, pos=(4, 0), span=(1, 6), flag=wx.EXPAND
        )

        self.main_fig_sizer.AddGrowableCol(0)
        self.main_fig_sizer.AddGrowableCol(1)
        self.main_fig_sizer.AddGrowableCol(2)
        self.main_fig_sizer.AddGrowableCol(3)
        self.main_fig_sizer.AddGrowableCol(4)
        self.main_fig_sizer.AddGrowableCol(5)
        self.main_fig_sizer.AddGrowableRow(1)
        self.main_fig_sizer.AddGrowableRow(3)

        cid = self.int_canvas.mpl_connect("pick_event", self.on_pick)
        sid = self.proc_canvas.mpl_connect("pick_event", self.on_bar_pick)
        xid = self.int_canvas.mpl_connect("button_press_event", self.on_button_press)
        xid = self.hkl_canvas.mpl_connect("button_press_event", self.on_hkl_press)
        xid = self.proc_canvas.mpl_connect("button_press_event", self.on_button_press)
        xid = self.proc_canvas.mpl_connect(
            "button_release_event", self.on_button_release
        )

        self.SetSizer(self.main_fig_sizer)

    def onSGTextEnter(self, e):
        self.spacegroup = str(self.hkl_sg.sg.GetValue())
        self.draw_plots()

    def onSGCheckbox(self, e):
        if self.hkl_sg.toggle.GetValue():
            if self.spacegroup is not None:
                self.hkl_sg.sg.SetValue(str(self.spacegroup))
            else:
                self.spacegroup = "P1"
                self.hkl_sg.sg.SetValue("P1")
        else:
            self.hkl_sg.sg.SetValue("")
        self.draw_plots()

    def draw_summary(self):
        try:
            # Summary horizontal stack bar graph
            categories = [
                [
                    "failed triage",
                    "#d73027",
                    len(
                        [i for i in self.finished_objects if i.fail == "failed triage"]
                    ),
                ],
                [
                    "failed indexing / integration",
                    "#f46d43",
                    len(
                        [
                            i
                            for i in self.finished_objects
                            if i.fail == "failed grid search"
                        ]
                    ),
                ],
                [
                    "failed filter",
                    "#ffffbf",
                    len(
                        [
                            i
                            for i in self.finished_objects
                            if i.fail == "failed prefilter" or i.fail == "failed filter"
                        ]
                    ),
                ],
                [
                    "failed spotfinding",
                    "#f46d43",
                    len(
                        [
                            i
                            for i in self.finished_objects
                            if i.fail == "failed spotfinding"
                        ]
                    ),
                ],
                [
                    "failed indexing",
                    "#fdae61",
                    len(
                        [
                            i
                            for i in self.finished_objects
                            if i.fail == "failed indexing"
                        ]
                    ),
                ],
                [
                    "failed integration",
                    "#fee090",
                    len(
                        [
                            i
                            for i in self.finished_objects
                            if i.fail == "failed integration"
                        ]
                    ),
                ],
                [
                    "integrated",
                    "#4575b4",
                    len(
                        [
                            i
                            for i in self.finished_objects
                            if i.fail == None and i.final["final"] != None
                        ]
                    ),
                ],
            ]
            categories.append(
                [
                    "not processed",
                    "#e0f3f8",
                    len(self.img_list) - sum([i[2] for i in categories]),
                ]
            )
            nonzero = [i for i in categories if i[2] > 0]
            names = [i[0] for i in nonzero]
            patches = [None] * len(nonzero)

            self.sum_axes.clear()
            self.sum_axes.axis([0, 1.01 * len(self.img_list), -0.5, 0.75])
            self.sum_axes.axis("off")

            for i in range(len(nonzero)):
                percent = np.round(nonzero[i][2] / len(self.img_list) * 100)

                previous = [j[2] for j in nonzero[:i]]
                lf = np.sum(previous)
                barh = self.sum_axes.barh(
                    0,
                    nonzero[i][2],
                    left=lf,
                    color=nonzero[i][1],
                    align="center",
                    label="{}%".format(percent),
                    picker=True,
                )
                patch = barh[0]
                bl = patch.get_xy()
                patches[i] = (
                    (bl[0], bl[0] + patch.get_width()),
                    (bl[1], bl[1] + patch.get_height()),
                )
                x = 0.5 * patch.get_width() + bl[0]
                y = 0.5 * patch.get_height() + bl[1]
                self.sum_axes.text(
                    x, y, "{}%".format(percent), ha="center", va="center"
                )
            self.sum_axes.legend(
                names,
                ncol=len(nonzero),
                bbox_to_anchor=(0, -1, 1, 1),
                loc="upper center",
                fontsize=9,
                frameon=False,
                handlelength=1,
            )

            self.bracket = mpatches.Rectangle(
                (0, 0),
                len(self.img_list),
                1,
                facecolor="white",
                edgecolor="black",
                zorder=2,
                lw=2,
                visible=False,
            )
            self.sum_axes.add_patch(self.bracket)

            # If bar is clicked, find category and files for display
            if self.pick["picked"] and self.pick["axis"] == "summary":
                idx = self.pick["index"]
                p_idx = [
                    patches.index(i)
                    for i in patches
                    if idx >= i[0][0] and idx <= i[0][1]
                ][0]
                cat = names[p_idx]
                if self.gparams.advanced.integrate_with == "cctbx":
                    if cat == "failed indexing / integration":
                        cat = "failed grid search"
                    elif cat == "failed filter":
                        cat = "failed prefilter"

                if cat not in ("integrated", "not processed"):
                    self.proc_fnames = [
                        i.conv_img for i in self.finished_objects if i.fail == cat
                    ]
                elif cat == "integrated":
                    self.proc_fnames = [
                        i.conv_img
                        for i in self.finished_objects
                        if i.fail == None and i.final["final"] != None
                    ]
                elif cat == "not processed":
                    self.proc_fnames = [
                        i.conv_img
                        for i in self.finished_objects
                        if i.fail == None and i.final["final"] == None
                    ]
                else:
                    self.proc_fnames = ""

                px = patches[p_idx][0][0]
                pw = patches[p_idx][0][1] - patches[p_idx][0][0]
                py = patches[p_idx][1][0]
                ph = patches[p_idx][1][1] - patches[p_idx][1][0]
                self.bracket.set_bounds(px, py, pw, ph)
                self.bracket.set_visible(True)
                self.proc_panel.Refresh()

            self.proc_canvas.draw()

        except ValueError, e:
            print "SUMMARY PLOT ERROR: ", e

    def draw_plots(self):
        if sum(self.nref_list) > 0 and sum(self.res_list) > 0:
            self.draw_integration_plots()
            self.draw_uc_histograms()
            self.draw_measured_indices()
            self.int_canvas.draw()
        self.Layout()
        self.SetupScrolling()

    def draw_integration_plots(self):
        try:
            # Strong reflections per frame
            self.nsref_axes.clear()
            self.nsref_x = np.array([i + 1 for i in range(len(self.img_list))]).astype(
                np.double
            )
            self.nsref_y = np.array(
                [np.nan if i == 0 else i for i in self.nref_list]
            ).astype(np.double)
            nsref_ylabel = "Reflections (I/{0}(I) > {1})" "".format(
                r"$\sigma$", self.gparams.cctbx.selection.min_sigma
            )
            self.nsref = self.nsref_axes.scatter(
                self.nsref_x,
                self.nsref_y,
                s=45,
                marker="o",
                edgecolors="black",
                color="#ca0020",
                picker=True,
            )

            nsref_median = np.median([i for i in self.nref_list if i > 0])
            nsref_med = self.nsref_axes.axhline(nsref_median, c="#ca0020", ls="--")

            self.nsref_axes.set_xlim(0, np.nanmax(self.nsref_x) + 2)
            nsref_ymax = np.nanmax(self.nsref_y) * 1.25 + 10
            if nsref_ymax == 0:
                nsref_ymax = 100
            self.nsref_axes.set_ylim(ymin=0, ymax=nsref_ymax)
            self.nsref_axes.set_ylabel(nsref_ylabel, fontsize=10)
            self.nsref_axes.set_xlabel("Frame")
            self.nsref_axes.yaxis.get_major_ticks()[0].label1.set_visible(False)
            self.nsref_axes.yaxis.get_major_ticks()[-1].label1.set_visible(False)

        except ValueError, e:
            print "NSREF ERROR: ", e

        try:
            # Resolution per frame
            self.res_axes.clear()
            self.res_x = np.array([i + 1 for i in range(len(self.img_list))]).astype(
                np.double
            )
            self.res_y = np.array(
                [np.nan if i == 0 else i for i in self.res_list]
            ).astype(np.double)
            res_m = np.isfinite(self.res_y)

            self.res = self.res_axes.scatter(
                self.res_x[res_m],
                self.res_y[res_m],
                s=45,
                marker="o",
                edgecolors="black",
                color="#0571b0",
                picker=True,
            )
            res_median = np.median([i for i in self.res_list if i > 0])
            res_med = self.res_axes.axhline(res_median, c="#0571b0", ls="--")

            self.res_axes.set_xlim(0, np.nanmax(self.res_x) + 2)
            res_ymax = np.nanmax(self.res_y) * 1.1
            res_ymin = np.nanmin(self.res_y) * 0.9
            if res_ymin == res_ymax:
                res_ymax = res_ymin + 1
            self.res_axes.set_ylim(ymin=res_ymin, ymax=res_ymax)
            res_ylabel = "Resolution ({})".format(r"$\AA$")
            self.res_axes.set_ylabel(res_ylabel, fontsize=10)
            self.res_axes.yaxis.get_major_ticks()[0].label1.set_visible(False)
            self.res_axes.yaxis.get_major_ticks()[-1].label1.set_visible(False)
            plt.setp(self.res_axes.get_xticklabels(), visible=False)

            (self.nsref_pick,) = self.nsref_axes.plot(
                self.nsref_x[0],
                self.nsref_y[0],
                marker="o",
                ms=12,
                alpha=0.5,
                zorder=2,
                color="yellow",
                visible=False,
            )
            (self.res_pick,) = self.res_axes.plot(
                self.res_x[0],
                self.res_x[0],
                marker="o",
                zorder=2,
                ms=12,
                alpha=0.5,
                color="yellow",
                visible=False,
            )
            if self.pick["picked"] and self.pick["axis"] != "summary":
                img = self.pick["image"]
                idx = self.pick["index"]
                axis = self.pick["axis"]
                if axis == "nsref":
                    if not np.isnan(self.nsref_y[idx]):
                        self.nsref_pick.set_visible(True)
                        self.nsref_pick.set_data(self.nsref_x[idx], self.nsref_y[idx])
                elif axis == "res":
                    if not np.isnan(self.res_y[idx]):
                        self.res_pick.set_visible(True)
                        self.res_pick.set_data(self.res_x[idx], self.res_y[idx])
                self.info_txt.SetValue(img)
                self.btn_left.Enable()
                self.btn_right.Enable()
                self.btn_viewer.Enable()

        except ValueError, e:
            print "RES ERROR: ", e

    def calculate_uc_histogram(self, a, axes, xticks_loc="top", set_ylim=False):
        n, bins = np.histogram(a, 50)
        left = np.array(bins[:-1])
        right = np.array(bins[1:])
        bottom = np.zeros(len(left))
        top = bottom + n
        XY = np.array([[left, left, right, right], [bottom, top, top, bottom]]).T
        barpath = path.Path.make_compound_path_from_polys(XY)
        patch = mpatches.PathPatch(barpath, fc="#4575b4", lw=0, alpha=0.75)
        axes.add_patch(patch)

        axes.set_xlim(left[0], right[-1])
        if set_ylim:
            axes.set_ylim(bottom.min(), 1.05 * top.max())

        # axes.hist(a, 50, normed=False, facecolor='#4575b4',
        #                  histtype='stepfilled')
        axes.xaxis.get_major_ticks()[0].label1.set_visible(False)
        axes.xaxis.get_major_ticks()[-1].label1.set_visible(False)

        if xticks_loc == "top":
            axes.xaxis.tick_top()
        elif xticks_loc == "bottom":
            axes.xaxis.tick_bottom()

    def draw_uc_histograms(self):
        try:
            # Unit cell histograms
            finished = [
                i
                for i in self.finished_objects
                if i.fail == None and i.final["final"] != None
            ]
            if len(finished) > 0:
                self.a_axes.clear()
                self.b_axes.clear()
                self.c_axes.clear()
                self.alpha_axes.clear()
                self.beta_axes.clear()
                self.gamma_axes.clear()

                a = [i.final["a"] for i in finished]
                b = [i.final["b"] for i in finished]
                c = [i.final["c"] for i in finished]
                alpha = [i.final["alpha"] for i in finished]
                beta = [i.final["beta"] for i in finished]
                gamma = [i.final["gamma"] for i in finished]

                self.calculate_uc_histogram(
                    a, self.a_axes, xticks_loc="top", set_ylim=True
                )
                edge_ylabel = "a, b, c ({})".format(r"$\AA$")
                self.a_axes.set_ylabel(edge_ylabel)

                self.calculate_uc_histogram(b, self.b_axes, xticks_loc="top")
                plt.setp(self.b_axes.get_yticklabels(), visible=False)

                self.calculate_uc_histogram(c, self.c_axes, xticks_loc="top")
                plt.setp(self.c_axes.get_yticklabels(), visible=False)

                self.calculate_uc_histogram(
                    alpha, self.alpha_axes, xticks_loc="bottom", set_ylim=True
                )
                ang_ylabel = "{}, {}, {} ({})".format(
                    r"$\alpha$", r"$\beta$", r"$\gamma$", r"$^\circ$"
                )
                self.alpha_axes.set_ylabel(ang_ylabel)

                self.calculate_uc_histogram(beta, self.beta_axes, xticks_loc="bottom")
                plt.setp(self.beta_axes.get_yticklabels(), visible=False)

                self.calculate_uc_histogram(gamma, self.gamma_axes, xticks_loc="bottom")
                plt.setp(self.gamma_axes.get_yticklabels(), visible=False)

        except ValueError, e:
            print "UC HISTOGRAM ERROR: ", e

    # def draw_beamXY_plot(self):
    # try:
    #   # Beam XY (cumulative)
    #   info = []
    #   wavelengths = []
    #   distances = []
    #   cells = []
    #
    #   # Import relevant info
    #   for obj in self.finished_objects:
    #     fin = obj.final
    #     pickle = fin['final']
    #     if 'wavelength' in obj.final:
    #       info.append([pickle, fin['beamX'], fin['beamY']])
    #       wavelengths.append(fin['wavelength'])
    #       distances.append(fin['distance'])
    #       cells.append([fin['a'], fin['b'], fin['c'],
    #               fin['alpha'], fin['beta'], fin['gamma']])
    #     else:
    #       if (pickle is not None and
    #               os.path.isfile(pickle)):
    #         try:
    #           beam = ep.load(pickle)
    #           info.append([pickle, beam['xbeam'], beam['ybeam']])
    #           wavelengths.append(beam['wavelength'])
    #           distances.append(beam['distance'])
    #           cells.append(beam['observations'][0].unit_cell().parameters())
    #         except Exception, e:
    #           print 'BEAMXY_PLOT_ERROR: ', e
    #           pass
    #
    #   # Calculate beam center coordinates and distances
    #   if len(info) > 0:
    #     beamX = [i[1] for i in info]
    #     beamY = [j[2] for j in info]
    #     beam_dist = [math.hypot(i[1] - np.median(beamX), i[2] -
    #                             np.median(beamY)) for i in info]
    #
    #     wavelength = np.median(wavelengths)
    #     det_distance = np.median(distances)
    #     a = np.median([i[0] for i in cells])
    #     b = np.median([i[1] for i in cells])
    #     c = np.median([i[2] for i in cells])
    #
    #     # Calculate predicted L +/- 1 misindexing distance for each cell edge
    #     aD = det_distance * math.tan(2 * math.asin(wavelength / (2 * a)))
    #     bD = det_distance * math.tan(2 * math.asin(wavelength / (2 * b)))
    #     cD = det_distance * math.tan(2 * math.asin(wavelength / (2 * c)))
    #
    #     # Calculate axis limits of beam center scatter plot
    #     beamxy_delta = np.ceil(np.max(beam_dist))
    #     xmax = round(np.median(beamX) + beamxy_delta)
    #     xmin = round(np.median(beamX) - beamxy_delta)
    #     ymax = round(np.median(beamY) + beamxy_delta)
    #     ymin = round(np.median(beamY) - beamxy_delta)
    #
    #     if xmax == xmin:
    #       xmax += 0.5
    #       xmin -= 0.5
    #     if ymax == ymin:
    #       ymax += 0.5
    #       ymin -= 0.5
    #
    #     # Plot beam center scatter plot
    #     self.bxy_axes.clear()
    #     self.bxy_axes.axis('equal')
    #     self.bxy_axes.axis([xmin, xmax, ymin, ymax])
    #     self.bxy_axes.scatter(beamX, beamY, alpha=1, s=20, c='grey', lw=1)
    #     self.bxy_axes.plot(np.median(beamX), np.median(beamY), markersize=8, marker='o', c='yellow', lw=2)
    #
    #     # Plot projected mis-indexing limits for all three axes
    #     circle_a = plt.Circle((np.median(beamX), np.median(beamY)), radius=aD, color='r', fill=False, clip_on=True)
    #     circle_b = plt.Circle((np.median(beamX), np.median(beamY)), radius=bD, color='g', fill=False, clip_on=True)
    #     circle_c = plt.Circle((np.median(beamX), np.median(beamY)), radius=cD, color='b', fill=False, clip_on=True)
    #     self.bxy_axes.add_patch(circle_a)
    #     self.bxy_axes.add_patch(circle_b)
    #     self.bxy_axes.add_patch(circle_c)
    #     self.bxy_axes.set_xlabel('BeamX (mm)', fontsize=10)
    #     self.bxy_axes.set_ylabel('BeamY (mm)', fontsize=10)
    #     self.bxy_axes.set_title('Beam Center Coordinates')
    #
    #   self.int_canvas.draw()
    #
    # except ValueError, e:
    #   print 'BEAM XY ERROR: ', e

    def draw_measured_indices(self):
        # Extract indices from list and apply symmetry if any via miller object
        if self.idx_array is None:
            self.idx_array = flex.miller_index(self.indices)
        else:
            if self.indices != []:
                self.idx_array.extend(flex.miller_index(self.indices))
        self.indices = []

        if self.hkl_sg.toggle.GetValue():
            try:
                crystal_symmetry = crystal.symmetry(space_group_symbol=self.spacegroup)
            except RuntimeError:
                crystal_symmetry = crystal.symmetry(space_group_symbol="P1")
        else:
            crystal_symmetry = crystal.symmetry(space_group_symbol="P1")

        try:
            ms = miller.set(
                crystal_symmetry=crystal_symmetry,
                indices=self.idx_array,
                anomalous_flag=False,
            )
            equiv = ms.multiplicities().merge_equivalents()
            merged_indices = equiv.redundancies()

        except Exception, e:
            print "HKL ERROR: ", e
            return

        # Draw a h0, k0, or l0 slice of merged data so far
        self.hkl_axes.clear()
        try:
            self.hkl_colorbar.remove()
        except Exception:
            pass

        slice = merged_indices.slice(
            axis=self.hkl_view_axis, slice_start=0, slice_end=0
        )

        hkl = [i[0] for i in slice]
        freq = [i[1] for i in slice]

        if self.hkl_view_axis == "l":
            x = [i[0] for i in hkl]
            y = [i[1] for i in hkl]
            self.hkl_axes.set_xlabel("h", weight="bold")
            self.hkl_axes.set_ylabel("k", weight="bold", rotation="horizontal")
        elif self.hkl_view_axis == "k":
            x = [i[0] for i in hkl]
            y = [i[2] for i in hkl]
            self.hkl_axes.set_xlabel("h", weight="bold")
            self.hkl_axes.set_ylabel("l", weight="bold", rotation="horizontal")
        elif self.hkl_view_axis == "h":
            x = [i[1] for i in hkl]
            y = [i[2] for i in hkl]
            self.hkl_axes.set_xlabel("k", weight="bold")
            self.hkl_axes.set_ylabel("l", weight="bold", rotation="horizontal")
        else:
            # if for some reason this goes to plotting without any indices
            x = np.zeros(500)
            y = np.zeros(500)
            freq = np.zeros(500)

        # Format plot
        hkl_scatter = self.hkl_axes.scatter(x, y, c=freq, cmap="jet", s=1)
        self.hkl_axes.axhline(0, lw=0.5, c="black", ls="-")
        self.hkl_axes.axvline(0, lw=0.5, c="black", ls="-")
        self.hkl_axes.set_xticks([])
        self.hkl_axes.set_yticks([])
        self.hkl_axes.xaxis.set_label_coords(x=1, y=0.5)
        self.hkl_axes.yaxis.set_label_coords(x=0.5, y=1)

        try:
            xmax = abs(max(x, key=abs))
            ymax = abs(max(y, key=abs))
            self.hkl_axes.set_xlim(xmin=-xmax, xmax=xmax)
            self.hkl_axes.set_ylim(ymin=-ymax, ymax=ymax)
        except ValueError, e:
            pass

        norm = colors.Normalize(vmin=0, vmax=np.max(freq))
        self.hkl_colorbar = self.hkl_figure.colorbar(
            hkl_scatter,
            ax=self.hkl_axes,
            cmap="jet",
            norm=norm,
            orientation="vertical",
            aspect=40,
            use_gridspec=True,
        )

    def onImageView(self, e):
        filepath = self.info_txt.GetValue()
        viewer = self.gparams.advanced.image_viewer
        if os.path.isfile(filepath):
            viewer = thr.ImageViewerThread(self, viewer=viewer, file_string=filepath)
            viewer.start()

    def view_proc_images(self):
        if self.proc_fnames is not None:
            view_warning = dlg.ViewerWarning(self.parent, len(self.proc_fnames))
            if view_warning.ShowModal() == wx.ID_OK:
                # parse 'other' entry
                img_no_string = str(view_warning.no_images).split(",")
                filenames = []
                for n in img_no_string:
                    if "-" in n:
                        img_limits = n.split("-")
                        start = int(min(img_limits))
                        end = int(max(img_limits))
                        if start <= len(self.proc_fnames) and end <= len(
                            self.proc_fnames
                        ):
                            filenames.extend(self.proc_fnames[start:end])
                    else:
                        if int(n) <= len(self.proc_fnames):
                            filenames.append(self.proc_fnames[int(n)])
                file_string = " ".join(filenames)
                viewer = self.gparams.advanced.image_viewer
                viewer = thr.ImageViewerThread(
                    self, viewer=viewer, file_string=file_string
                )
                viewer.start()

    def onArrow(self, e):
        idx = self.pick["index"]
        self.pick["image"] = None
        if e.GetId() == self.btn_right.GetId():
            direction = 1
        elif e.GetId() == self.btn_left.GetId():
            direction = -1

        search = True
        while search:
            idx += direction
            try:
                if self.pick["axis"] == "nsref":
                    if not np.isnan(self.nsref_y[idx]):
                        self.pick["index"] = idx
                        self.pick["image"] = self.finished_objects[idx].conv_img
                        search = False
                    else:
                        search = True
                if self.pick["axis"] == "res":
                    if not np.isnan(self.res_y[idx]):
                        self.pick["index"] = idx
                        self.pick["image"] = self.finished_objects[idx].conv_img
                        search = False
                    else:
                        search = True
            except IndexError, e:
                search = False
                self.pick["index"] = idx
                self.pick["image"] = None

        self.draw_plots()

    def on_pick(self, event):
        self.pick["picked"] = True
        idx = int(round(event.mouseevent.xdata)) - 1
        obj_i = [i for i in self.finished_objects if i.img_index == idx + 1]
        img = obj_i[0].conv_img

        print "{}: {}".format(idx + 1, img)
        self.pick["image"] = img
        self.pick["index"] = idx

        if event.mouseevent.inaxes == self.nsref_axes:
            self.pick["axis"] = "nsref"
        elif event.mouseevent.inaxes == self.res_axes:
            self.pick["axis"] = "res"
        self.draw_plots()

    def on_bar_pick(self, event):
        self.show_image_group(e=event.mouseevent)

    def show_image_group(self, e):
        self.pick["picked"] = True
        if e.inaxes == self.sum_axes:
            self.pick["axis"] = "summary"
            self.pick["index"] = e.xdata
        self.draw_summary()

    def on_hkl_press(self, event):
        if event.inaxes == self.hkl_axes:
            if self.hkl_view_axis == "h":
                self.hkl_view_axis = "k"
            elif self.hkl_view_axis == "k":
                self.hkl_view_axis = "l"
            elif self.hkl_view_axis == "l":
                self.hkl_view_axis = "h"
            self.draw_plots()

    def on_button_press(self, event):
        if event.button != 1:
            self.pick["picked"] = False
            if event.inaxes == self.sum_axes:
                self.bracket.set_visible(False)
                self.draw_summary()
            elif event.inaxes == self.nsref_axes:
                self.nsref_pick.set_visible(False)
            elif event.inaxes == self.res_axes:
                self.res_pick.set_visible(False)

            self.draw_plots()

        if event.dblclick:
            self.dblclick = True
        else:
            self.dblclick = False

    def on_button_release(self, event):
        if event.button == 1 and self.dblclick:
            self.show_image_group(e=event)
            self.view_proc_images()


class SummaryTab(ScrolledPanel):
    def __init__(
        self,
        parent,
        init=None,
        gparams=None,
        final_objects=None,
        out_dir=None,
        plot=None,
    ):
        ScrolledPanel.__init__(self, parent)

        self.parent = parent
        self.final_objects = final_objects
        self.gparams = gparams
        self.out_dir = out_dir
        self.plot = plot
        self.init = init

        summary_sizer = wx.BoxSizer(wx.VERTICAL)

        sfont = wx.Font(norm_font_size, wx.DEFAULT, wx.NORMAL, wx.NORMAL)
        bfont = wx.Font(norm_font_size, wx.DEFAULT, wx.NORMAL, wx.BOLD)
        self.SetFont(bfont)

        # Run information
        run_box = wx.StaticBox(self, label="Run Information")
        run_box.SetFont(sfont)
        run_box_sizer = wx.StaticBoxSizer(run_box, wx.VERTICAL)
        run_box_grid = wx.FlexGridSizer(3, 2, 5, 20)
        self.title_txt = wx.StaticText(self, label="")
        self.title_txt.SetFont(sfont)
        self.folder_txt = wx.StaticText(self, label="")
        self.folder_txt.SetFont(sfont)

        run_box_grid.AddMany(
            [
                (wx.StaticText(self, label="Title")),
                (self.title_txt, 1, wx.EXPAND),
                (wx.StaticText(self, label="Directory")),
                (self.folder_txt, 1, wx.EXPAND),
            ]
        )

        run_box_grid.AddGrowableCol(1, 1)
        run_box_sizer.Add(run_box_grid, flag=wx.EXPAND | wx.ALL, border=10)

        summary_sizer.Add(run_box_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # Integration summary
        if self.gparams.advanced.integrate_with == "cctbx":
            int_box = wx.StaticBox(self, label="Analysis of Integration")
            int_box.SetFont(sfont)
            int_box_sizer = wx.StaticBoxSizer(int_box, wx.HORIZONTAL)
            int_box_grid = wx.FlexGridSizer(4, 5, 5, 20)
            int_btn_sizer = wx.BoxSizer(wx.VERTICAL)

            # Grid search summary
            self.sih_min = wx.StaticText(self, label="4.0")
            self.sih_min.SetFont(sfont)
            self.sih_max = wx.StaticText(self, label="8.0")
            self.sih_max.SetFont(sfont)
            self.sih_avg = wx.StaticText(self, label="6.0")
            self.sih_avg.SetFont(sfont)
            self.sih_std = wx.StaticText(self, label="0.05")
            self.sih_std.SetFont(sfont)
            self.sph_min = wx.StaticText(self, label="5.0")
            self.sph_min.SetFont(sfont)
            self.sph_max = wx.StaticText(self, label="12.0")
            self.sph_max.SetFont(sfont)
            self.sph_avg = wx.StaticText(self, label="8.5")
            self.sph_avg.SetFont(sfont)
            self.sph_std = wx.StaticText(self, label="0.15")
            self.sph_std.SetFont(sfont)
            self.spa_min = wx.StaticText(self, label="10.0")
            self.spa_min.SetFont(sfont)
            self.spa_max = wx.StaticText(self, label="20.0")
            self.spa_max.SetFont(sfont)
            self.spa_avg = wx.StaticText(self, label="15.0")
            self.spa_avg.SetFont(sfont)
            self.spa_std = wx.StaticText(self, label="0.01")
            self.spa_std.SetFont(sfont)

            int_box_grid.AddMany(
                [
                    (wx.StaticText(self, label="")),
                    (wx.StaticText(self, label="min")),
                    (wx.StaticText(self, label="max")),
                    (wx.StaticText(self, label="avg")),
                    (wx.StaticText(self, label="std")),
                    (wx.StaticText(self, label="minimum signal height")),
                    (self.sih_min),
                    (self.sih_max),
                    (self.sih_avg),
                    (self.sih_std),
                    (wx.StaticText(self, label="minimum spot height")),
                    (self.sph_min),
                    (self.sph_max),
                    (self.sph_avg),
                    (self.sph_std),
                    (wx.StaticText(self, label="minimum spot area")),
                    (self.spa_min),
                    (self.spa_max),
                    (self.spa_avg),
                    (self.spa_std),
                ]
            )

            # Button & binding for heatmap display
            heatmap_bmp = bitmaps.fetch_custom_icon_bitmap("heatmap24")
            self.int_heatmap = ct.GradButton(
                self, bmp=heatmap_bmp, label="  Spotfinding Heatmap", size=(250, -1)
            )
            int_btn_sizer.Add(self.int_heatmap)
            self.Bind(wx.EVT_BUTTON, self.onPlotHeatmap, self.int_heatmap)

            # Insert into sizers
            int_box_sizer.Add(int_box_grid, flag=wx.ALL, border=10)
            int_box_sizer.AddStretchSpacer()
            int_box_sizer.Add(int_btn_sizer, flag=wx.ALL, border=10)
            summary_sizer.Add(int_box_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # Dataset Info
        dat_box = wx.StaticBox(self, label="Dataset Information")
        dat_box.SetFont(sfont)
        dat_box_sizer = wx.StaticBoxSizer(dat_box, wx.HORIZONTAL)
        dat_box_grid = wx.FlexGridSizer(4, 2, 5, 20)
        dat_btn_sizer = wx.BoxSizer(wx.VERTICAL)

        self.pg_txt = wx.StaticText(self, label="P4")
        self.pg_txt.SetFont(sfont)
        self.uc_txt = wx.StaticText(self, label="79 79 38 90 90 90")
        self.uc_txt.SetFont(sfont)
        res = to_unicode(u"50.0 - 1.53 {}".format(u"\u212B"))
        self.rs_txt = wx.StaticText(self, label=res)
        self.rs_txt.SetFont(sfont)
        self.xy_txt = wx.StaticText(self, label="X = 224.90 mm, Y = 225.08 mm")
        self.xy_txt.SetFont(sfont)

        dat_box_grid.AddMany(
            [
                (wx.StaticText(self, label="Bravais lattice: ")),
                (self.pg_txt),
                (wx.StaticText(self, label="Unit cell: ")),
                (self.uc_txt),
                (wx.StaticText(self, label="Resolution: ")),
                (self.rs_txt),
                (wx.StaticText(self, label="Beam XY: ")),
                (self.xy_txt),
            ]
        )

        # Buttons for res. histogram and beam xy plot
        hist_bmp = bitmaps.fetch_icon_bitmap(
            "mimetypes", "spreadsheet", size=32, scale=(24, 24)
        )
        self.dat_reshist = ct.GradButton(
            self, bmp=hist_bmp, label="  Resolution Histogram", size=(250, -1)
        )
        beamXY_bmp = bitmaps.fetch_custom_icon_bitmap("scatter_plot_24")
        self.dat_beamxy = ct.GradButton(
            self, bmp=beamXY_bmp, label="  Beam XY Plot", size=(250, -1)
        )
        self.dat_beam3D = ct.GradButton(
            self, bmp=beamXY_bmp, label="  Beam XYZ Plot", size=(250, -1)
        )
        dat_btn_sizer.Add(self.dat_reshist)
        dat_btn_sizer.Add(self.dat_beamxy, flag=wx.TOP, border=5)
        dat_btn_sizer.Add(self.dat_beam3D, flag=wx.TOP, border=5)
        self.Bind(wx.EVT_BUTTON, self.onPlotBeamXY, self.dat_beamxy)
        self.Bind(wx.EVT_BUTTON, self.onPlotBeam3D, self.dat_beam3D)
        self.Bind(wx.EVT_BUTTON, self.onPlotResHist, self.dat_reshist)

        # Insert into sizers
        dat_box_sizer.Add(dat_box_grid, flag=wx.ALL, border=10)
        dat_box_sizer.AddStretchSpacer()
        dat_box_sizer.Add(dat_btn_sizer, flag=wx.ALL, border=10)
        summary_sizer.Add(dat_box_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # Clustering info
        self.cluster_panel = wx.Panel(self)
        cluster_box = wx.StaticBox(self.cluster_panel, label="Unit Cell Clustering")
        cluster_box_sizer = wx.StaticBoxSizer(cluster_box, wx.VERTICAL)
        self.cluster_panel.SetSizer(cluster_box_sizer)
        self.cluster_info = ct.CustomListCtrl(self.cluster_panel, size=(-1, 100))
        self.cluster_info.ctr.InsertColumn(0, "#")
        self.cluster_info.ctr.InsertColumn(1, "Lattice")
        self.cluster_info.ctr.InsertColumn(2, "Unit Cell")
        self.cluster_info.ctr.InsertColumn(3, "Filename")
        self.cluster_info.ctr.setResizeColumn(3)
        cluster_box_sizer.Add(self.cluster_info, proportion=1, flag=wx.EXPAND)
        summary_sizer.Add(self.cluster_panel, flag=wx.EXPAND | wx.ALL, border=10)

        # Hide if not done
        if not self.gparams.analysis.run_clustering:
            self.cluster_panel.Hide()

        # Summary
        smr_box = wx.StaticBox(self, label="Run Summary")
        smr_box.SetFont(sfont)
        smr_box_sizer = wx.StaticBoxSizer(smr_box, wx.HORIZONTAL)
        smr_box_grid = wx.FlexGridSizer(8, 2, 5, 20)
        smr_btn_sizer = wx.BoxSizer(wx.VERTICAL)

        self.readin_txt = wx.StaticText(self, label="250")
        self.readin_txt.SetFont(sfont)
        self.nodiff_txt = wx.StaticText(self, label="100")
        self.nodiff_txt.SetFont(sfont)
        self.w_diff_txt = wx.StaticText(self, label="150")
        self.w_diff_txt.SetFont(sfont)
        self.noint_txt = wx.StaticText(self, label="30")
        self.noint_txt.SetFont(sfont)
        self.final_txt = wx.StaticText(self, label="100")
        self.final_txt.SetFont(sfont)

        smr_box_grid.AddMany(
            [
                (wx.StaticText(self, label="Read in: ")),
                (self.readin_txt),
                (wx.StaticText(self, label="No diffraction:")),
                (self.nodiff_txt),
                (wx.StaticText(self, label="Have diffraction: ")),
                (self.w_diff_txt),
            ]
        )

        prime_bmp = bitmaps.fetch_custom_icon_bitmap("prime32", scale=(24, 24))
        self.smr_runprime = ct.GradButton(
            self, bmp=prime_bmp, label="  Run PRIME", size=(250, -1)
        )
        cluster_bmp = bitmaps.fetch_custom_icon_bitmap(
            "distance_difference", scale=(24, 24)
        )
        self.smr_runcluster = ct.GradButton(
            self, bmp=cluster_bmp, label="  Run CLUSTER", size=(250, -1)
        )

        smr_btn_sizer.Add(self.smr_runcluster)
        smr_btn_sizer.Add(self.smr_runprime, flag=wx.TOP, border=5)
        self.Bind(wx.EVT_BUTTON, self.onPRIME, self.smr_runprime)
        self.Bind(wx.EVT_BUTTON, self.onCLUSTER, self.smr_runcluster)

        if self.gparams.advanced.integrate_with == "cctbx":
            self.noprf_txt = wx.StaticText(self, label="20")
            self.noprf_txt.SetFont(sfont)
            smr_box_grid.AddMany(
                [
                    (wx.StaticText(self, label="Failed indexing / integration")),
                    (self.noint_txt),
                    (wx.StaticText(self, label="Failed filter")),
                    (self.noprf_txt),
                ]
            )
        elif self.gparams.advanced.integrate_with == "dials":
            self.nospf_txt = wx.StaticText(self, label="10")
            self.nospf_txt.SetFont(sfont)
            self.noidx_txt = wx.StaticText(self, label="20")
            self.noidx_txt.SetFont(sfont)
            self.noflt_txt = wx.StaticText(self, label="20")
            self.noflt_txt.SetFont(sfont)
            smr_box_grid.AddMany(
                [
                    (wx.StaticText(self, label="Failed spotfinding")),
                    (self.nospf_txt),
                    (wx.StaticText(self, label="Failed indexing")),
                    (self.noidx_txt),
                    (wx.StaticText(self, label="Failed integration")),
                    (self.noint_txt),
                    (wx.StaticText(self, label="Failed filter")),
                    (self.noflt_txt),
                ]
            )
        smr_box_grid.AddMany(
            [(wx.StaticText(self, label="Final integrated pickles")), (self.final_txt)]
        )

        smr_box_sizer.Add(smr_box_grid, flag=wx.ALL, border=10)
        smr_box_sizer.AddStretchSpacer()
        smr_box_sizer.Add(smr_btn_sizer, flag=wx.ALL, border=10)
        summary_sizer.Add(smr_box_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.SetFont(sfont)
        self.SetSizer(summary_sizer)
        self.SetupScrolling()

    def onPRIME(self, e):
        from prime.postrefine.mod_gui_init import PRIMEWindow

        self.prime_window = PRIMEWindow(
            self, -1, title="PRIME", prefix=self.gparams.advanced.prime_prefix
        )
        self.prime_window.load_script(out_dir=self.out_dir)
        self.prime_window.SetMinSize(self.prime_window.GetEffectiveMinSize())
        self.prime_window.Show(True)

    def onCLUSTER(self, e):
        cluster_dlg = dlg.ClusterDialog(self)
        cluster_dlg.write_files.SetValue(self.gparams.analysis.cluster_write_files)
        cluster_dlg.cluster_threshold.ctr.SetValue(
            self.gparams.analysis.cluster_threshold
        )
        cluster_dlg.cluster_limit.ctr.SetValue(self.gparams.analysis.cluster_limit)
        if self.gparams.analysis.cluster_n_images > 0:
            cluster_dlg.cluster_n_images.ctr.SetValue(
                self.gparams.analysis.cluster_n_images
            )

        if cluster_dlg.ShowModal() == wx.ID_OK:
            self.cluster_panel.Show()
            self.Layout()
            self.gparams.analysis.run_clustering = True
            self.gparams.analysis.cluster_write_files = (
                cluster_dlg.write_files.GetValue()
            )
            self.gparams.analysis.cluster_threshold = (
                cluster_dlg.cluster_threshold.ctr.GetValue()
            )
            self.gparams.analysis.cluster_limit = (
                cluster_dlg.cluster_limit.ctr.GetValue()
            )
            if cluster_dlg.cluster_n_images.toggle.GetValue():
                self.gparams.analysis.cluster_n_images = int(
                    cluster_dlg.cluster_n_images.ctr.GetValue()
                )
            else:
                self.gparams.analysis.cluster_n_images = 0
            self.init.params = self.gparams

            analysis = Analyzer(
                init=self.init, all_objects=self.final_objects, gui_mode=True
            )
            pg, uc, clusters = analysis.unit_cell_analysis()
            if clusters != []:
                self.report_clustering_results(clusters=clusters)

    def report_clustering_results(self, clusters):
        self.cluster_info.ctr.DeleteAllItems()
        clusters = sorted(clusters, key=lambda i: i["number"], reverse=True)
        for c in clusters:
            i = clusters.index(c)
            idx = self.cluster_info.ctr.InsertStringItem(i, str(c["number"]))
            self.cluster_info.ctr.SetStringItem(idx, 1, str(c["pg"]))
            self.cluster_info.ctr.SetStringItem(idx, 2, str(c["uc"]))
            if c["filename"] != "*":
                self.cluster_info.ctr.SetStringItem(idx, 3, c["filename"])

        self.Refresh()
        self.SetupScrolling()

    def onPlotHeatmap(self, e):
        if self.final_objects != None:
            self.plot.plot_spotfinding_heatmap()

    def onPlotBeamXY(self, e):
        if self.final_objects != None:
            self.plot.plot_beam_xy()

    def onPlotBeam3D(self, e):
        if self.final_objects != None:
            self.plot.plot_beam_xy(threeD=True)

    def onPlotResHist(self, e):
        if self.final_objects != None:
            self.plot.plot_res_histogram()


class ProcWindow(wx.Frame):
    """ New frame that will show processing info """

    def __init__(self, parent, id, title, phil, target_phil=None):
        wx.Frame.__init__(
            self,
            parent,
            id,
            title,
            size=(800, 900),
            style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX | wx.RESIZE_BORDER,
        )

        self.logtext = ""
        self.obj_counter = 0
        self.bookmark = 0
        self.gparams = phil.extract()

        self.target_phil = target_phil
        self.state = "process"
        self.recovery = False

        self.abort_initiated = False
        self.monitor_mode = False
        self.monitor_mode_timeout = None
        self.timeout_start = None
        self.find_new_images = self.monitor_mode
        self.start_object_finder = True
        self.finished_objects = []
        self.read_object_files = []
        self.new_images = []
        self.indices = []

        self.main_panel = wx.Panel(self)
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Toolbar
        self.proc_toolbar = self.CreateToolBar(style=wx.TB_3DBUTTONS | wx.TB_TEXT)
        abort_bmp = bitmaps.fetch_icon_bitmap("actions", "stop")
        self.tb_btn_abort = self.proc_toolbar.AddLabelTool(
            wx.ID_ANY, label="Abort", bitmap=abort_bmp, shortHelp="Abort"
        )
        resume_bmp = bitmaps.fetch_icon_bitmap("actions", "quick_restart")
        self.tb_btn_resume = self.proc_toolbar.AddLabelTool(
            wx.ID_ANY, label="Resume", bitmap=resume_bmp, shortHelp="Resume aborted run"
        )
        self.proc_toolbar.EnableTool(self.tb_btn_resume.GetId(), False)
        self.proc_toolbar.AddSeparator()
        watch_bmp = bitmaps.fetch_icon_bitmap("apps", "search")
        self.tb_btn_monitor = self.proc_toolbar.AddCheckLabelTool(
            wx.ID_ANY, label="Monitor", bitmap=watch_bmp, shortHelp="Monitor Mode"
        )
        self.proc_toolbar.Realize()

        # Status box
        self.status_panel = wx.Panel(self.main_panel)
        self.status_sizer = wx.BoxSizer(wx.VERTICAL)
        self.status_box = wx.StaticBox(self.status_panel, label="Status")
        self.status_box_sizer = wx.StaticBoxSizer(self.status_box, wx.HORIZONTAL)
        self.status_txt = wx.StaticText(self.status_panel, label="")
        self.status_box_sizer.Add(
            self.status_txt, flag=wx.ALL | wx.ALIGN_CENTER, border=10
        )
        self.status_sizer.Add(self.status_box_sizer, flag=wx.EXPAND | wx.ALL, border=3)
        self.status_panel.SetSizer(self.status_sizer)

        # Tabbed output window(s)
        self.proc_panel = wx.Panel(self.main_panel)
        self.proc_nb = wx.Notebook(self.proc_panel, style=0)
        self.chart_tab = ProcessingTab(self.proc_nb)
        self.log_tab = LogTab(self.proc_nb)
        self.proc_nb.AddPage(self.log_tab, "Log")
        self.proc_nb.AddPage(self.chart_tab, "Charts")
        self.proc_nb.SetSelection(1)
        self.proc_sizer = wx.BoxSizer(wx.VERTICAL)
        self.proc_sizer.Add(self.proc_nb, 1, flag=wx.EXPAND | wx.ALL, border=3)
        self.proc_panel.SetSizer(self.proc_sizer)

        self.main_sizer.Add(self.status_panel, flag=wx.EXPAND | wx.ALL, border=3)
        self.main_sizer.Add(self.proc_panel, 1, flag=wx.EXPAND | wx.ALL, border=3)
        self.main_panel.SetSizer(self.main_sizer)

        # Processing status bar
        self.sb = self.CreateStatusBar()
        self.sb.SetFieldsCount(2)
        self.sb.SetStatusWidths([-1, -2])

        # Output gauge in status bar
        self.gauge_process = wx.Gauge(
            self.sb, -1, style=wx.GA_HORIZONTAL | wx.GA_SMOOTH
        )
        rect = self.sb.GetFieldRect(0)
        self.gauge_process.SetPosition((rect.x + 2, rect.y + 2))
        self.gauge_process.SetSize((rect.width - 4, rect.height - 4))
        self.gauge_process.Hide()

        # Output polling timer
        self.timer = wx.Timer(self)

        # Event bindings
        self.Bind(thr.EVT_ALLDONE, self.onFinishedProcess)
        self.Bind(thr.EVT_IMGDONE, self.onFinishedImageFinder)
        self.sb.Bind(wx.EVT_SIZE, self.onStatusBarResize)
        self.Bind(wx.EVT_TIMER, self.onTimer, id=self.timer.GetId())

        # Button bindings
        self.Bind(wx.EVT_TOOL, self.onAbort, self.tb_btn_abort)
        self.Bind(wx.EVT_TOOL, self.onResume, self.tb_btn_resume)
        self.Bind(wx.EVT_TOOL, self.onMonitor, self.tb_btn_monitor)

        # Determine if monitor mode was previously selected
        if self.gparams.advanced.monitor_mode:
            self.proc_toolbar.ToggleTool(self.tb_btn_monitor.GetId(), True)
            self.monitor_mode = True
            if self.gparams.advanced.monitor_mode_timeout:
                if self.gparams.advanced.monitor_mode_timeout_length is None:
                    self.monitor_mode_timeout = 30
                else:
                    self.monitor_mode_timeout = (
                        self.gparams.advanced.monitor_mode_timeout_length
                    )

    def onMonitor(self, e):
        if self.proc_toolbar.GetToolState(self.tb_btn_monitor.GetId()):
            self.monitor_mode = True
            if self.gparams.advanced.monitor_mode_timeout:
                if self.gparams.advanced.monitor_mode_timeout_length is None:
                    self.monitor_mode_timeout = 30
                else:
                    self.monitor_mode_timeout = (
                        self.gparams.advanced.monitor_mode_timeout_length
                    )
        elif not self.proc_toolbar.GetToolState(self.tb_btn_monitor.GetId()):
            self.monitor_mode = False
            self.monitor_mode_timeout = None
        self.find_new_images = self.monitor_mode

    def onStatusBarResize(self, e):
        rect = self.sb.GetFieldRect(0)
        self.gauge_process.SetPosition((rect.x + 2, rect.y + 2))
        self.gauge_process.SetSize((rect.width - 4, rect.height - 4))
        self.Refresh()
        self.Layout()

    def onAbort(self, e):
        if self.gparams.mp_method == "lsf":
            kill_command = "bkill -J {}".format(self.job_id)
            easy_run.fully_buffered(kill_command)
        with open(self.tmp_abort_file, "w") as af:
            af.write("")
        self.abort_initiated = True
        self.status_txt.SetForegroundColour("red")
        self.status_txt.SetLabel("Aborting...")
        self.proc_toolbar.EnableTool(self.tb_btn_abort.GetId(), False)

    def onResume(self, e):
        """ Restarts an aborted run if the processing window is still open.
    Basically goes through self.finished_objects, extracts the raw image
    names and regenerates the self.img_list to only have those image paths;
    then finds any 'new' images (which includes unprocessed images as well as
    any images that may have been added during the abort pause) and runs
    processing """

        # Remove abort signal file(s)
        if os.path.isfile(self.tmp_abort_file):
            os.remove(self.tmp_abort_file)
        if os.path.isfile(self.tmp_aborted_file):
            os.remove(self.tmp_aborted_file)
        self.abort_initiated = False
        self.run_aborted = False

        # Re-generate new image info to include un-processed images
        input_entries = [i for i in self.gparams.input if i != None]
        ext_file_list = ginp.make_input_list(
            input_entries, filter=True, filter_type="image"
        )
        old_file_list = [i.raw_img for i in self.finished_objects]
        new_file_list = [i for i in ext_file_list if i not in old_file_list]

        # Generate list of new images
        self.new_images = [
            [i, len(ext_file_list) + 1, j]
            for i, j in enumerate(new_file_list, len(old_file_list) + 1)
        ]

        # Reset self.img_list to only processed images
        self.img_list = [
            [i, len(ext_file_list) + 1, j] for i, j in enumerate(old_file_list, 1)
        ]

        # Check if no images are left to process:
        if len(self.new_images) == 0:
            self.state = "finished"
            self.finish_process()
        else:
            # Reset toolbar buttons
            self.proc_toolbar.EnableTool(self.tb_btn_abort.GetId(), True)
            self.proc_toolbar.EnableTool(self.tb_btn_resume.GetId(), False)
            self.proc_toolbar.EnableTool(self.tb_btn_monitor.GetId(), True)

            # Run processing, etc.
            self.state = "resume"
            self.process_images()
            self.timer.Start(5000)

    def recover(self, int_path, status, init, params):
        self.recovery = True
        self.init = init
        self.gparams = params
        self.tmp_abort_file = os.path.join(int_path, ".abort.tmp")
        self.tmp_aborted_file = os.path.join(int_path, ".aborted.tmp")
        self.img_list = [
            [i, len(self.init.input_list) + 1, j]
            for i, j in enumerate(self.init.input_list, 1)
        ]
        self.status_txt.SetLabel("Searching in {} ...".format(int_path))

        self.status_summary = [0] * len(self.img_list)
        self.nref_list = [0] * len(self.img_list)
        self.nref_xaxis = [i[0] for i in self.img_list]
        self.res_list = [0] * len(self.img_list)

        self.state = status
        self.finished_objects = []

        self.last_object = None
        self.finish_process()

    def run(self, init):
        # Initialize IOTA parameters and log

        self.init = init
        good_init = self.init.run(self.gparams, target_phil=self.target_phil)

        # Start process
        if good_init:
            self.tmp_abort_file = os.path.join(self.init.int_base, ".abort.tmp")
            self.tmp_aborted_file = os.path.join(self.init.int_base, ".aborted.tmp")
            self.status_txt.SetForegroundColour("black")
            self.status_txt.SetLabel("Running...")
            self.process_images()
            self.good_to_go = True
            self.timer.Start(5000)

            # write init file
            ep.dump(os.path.join(self.init.int_base, "init.cfg"), self.init)

        else:
            self.good_to_go = False

    def process_images(self):
        """ One-fell-swoop importing / triaging / integration of images """

        # Set font properties for status window
        font = self.sb.GetFont()
        font.SetWeight(wx.NORMAL)
        self.status_txt.SetFont(font)
        self.status_txt.SetForegroundColour("black")

        if self.init.params.cctbx.selection.select_only.flag_on:
            self.img_list = [
                [i, len(self.init.gs_img_objects) + 1, j]
                for i, j in enumerate(self.init.gs_img_objects, 1)
            ]
            iterable = self.img_list
            self.status_summary = [0] * len(self.img_list)
            self.nref_list = [0] * len(self.img_list)
            self.nref_xaxis = [i[0] for i in self.img_list]
            self.res_list = [0] * len(self.img_list)
            type = "object"
            self.status_txt.SetLabel("Re-running selection...")
        else:
            type = "image"
            if self.state == "new images":
                iterable = self.new_images
                self.img_list.extend(self.new_images)
                self.new_images = []
                self.status_summary.extend([0] * len(iterable))
                self.nref_list.extend([0] * len(iterable))
                self.nref_xaxis.extend([i[0] for i in iterable])
                self.res_list.extend([0] * len(iterable))
                self.status_txt.SetForegroundColour("black")
                self.status_txt.SetLabel(
                    "Processing additional {} images ({} total)..."
                    "".format(len(iterable), len(self.img_list))
                )
                self.plot_integration()
            elif self.state == "resume":
                iterable = self.new_images
                self.img_list.extend(self.new_images)
                self.new_images = []
                # self.status_summary = [0] * len(self.img_list)
                # self.nref_list = [0] * len(self.img_list)
                # self.nref_xaxis = [i[0] for i in self.img_list]
                # self.res_list = [0] * len(self.img_list)
                self.status_txt.SetLabel(
                    "Processing {} remaining images ({} total)..."
                    "".format(len(iterable), len(self.img_list))
                )
                self.start_object_finder = True
            else:
                self.img_list = [
                    [i, len(self.init.input_list) + 1, j]
                    for i, j in enumerate(self.init.input_list, 1)
                ]
                iterable = self.img_list
                self.status_summary = [0] * len(self.img_list)
                self.nref_list = [0] * len(self.img_list)
                self.nref_xaxis = [i[0] for i in self.img_list]
                self.res_list = [0] * len(self.img_list)
                self.status_txt.SetLabel(
                    "Processing {} images..." "".format(len(self.img_list))
                )
        self.gauge_process.SetRange(len(self.img_list))

        if self.gparams.mp_method == "multiprocessing":
            self.img_process = thr.ProcThread(
                self,
                init=self.init,
                iterable=iterable,
                input_type=type,
                term_file=self.tmp_abort_file,
            )
            self.img_process.start()
        else:
            self.img_process = None
            self.job_id = None
            queue = self.gparams.mp_queue
            iter_path = os.path.join(self.init.int_base, "iter.cfg")
            init_path = os.path.join(self.init.int_base, "init.cfg")
            nproc = self.init.params.n_processors
            ep.dump(iter_path, iterable)
            ep.dump(init_path, self.init)

            if self.init.params.mp_method == "lsf":
                logfile = os.path.join(self.init.int_base, "bsub.log")
                pid = os.getpid()
                try:
                    user = os.getlogin()
                except OSError:
                    user = "iota"
                self.job_id = "J_{}{}".format(user[0], pid)
                command = (
                    "bsub -o {} -q {} -n {} -J {} "
                    "iota.process {} --files {} --type {} --stopfile {}"
                    "".format(
                        logfile,
                        queue,
                        nproc,
                        self.job_id,
                        init_path,
                        iter_path,
                        type,
                        self.tmp_abort_file,
                    )
                )
            elif self.init.params.mp_method == "torq":
                params = "{} --files {} --type {} --stopfile {}" "".format(
                    init_path, iter_path, type, self.tmp_abort_file
                )
                command = (
                    'qsub -e /dev/null -o /dev/null -d {} iota.process -F "{}"'
                    "".format(self.init.params.output, params)
                )
            else:
                command = None
            if command is not None:
                try:
                    print command
                    easy_run.fully_buffered(
                        command, join_stdout_stderr=True
                    ).show_stdout()
                    print "JOB NAME = ", self.job_id
                except thr.IOTATermination, e:
                    print "IOTA: JOB TERMINATED", e
            else:
                print "IOTA ERROR: COMMAND NOT ISSUED!"
                return

    def analyze_results(self, analysis=None):
        if len(self.final_objects) == 0:
            self.status_txt.SetForegroundColour("red")
            self.status_txt.SetLabel("No images successfully integrated")

        else:
            if not self.gparams.image_conversion.convert_only:
                self.status_txt.SetForegroundColour("black")
                self.status_txt.SetLabel("Analyzing results...")

                # Do analysis
                if analysis is None:
                    self.recovery = False
                    analysis = Analyzer(self.init, self.finished_objects, gui_mode=True)
                plot = Plotter(self.gparams, self.final_objects, self.init.viz_base)

                # Initialize summary tab
                prime_file = os.path.join(
                    self.init.int_base,
                    "{}.phil".format(self.gparams.advanced.prime_prefix),
                )
                self.summary_tab = SummaryTab(
                    self.proc_nb,
                    init=self.init,
                    gparams=self.gparams,
                    final_objects=self.final_objects,
                    out_dir=os.path.dirname(prime_file),
                    plot=plot,
                )

                # Run information
                self.summary_tab.title_txt.SetLabel(noneset(self.gparams.description))
                self.summary_tab.folder_txt.SetLabel(self.gparams.output)

                # Analysis of integration
                if self.gparams.advanced.integrate_with == "cctbx":
                    self.summary_tab.sih_min.SetLabel(
                        "{:4.0f}".format(np.min(analysis.s))
                    )
                    self.summary_tab.sih_max.SetLabel(
                        "{:4.0f}".format(np.max(analysis.s))
                    )
                    self.summary_tab.sih_avg.SetLabel(
                        "{:4.2f}".format(np.mean(analysis.s))
                    )
                    self.summary_tab.sih_std.SetLabel(
                        "{:4.2f}".format(np.std(analysis.s))
                    )
                    self.summary_tab.sph_min.SetLabel(
                        "{:4.0f}".format(np.min(analysis.h))
                    )
                    self.summary_tab.sph_max.SetLabel(
                        "{:4.0f}".format(np.max(analysis.h))
                    )
                    self.summary_tab.sph_avg.SetLabel(
                        "{:4.2f}".format(np.mean(analysis.h))
                    )
                    self.summary_tab.sph_std.SetLabel(
                        "{:4.2f}".format(np.std(analysis.h))
                    )
                    self.summary_tab.spa_min.SetLabel(
                        "{:4.0f}".format(np.min(analysis.a))
                    )
                    self.summary_tab.spa_max.SetLabel(
                        "{:4.0f}".format(np.max(analysis.a))
                    )
                    self.summary_tab.spa_avg.SetLabel(
                        "{:4.2f}".format(np.mean(analysis.a))
                    )
                    self.summary_tab.spa_std.SetLabel(
                        "{:4.2f}".format(np.std(analysis.a))
                    )

                # Dataset information
                if self.recovery:
                    pg = analysis.cons_pg
                    uc = analysis.cons_uc
                    clusters = analysis.clusters
                else:
                    analysis.print_results()
                    pg, uc, clusters = analysis.unit_cell_analysis()

                if clusters != []:
                    self.summary_tab.report_clustering_results(clusters=clusters)

                self.summary_tab.pg_txt.SetLabel(str(pg))
                unit_cell = " ".join(["{:4.1f}".format(i) for i in uc])
                self.summary_tab.uc_txt.SetLabel(unit_cell)
                res = to_unicode(
                    u"{:4.2f} - {:4.2f} {}".format(
                        np.mean(analysis.lres), np.mean(analysis.hres), u"\u212B"
                    )
                )
                self.summary_tab.rs_txt.SetLabel(res)

                if self.recovery and (
                    hasattr(analysis, "beamX_mm")
                    and hasattr(analysis, "beamY_mm")
                    and hasattr(analysis, "pixel_size")
                ):
                    beamX_mm = analysis.beamX_mm
                    beamY_mm = analysis.beamY_mm
                    pixel_size = analysis.pixel_size
                else:
                    with warnings.catch_warnings():
                        # To catch any 'mean of empty slice' runtime warnings
                        warnings.simplefilter("ignore", category=RuntimeWarning)
                        beamxy_calc = plot.calculate_beam_xy()
                        beamX, beamY = beamxy_calc[:2]
                        pixel_size = beamxy_calc[-1]
                        beamX_mm = np.median(beamX)
                        beamY_mm = np.median(beamY)
                beamX_px = beamX_mm / pixel_size
                beamY_px = beamY_mm / pixel_size
                beamXY = (
                    "X = {:4.1f} mm / {:4.0f} px\n"
                    "Y = {:4.1f} mm / {:4.0f} px"
                    "".format(beamX_mm, beamX_px, beamY_mm, beamY_px)
                )
                self.summary_tab.xy_txt.SetLabel(beamXY)

                # Summary
                if self.recovery:
                    self.summary_tab.readin_txt.SetLabel(str(analysis.n_all_objects))
                    self.summary_tab.nodiff_txt.SetLabel(
                        str(analysis.n_no_diff_objects)
                    )
                    self.summary_tab.w_diff_txt.SetLabel(str(analysis.n_diff_objects))
                    if self.gparams.advanced.integrate_with == "cctbx":
                        self.summary_tab.noint_txt.SetLabel(
                            str(analysis.n_not_int_objects)
                        )
                        self.summary_tab.noprf_txt.SetLabel(
                            str(analysis.n_filter_fail_objects)
                        )
                    elif self.gparams.advanced.integrate_with == "dials":
                        self.summary_tab.nospf_txt.SetLabel(
                            str(analysis.n_not_spf_objects)
                        )
                        self.summary_tab.noidx_txt.SetLabel(
                            str(analysis.n_not_idx_objects)
                        )
                        self.summary_tab.noint_txt.SetLabel(
                            str(analysis.n_not_int_objects)
                        )
                        self.summary_tab.noflt_txt.SetLabel(
                            str(analysis.n_filter_fail_objects)
                        )
                    self.summary_tab.final_txt.SetLabel(str(analysis.n_final_objects))
                else:
                    self.summary_tab.readin_txt.SetLabel(str(len(analysis.all_objects)))
                    self.summary_tab.nodiff_txt.SetLabel(
                        str(len(analysis.no_diff_objects))
                    )
                    self.summary_tab.w_diff_txt.SetLabel(
                        str(len(analysis.diff_objects))
                    )
                    if self.gparams.advanced.integrate_with == "cctbx":
                        self.summary_tab.noint_txt.SetLabel(
                            str(len(analysis.not_int_objects))
                        )
                        self.summary_tab.noprf_txt.SetLabel(
                            str(len(analysis.filter_fail_objects))
                        )
                    elif self.gparams.advanced.integrate_with == "dials":
                        self.summary_tab.nospf_txt.SetLabel(
                            str(len(analysis.not_spf_objects))
                        )
                        self.summary_tab.noidx_txt.SetLabel(
                            str(len(analysis.not_idx_objects))
                        )
                        self.summary_tab.noint_txt.SetLabel(
                            str(len(analysis.not_int_objects))
                        )
                        self.summary_tab.noflt_txt.SetLabel(
                            str(len(analysis.filter_fail_objects))
                        )
                    self.summary_tab.final_txt.SetLabel(
                        str(len(analysis.final_objects))
                    )

                    # Generate input file for PRIME
                    analysis.print_summary()
                    analysis.make_prime_input(filename=prime_file)

                # Display summary
                self.proc_nb.AddPage(self.summary_tab, "Analysis")
                self.proc_nb.SetSelection(2)

            # Signal end of run
            font = self.sb.GetFont()
            font.SetWeight(wx.BOLD)
            self.status_txt.SetFont(font)
            self.status_txt.SetForegroundColour("blue")
            self.status_txt.SetLabel("DONE")

        # Finish up
        self.display_log()
        self.plot_integration()

        # Stop timer
        self.timer.Stop()

    def display_log(self):
        """ Display PRIME stdout """
        if os.path.isfile(self.init.logfile):
            with open(self.init.logfile, "r") as out:
                out.seek(self.bookmark)
                output = out.read()
                self.bookmark = out.tell()

            ins_pt = self.log_tab.log_window.GetInsertionPoint()
            self.log_tab.log_window.AppendText(output)
            self.log_tab.log_window.SetInsertionPoint(ins_pt)

    def plot_integration(self):
        if self.nref_list is not None and self.res_list is not None:

            self.chart_tab.init = self.init
            self.chart_tab.gparams = self.gparams
            self.chart_tab.finished_objects = self.finished_objects
            self.chart_tab.img_list = self.img_list
            self.chart_tab.res_list = self.res_list
            self.chart_tab.nref_list = self.nref_list

            if self.chart_tab.spacegroup is None:
                if self.gparams.advanced.integrate_with == "dials":
                    sg = self.gparams.dials.target_space_group
                    if sg is not None:
                        self.chart_tab.spacegroup = str(sg)
                else:
                    self.chart_tab.spacegroup = "P1"

            self.chart_tab.indices = self.indices
            self.indices = []
            self.chart_tab.draw_plots()
            self.chart_tab.draw_summary()

    def find_objects(self, find_old=False):
        if find_old:
            min_back = None
        else:
            min_back = -1
        object_files = ginp.get_file_list(
            self.init.obj_base, ext_only="int", min_back=min_back
        )
        new_object_files = list(set(object_files) - set(self.read_object_files))
        new_objects = [self.read_object_file(i) for i in new_object_files]
        new_finished_objects = [
            i for i in new_objects if i is not None and i.status == "final"
        ]

        self.finished_objects.extend(new_finished_objects)
        self.read_object_files = [i.obj_file for i in self.finished_objects]

        self.populate_data_points(objects=new_finished_objects)

        if str(self.state).lower() in ("finished", "aborted", "unknown"):
            if self.finished_objects != []:
                self.finish_process()
            else:
                return
        else:
            self.start_object_finder = True

    def read_object_file(self, filepath):
        try:
            object = ep.load(filepath)
            if object.final["final"] is not None:
                pickle_path = object.final["final"]
                if os.path.isfile(pickle_path):
                    pickle = ep.load(pickle_path)
                    object.final["observations"] = pickle["observations"][0]
            return object
        except Exception, e:
            print "OBJECT_IMPORT_ERROR for {}: {}".format(filepath, e)
            return None

    def populate_data_points(self, objects=None):
        self.indices = []
        if objects is not None:
            for obj in objects:
                try:
                    self.nref_list[obj.img_index - 1] = obj.final["strong"]
                    self.res_list[obj.img_index - 1] = obj.final["res"]
                    if "observations" in obj.final:
                        self.indices.extend([i[0] for i in obj.final["observations"]])
                except Exception, e:
                    print "OBJECT_ERROR:", e, "({})".format(obj.obj_file)
                    pass

    def onTimer(self, e):
        if self.abort_initiated:
            if self.img_process is not None:
                self.run_aborted = self.img_process.aborted
            elif self.gparams.mp_method == "lsf":
                info_command = "bjobs -J {}".format(self.job_id)
                lsf_info = easy_run.fully_buffered(info_command).stdout_lines
                self.run_aborted = lsf_info == []
            else:
                self.run_aborted = os.path.isfile(self.tmp_aborted_file)

            if self.run_aborted:
                self.finish_process()
        else:
            self.run_aborted = False

        # Find processed image objects
        if self.start_object_finder:
            self.start_object_finder = False
            if self.finished_objects is None or self.finished_objects == []:
                self.last_object = None
            else:
                self.last_object = self.finished_objects[-1]
            self.find_objects()

        if len(self.finished_objects) > self.obj_counter:
            self.plot_integration()
            self.obj_counter = len(self.finished_objects)

        # Update gauge
        self.gauge_process.Show()
        self.gauge_process.SetValue(len(self.finished_objects))

        # Update status bar
        if self.gparams.image_conversion.convert_only:
            img_with_diffraction = [
                i
                for i in self.finished_objects
                if i.status == "imported" and i.fail == None
            ]
            self.sb.SetStatusText(
                "{} of {} images imported, {} have diffraction"
                "".format(
                    self.obj_counter,
                    len(self.init.input_list),
                    len(img_with_diffraction),
                ),
                1,
            )
        else:
            processed_images = [i for i in self.finished_objects if i.fail == None]
            self.sb.SetStatusText(
                "{} of {} images processed, {} successfully integrated"
                "".format(self.obj_counter, len(self.img_list), len(processed_images)),
                1,
            )

        # Update log
        self.display_log()

        # Run an instance of new image finder on a separate thread
        if self.find_new_images:
            self.find_new_images = False
            ext_image_list = self.img_list + self.new_images
            img_finder = thr.ImageFinderThread(
                self, image_paths=self.gparams.input, image_list=ext_image_list
            )
            img_finder.start()

        # Check if all images have been looked at; if yes, finish process
        if self.obj_counter >= len(self.img_list):
            if self.monitor_mode:
                if len(self.new_images) > 0:
                    self.status_txt.SetLabel(
                        "Found {} new images".format(len(self.new_images))
                    )
                    self.timeout_start = None
                    self.state = "new images"
                    self.process_images()
                else:
                    if self.monitor_mode_timeout != None:
                        if self.timeout_start is None:
                            self.timeout_start = time.time()
                        else:
                            interval = time.time() - self.timeout_start
                            if interval >= self.monitor_mode_timeout:
                                self.status_txt.SetLabel("Timed out. Finishing...")
                                self.finish_process()
                            else:
                                timeout_msg = (
                                    "No images found! Timing out in {} seconds"
                                    "".format(int(self.monitor_mode_timeout - interval))
                                )
                                self.status_txt.SetLabel(timeout_msg)
                    else:
                        self.find_new_images = self.monitor_mode
                        self.status_txt.SetLabel("No new images found! Waiting ...")
            else:
                self.status_txt.SetLabel("Wrapping up ...")
                self.finish_process()

    def onFinishedProcess(self, e):
        pass

    def onFinishedImageFinder(self, e):
        new_img = e.GetValue()
        self.new_images = self.new_images + new_img
        self.find_new_images = self.monitor_mode

    def finish_process(self):
        import shutil

        self.timer.Stop()

        if self.finished_objects is None:
            font = self.sb.GetFont()
            font.SetWeight(wx.BOLD)
            self.status_txt.SetFont(font)
            self.status_txt.SetForegroundColour("blue")
            self.status_txt.SetLabel("OBJECT READ-IN ERROR! NONE IMPORTED")
            return

        if str(self.state).lower() in ("finished", "aborted", "unknown"):
            self.gauge_process.Hide()
            font = self.sb.GetFont()
            font.SetWeight(wx.BOLD)
            self.status_txt.SetFont(font)
            run_no = int(self.init.int_base.split("/")[-1])
            self.status_txt.SetLabel("Run #{} Loaded!".format(run_no))
            self.proc_toolbar.EnableTool(self.tb_btn_abort.GetId(), False)
            self.proc_toolbar.EnableTool(self.tb_btn_monitor.GetId(), False)
            self.proc_toolbar.ToggleTool(self.tb_btn_monitor.GetId(), False)

            analysis_file = os.path.join(self.init.int_base, "analysis.pickle")
            if os.path.isfile(analysis_file):
                analysis = ep.load(analysis_file)
            else:
                analysis = None

            if self.finished_objects == []:
                if analysis is not None and hasattr(analysis, "image_objects"):
                    self.finished_objects = [
                        i
                        for i in analysis.image_objects
                        if i is not None and i.status == "final"
                    ]
                else:
                    self.find_objects(find_old=True)

            self.populate_data_points(objects=self.finished_objects)

            if str(self.state).lower() == "finished":
                self.final_objects = [
                    i for i in self.finished_objects if i.fail is None
                ]
                self.analyze_results(analysis=analysis)

            else:
                if len(self.finished_objects) > 0:
                    self.plot_integration()
                if os.path.isfile(os.path.join(self.init.int_base, "init.cfg")):
                    self.proc_toolbar.EnableTool(self.tb_btn_resume.GetId(), True)

            return

        elif self.run_aborted:
            self.gauge_process.Hide()
            font = self.sb.GetFont()
            font.SetWeight(wx.BOLD)
            self.status_txt.SetFont(font)
            self.status_txt.SetForegroundColour("red")
            self.status_txt.SetLabel("ABORTED BY USER")
            self.proc_toolbar.EnableTool(self.tb_btn_resume.GetId(), True)
            try:
                shutil.rmtree(self.init.tmp_base)
            except Exception:
                pass
            print "JOB TERMINATED!"
            return
        else:
            self.final_objects = [i for i in self.finished_objects if i.fail == None]
            self.gauge_process.Hide()
            self.proc_toolbar.EnableTool(self.tb_btn_abort.GetId(), False)
            self.proc_toolbar.EnableTool(self.tb_btn_monitor.GetId(), False)
            self.proc_toolbar.ToggleTool(self.tb_btn_monitor.GetId(), False)
            self.sb.SetStatusText(
                "{} of {} images successfully integrated"
                "".format(len(self.final_objects), len(self.img_list)),
                1,
            )
            if len(self.final_objects) > 0:
                # Signal end of run
                self.plot_integration()
                self.analyze_results()
            else:
                font = self.sb.GetFont()
                font.SetWeight(wx.BOLD)
                self.status_txt.SetFont(font)
                self.status_txt.SetForegroundColour("blue")
                self.status_txt.SetLabel("NO IMAGES PROCESSED")

            print "JOB FINISHED!"

            try:
                shutil.rmtree(self.init.tmp_base)
            except Exception:
                pass
