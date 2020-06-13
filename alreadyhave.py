import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject, GLib

import argparse
import os
import datetime
import threading
import pathlib
from pathlib import PurePath
import itertools

# For opening files on a right click
import subprocess
import platform

from model.directory import Directory, File

def is_subdir(parent_dir, _dir):
    """ Tests if _dir is a subdirectory of parent_dir """
    return pathlib.Path(parent_dir).resolve() in pathlib.Path(_dir).resolve().parents

def sizeof_format(num, suffix="B"):
    """ Makes a human-readable file size.
        Adapted from https://stackoverflow.com/questions/1094841 """
    if num < 1024:
        # Don't include the decimal place for bytes
        return "{bytes} {suffix}".format(bytes=num, suffix=suffix)
    num /= 1024.0
    for unit in ['Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "{:3.2f} {unit}{suffix}".format(num, unit=unit, suffix=suffix)
        num /= 1024.0
    return "{:3.2f} {unit}{suffix}".format(num, unit=unit, suffix=suffix)

def open_file_external(filepath):
    """ Opens a file with its default application, depending on the platform.
        Adapted from https://stackoverflow.com/questions/434597 """
    if platform.system() == 'Darwin':
        # macOS
        subprocess.call(('open', filepath))
    elif platform.system() == 'Windows':
        # Windows
        os.startfile(filepath)
    elif platform.system() == 'Linux':
        # Linux
        subprocess.call(('xdg-open', filepath))
    else:
        print("I don't know how to open files on this platform yet:", platform.system())

class AppWindow(Gtk.Window):
    def __init__(self, dirs):
        Gtk.Window.__init__(self, title="AlreadyHave")
        self.set_default_size(1200, 600)
        
        # Box containing each of the "columns" (directories open)
        self.colsbox = Gtk.Box()
        self.colsbox.props.spacing = 5
        self.colsbox.props.homogeneous = True
        self.add(self.colsbox)
        
        self.dir_paths = dirs
        self.dirs = []
        self.dirs_cd = [PurePath(".")] * len(dirs)
        self.dirs_list_stores = []
        self.progress_bars = []
        self.tree_views = []
        self.toolbar_buttons = []
        self.entries = []
        
        # Number of directories currently loaded
        self.num_dirs_loaded = 0
        
        for dir_index, dirpath in enumerate(self.dir_paths):
            # Add this directory (column)
            thiscol = Gtk.Box()
            thiscol.props.orientation = Gtk.Orientation.VERTICAL
            self.colsbox.pack_start(thiscol, True, True, 0)
            
            # Progress bar for scanning the directory
            progress_bar = Gtk.ProgressBar()
            progress_bar.set_show_text(True)
            progress_bar.set_ellipsize(2)
            self.progress_bars.append(progress_bar)
            thiscol.pack_start(progress_bar, False, True, 0)
            
            # Add entry (with directory name in it)
            entry = Gtk.Entry()
            entry.set_text(str(pathlib.Path(dirpath).resolve()))
            entry.connect("activate", self.set_dir, dir_index)
            self.entries.append(entry)
            thiscol.pack_start(entry, False, True, 0)
            
            # Add toolbar with actions
            toolbar = Gtk.Toolbar()
            toolbutton_up_dir = Gtk.ToolButton()
            toolbutton_up_dir.set_label("Up")
            toolbutton_up_dir.set_is_important(True)
            toolbutton_up_dir.set_icon_name("gtk-go-up")
            toolbutton_up_dir.set_sensitive(False)
            toolbutton_up_dir.connect("clicked", self.go_up_dir, dir_index)
            
            # Add the "Go up a directory" button to the end of the toolbar
            toolbar.insert(toolbutton_up_dir, -1)
            thiscol.pack_start(toolbar, False, True, 0)
            
            self.toolbar_buttons.append({
                "up": toolbutton_up_dir
            })
            
            # Create ListStore
            # Filename, Size, Modified Date, IsDir, row_color
            list_store = Gtk.ListStore(str, GObject.TYPE_INT64, str, GObject.TYPE_INT64, str)
            self.dirs_list_stores.append(list_store)
            
            # Add tree view
            tree_view = Gtk.TreeView(list_store)
            self.tree_views.append(tree_view)
            
            for i, column_title in [(0, "Filename"), (1, "Size"), (2, "Last Modified")]:
                renderer = Gtk.CellRendererText()
                column = Gtk.TreeViewColumn(column_title, renderer, text=i, background=4)
                column.set_resizable(True)
                column.set_sort_column_id(i)
                if column_title == "Size":
                    # Set custom data function for file sizes
                    column.set_cell_data_func(renderer, self.render_file_size)
                    # Align header and data to the right
                    column.set_alignment(1.0)
                    renderer.set_alignment(1.0, 0.0)
                tree_view.append_column(column)
            
            # Handle selections
            selected_row = tree_view.get_selection()
            selected_row.connect("changed", self.item_selected)
            tree_view.connect("row-activated", self.row_activated)
            tree_view.connect("button-release-event", self.row_clicked, dir_index)
            
            # Add ScrollableWindow to house the tree view
            tree_view_scrollable = Gtk.ScrolledWindow()
            tree_view_scrollable.set_policy(Gtk.PolicyType.AUTOMATIC,
                Gtk.PolicyType.AUTOMATIC)
            tree_view_scrollable.set_propagate_natural_width(True)
            tree_view_scrollable.set_propagate_natural_height(True)
            tree_view_scrollable.add(tree_view)
            thiscol.pack_start(tree_view_scrollable, True, True, 0)
        
        # Start scanning the directories
        for dir_index in range(len(dirs)):
            this_dir = Directory(self.dir_paths[dir_index])
            self.dirs.append(this_dir)
            update_function = (lambda x: lambda done, total, path: GLib.idle_add(
                self.set_progress, x, done/total, path))(dir_index)
            finish_function = (lambda x: lambda: self.finish_scan(x))(dir_index)
            thread = threading.Thread(target=this_dir.scan, args=(update_function, finish_function))
            thread.daemon = True
            thread.start()

    def render_file_size(self, tree_column, cell, tree_model, _iter, data):
        """ Renders a file size in a human-readable format in the TreeView """
        file_size = tree_model.get_value(_iter, 1)
        if file_size >= 0:
            cell.set_property("text", sizeof_format(file_size))
        else:
            # Hide for directories
            cell.set_property("text", "")

    def set_dir(self, entry, dir_id):
        """ Set the directory for this entry, if it's valid.
            If it's not valid, set the entry's text to the current directory. """
        good_dir = False
        entry_dir = pathlib.Path(entry.get_text())
        if entry_dir.is_dir():
            # Equal to the root directory
            if entry_dir == pathlib.Path(self.dirs[dir_id].root_path).resolve():
                good_dir = True
            elif is_subdir(self.dirs[dir_id].root_path, entry_dir):
                good_dir = True
        
        if good_dir:
            self.list_dir_contents(dir_id, entry_dir
                .relative_to(pathlib.Path(self.dirs[dir_id].root_path).resolve()))
        else:
            # Get a Path object so that it can be resolved
            root_path_path = pathlib.Path(self.dirs[dir_id].root_path)
            entry.set_text(str(root_path_path.joinpath(self.dirs_cd[dir_id]).resolve()))
    
    def go_up_dir(self, button, dir_id):
        if self.dirs_cd[dir_id] != PurePath("."):
            self.list_dir_contents(dir_id, self.dirs_cd[dir_id].parent)
    
    def list_dir_contents(self, dir_id, directory):
        """ Shows the contents of "directory" in the TreeView """
        self.dirs_cd[dir_id] = directory
        
        # Update entry
        root_path_path = pathlib.Path(self.dirs[dir_id].root_path)
        self.entries[dir_id].set_text(
            str(root_path_path.joinpath(self.dirs_cd[dir_id]).resolve()))
        
        # Update directory up button
        enable_up_button = self.dirs_cd[dir_id] != PurePath(".")
        self.toolbar_buttons[dir_id]["up"].set_sensitive(enable_up_button)
        
        # Clear old view
        self.dirs_list_stores[dir_id].clear()
        
        # Populate
        for file_index in range(len(self.dirs[dir_id].directory_map[directory])):
            _file = self.dirs[dir_id].directory_map[directory][file_index]
            if _file.isdir:
                # Set the color to be a bit lighter if the directory was
                # only partially matched
                dir_name = _file.get_path()
                
                if dir_name in self.dirs[dir_id].directory_map_file:
                    print("{} {} / {}".format(_file.path, _file.to_match, _file.to_match_total))
                    if _file.to_match == 0:
                        if _file.to_match_total == 0:
                            # Empty directory, or directory with exclusively empty subdirectories
                            # Color: Gainsboro
                            color = "#DCDCDC"
                        else:
                            # All items in this directory are matched
                            color = "greenyellow"
                    elif _file.to_match < _file.to_match_total:
                        # Some files in this directory are matched
                        color = "palegreen"
                    else:
                        # No files in this directory are matched
                        color = "white"
                else:
                    # TODO: Remove
                    print("Warning?? {} for {} not in {}".format(dir_name, _file.path, [self.dirs[dir_id].directory_map_file.keys()]))
                    color = "white"
            else:
                color = "greenyellow" if _file.matched else "white"
            self.dirs_list_stores[dir_id].append([_file.basename, _file.size,
                str(_file.modified), file_index, color])
    
    def finish_scan(self, dir_id):
        print(str(self.dirs[dir_id].root_path) + " finished scanning "
            + str(len(self.dirs[dir_id].file_list)) + " files.")
        # Add top directory to list store
        self.list_dir_contents(dir_id, self.dirs_cd[dir_id])
        
        # Remove progress bar
        print("Should hide progress bar {}".format(dir_id))
        self.progress_bars[dir_id].hide()
        
        # Begin finding potential collisions if all directories are loaded
        self.num_dirs_loaded += 1
        if self.num_dirs_loaded == len(self.dirs):
            self.find_duplicates()
    
    def propagate_matched(self, _dir, _file, empty=False):
        """ Propagates to parent directories that the file was matched
            If empty is True, then the to_match_total will also be
            decreased """
        if _file.matched:
            return
        _file.matched = True
        if not _file.isdir:
            _file.set_match(-1, affect_total=empty)
    
    def find_duplicates(self):
        """ Finds duplicate files in separate directories """
        for dir_1, dir_2 in itertools.combinations(self.dirs, r=2):
            print("dir_1: {} dir_2: {}".format(dir_1, dir_2))
            for _file in dir_1.file_list:
                # First, compare sizes
                if _file.size in dir_2.size_map:
                    self.propagate_matched(dir_1, _file)
                    for _file2 in dir_2.size_map[_file.size]:
                        self.propagate_matched(dir_2, _file2)
                
        for i in range(len(self.dirs)):
            GLib.idle_add(self.list_dir_contents, i, PurePath("."))
        
    def set_progress(self, dir_id, fraction, text):
        """ Sets the progress of one of the directories """
        self.progress_bars[dir_id].set_fraction(fraction)
        self.progress_bars[dir_id].set_text(text)
    
    def row_activated(self, tree_view, path, column):
        dir_id = self.tree_views.index(tree_view)
        print("Row activated:", path, "Index:", dir_id)
        
        file_index = self.dirs_list_stores[dir_id][path][3]
        _file = self.dirs[dir_id].directory_map[self.dirs_cd[dir_id]][file_index]
        
        if _file.isdir:
            self.list_dir_contents(dir_id, _file.get_path())
    
    def row_clicked(self, tree_view, event, dir_id):
        model, tree_iter = tree_view.get_selection().get_selected()
        if tree_iter is not None:
            # Open if it's a right click
            if event.button == 3:
                filename = model[tree_iter][0]
                full_path = (self.dirs[dir_id].root_path
                            .joinpath(self.dirs_cd[dir_id])
                            .joinpath(PurePath(filename)))
                open_file_external(full_path)
    
    def item_selected(self, selection):
        """ Handle when a file is selected """
        model, row = selection.get_selected()
        if row is not None:
            print("File: " + model[row][0])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dirs", nargs="*", help="Directories to compare")
    args = parser.parse_args()
    while len(args.dirs) < 2:
        args.dirs.append(".")
    
    # Unnecessary for PyGObject >= 3.10.2
    #GObject.threads_init()
    window = AppWindow(args.dirs)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
