import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import argparse

class AppWindow(Gtk.Window):
    def __init__(self, dirs):
        Gtk.Window.__init__(self, title="AlreadyHave")
        
        # Box containing each of the "columns" (directories open)
        self.colsbox = Gtk.Box()
        self.colsbox.props.visible = True
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
            
            # Add tree view
            # ...

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
