import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

import argparse
import os
import datetime

def list_dir(dirpath):
    """ Lists all the files and subdirectories in a directory.
        Returns the list. """
    out_list = []
    for path, subdirs, files in os.walk(dirpath):
        for name in files:
            out_list.append(os.path.join(path, name))
        for subdir in subdirs:
            out_list.append(os.path.join(path, subdir))
    return out_list

class AppWindow(Gtk.Window):
    def __init__(self, dirs):
        Gtk.Window.__init__(self, title="AlreadyHave")
        
        # Box containing each of the "columns" (directories open)
        self.colsbox = Gtk.Box()
        self.colsbox.props.spacing = 5
        self.colsbox.props.homogeneous = True
        self.add(self.colsbox)
        
        self.dirs = dirs
        
        for dirpath in self.dirs:
            # Add this directory (column)
            thiscol = Gtk.Box()
            thiscol.props.orientation = Gtk.Orientation.VERTICAL
            self.colsbox.pack_start(thiscol, True, True, 0)
            
            # Add entry (with directory name in it)
            entry = Gtk.Entry()
            entry.set_text(dirpath)
            thiscol.pack_start(entry, False, True, 0)
            
            # Create ListStore
            # Filename, Size, Modified Date, IsDir
            list_store = Gtk.ListStore(str, GObject.TYPE_INT64, str, int)
            for path in list_dir(dirpath):
                # Get information
                stat_info = os.stat(path)
                mdate_str = str(datetime.datetime.fromtimestamp(stat_info.st_mtime))
                if not dirpath.endswith("/"):
                    dirpath += "/"
                list_store.append([path[len(dirpath):], stat_info.st_size, mdate_str])
            
            # Add tree view
            tree_view = Gtk.TreeView(list_store)
            tree_view.set_size_request(-1, 600)
            
            for i, column_title in [(0, "Filename"), (1, "Size"), (2, "Last Modified")]:
                renderer = Gtk.CellRendererText()
                column = Gtk.TreeViewColumn(column_title, renderer, text=i)
                column.set_resizable(True)
                tree_view.append_column(column)
            
            # Add ScrollableWindow to house the tree view
            tree_view_scrollable = Gtk.ScrolledWindow()
            tree_view_scrollable.set_policy(Gtk.PolicyType.AUTOMATIC,
                Gtk.PolicyType.AUTOMATIC)
            tree_view_scrollable.set_propagate_natural_width(True)
            tree_view_scrollable.set_propagate_natural_height(True)
            tree_view_scrollable.add(tree_view)
            thiscol.pack_start(tree_view_scrollable, True, True, 0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dirs", nargs="*", help="Directories to compare")
    args = parser.parse_args()
    while len(args.dirs) < 2:
        args.dirs.append(".")
    
    window = AppWindow(args.dirs)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
