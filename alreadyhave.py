import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject, GLib

import argparse
import os
import datetime
import threading
import pathlib
from pathlib import PurePath

all_files = {}

class File():
    def __init__(self, path, size, modified, isdir):
        self.path = path
        self.basename = os.path.basename(path)
        self.size = size
        self.modified = modified
        self.isdir = isdir
        self.hash_1k = None
        self.hash_full = None

class Directory():
    def __init__(self, path):
        """ Initialize a Directory object with a root path """
        if not os.path.isdir(path):
            raise Exception(path + " is not a directory")
        self.root_path = os.path.abspath(path)
        
        # Set up the data structures
        self.file_list = []
        self.directory_map = {}
        self.filename_map = {}
        self.size_map = {}
    
    def scan(self, update_function = None, finish_function = None):
        """ Scan the directory and all subdirectories for files and folders,
            periodically sending updates with update_function """
        # Files and folders left to read (initialized to 1 to read the root
        # directory)
        entries_total = 1
        # Files and folders read so far
        entries_done = 0
        
        for path, subdirs, files in os.walk(self.root_path):
            entries_done += 1
            entries_total += len(subdirs) + len(files)
            
            # Add this folder to the directory map
            path_shortened = os.path.relpath(path, start=self.root_path)
            self.directory_map[path_shortened] = []
            
            # Add subdirectories
            for subdir in subdirs:
                try:
                    stat_info = os.stat(os.path.join(path, subdir))
                    mdate = datetime.datetime.fromtimestamp(stat_info.st_mtime)
                    dirfile = File(os.path.join(path_shortened, subdir), 0, mdate,
                                   True)
                    
                    # Add to data structures
                    file_index = len(self.file_list)
                    self.file_list.append(dirfile)
                    self.directory_map[path_shortened].append(file_index)
                except (FileNotFoundError, PermissionError):
                    pass
                
                if entries_done % 1000 == 0 and update_function is not None:
                    update_function(entries_done, entries_total, dirfile.path)
            
            # Add files
            for filename in files:
                try:
                    stat_info = os.stat(os.path.join(path, filename))
                    mdate = datetime.datetime.fromtimestamp(stat_info.st_mtime)
                    _file = File(os.path.join(path_shortened, filename),
                                 stat_info.st_size, mdate, False)
                    
                    # Add to data structures
                    file_index = len(self.file_list)
                    self.file_list.append(_file)
                    self.directory_map[path_shortened].append(file_index)
                    self.filename_map[_file.basename] = file_index
                    self.size_map[_file.size] = file_index
                except (FileNotFoundError, PermissionError):
                    pass
                
                entries_done += 1
                
                if entries_done % 1000 == 0 and update_function is not None:
                    update_function(entries_done, entries_total, _file.path)
            
            # Reset some of these
            entries_done -= len(files) + 1
            entries_total -= len(files) + 1
        update_function(1, 1, None)
        finish_function()

def list_dir(dirpath):
    """ Lists all the files and subdirectories in a directory.
        Returns the list. """
    out_list = []
    for path, subdirs, files in os.walk(dirpath):
        if len(subdirs) == 0 and len(files) == 0:
            print("Empty path: " + path)
        for subdir in subdirs:
            out_list.append(os.path.join(path, subdir))
            print(out_list[len(out_list) - 1])
        for name in files:
            out_list.append(os.path.join(path, name))
            print(out_list[len(out_list) - 1])
    return out_list

def is_subdir(parent_dir, _dir):
    """ Tests if _dir is a subdirectory of parent_dir """
    return pathlib.Path(parent_dir).resolve() in pathlib.Path(_dir).resolve().parents

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
        self.dirs_cd = ["."] * len(dirs)
        self.dirs_list_stores = []
        self.progress_bars = []
        self.tree_views = []
        self.toolbar_buttons = []
        self.entries = []
        
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
            entry.set_text(os.path.abspath(dirpath))
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
            # Filename, Size, Modified Date, IsDir
            list_store = Gtk.ListStore(str, GObject.TYPE_INT64, str, GObject.TYPE_INT64)
            self.dirs_list_stores.append(list_store)
            """for path in list_dir(dirpath):
                # Get information
                stat_info = os.stat(path)
                mdate_str = str(datetime.datetime.fromtimestamp(stat_info.st_mtime))
                if not dirpath.endswith("/"):
                    dirpath += "/"
                list_store.append([path[len(dirpath):], stat_info.st_size, mdate_str])"""
            
            # Add tree view
            tree_view = Gtk.TreeView(list_store)
            self.tree_views.append(tree_view)
            
            for i, column_title in [(0, "Filename"), (1, "Size"), (2, "Last Modified")]:
                renderer = Gtk.CellRendererText()
                column = Gtk.TreeViewColumn(column_title, renderer, text=i)
                column.set_resizable(True)
                column.set_sort_column_id(i)
                tree_view.append_column(column)
            
            # Handle selections
            selected_row = tree_view.get_selection()
            selected_row.connect("changed", self.item_selected)
            tree_view.connect("row-activated", self.row_activated)
            
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

    def set_dir(self, entry, dir_id):
        """ Set the directory for this entry, if it's valid.
            If it's not valid, set the entry's text to the current directory. """
        good_dir = False
        if os.path.isdir(entry.get_text()):
            # Equal to the root directory
            if pathlib.Path(entry.get_text()) == pathlib.Path(self.dirs[dir_id].root_path):
                good_dir = True
            elif is_subdir(self.dirs[dir_id].root_path, entry.get_text()):
                good_dir = True
        
        if good_dir:
            self.list_dir_contents(dir_id, os.path.relpath(entry.get_text(), start=self.dirs[dir_id].root_path))
        else:
            entry.set_text(os.path.abspath(os.path.join(self.dirs[dir_id].root_path, self.dirs_cd[dir_id])))
    
    def go_up_dir(self, button, dir_id):
        if os.path.normpath(self.dirs_cd[dir_id]) != os.path.normpath("."):
            self.list_dir_contents(dir_id, os.path.normpath(os.path.join(self.dirs_cd[dir_id], "..")))
    
    def list_dir_contents(self, dir_id, directory):
        """ Shows the contents of "directory" in the TreeView """
        self.dirs_cd[dir_id] = directory
        
        # Update entry
        self.entries[dir_id].set_text(os.path.abspath(
            os.path.join(self.dirs[dir_id].root_path, self.dirs_cd[dir_id])))
        
        # Update directory up button
        enable_up_button = os.path.normpath(self.dirs_cd[dir_id]) != os.path.normpath(".")
        self.toolbar_buttons[dir_id]["up"].set_sensitive(enable_up_button)
        
        # Clear old view
        self.dirs_list_stores[dir_id].clear()
        
        # Populate
        for file_index in self.dirs[dir_id].directory_map[directory]:
            _file = self.dirs[dir_id].file_list[file_index]
            self.dirs_list_stores[dir_id].append([_file.basename, _file.size,
                str(_file.modified), file_index])
    
    def finish_scan(self, dir_id):
        print(self.dirs[dir_id].root_path + " finished scanning "
            + str(len(self.dirs[dir_id].file_list)) + " files.")
        # Add top directory to list store
        self.list_dir_contents(dir_id, self.dirs_cd[dir_id])
        
        # Remove progress bar
        print("Should hide progress bar {}".format(dir_id))
        self.progress_bars[dir_id].hide()
        
    def set_progress(self, dir_id, fraction, text):
        """ Sets the progress of one of the directories """
        self.progress_bars[dir_id].set_fraction(fraction)
        self.progress_bars[dir_id].set_text(text)
    
    def row_activated(self, tree_view, path, column):
        dir_id = self.tree_views.index(tree_view)
        print("Row activated:", path, "Index:", dir_id)
        
        file_index = self.dirs_list_stores[dir_id][path][3]
        _file = self.dirs[dir_id].file_list[file_index]
        
        if _file.isdir:
            self.list_dir_contents(dir_id, os.path.relpath(os.path.join(self.dirs_cd[dir_id], _file.basename)))
    
    
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
