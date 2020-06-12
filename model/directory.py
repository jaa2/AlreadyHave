"""Includes the necessary classes for storing information about files and
    directories."""

import os
import datetime

from pathlib import PurePath

class File():
    def __init__(self, path, size, modified, isdir, parent=None):
        self.path = path
        self.basename = os.path.basename(path)
        self.size = size
        self.modified = modified
        self.isdir = isdir
        self.hash_1k = None
        self.hash_full = None
        self.matched = False
        
        # For a directory, the number of files/subdirs left to match
        self.to_match = 0
        self.to_match_total = 0
        
        self.parent_dir = parent
    
    def get_path(self):
        """ Returns a complete PurePath of this object.
            Runtime: O(n), where n = depth in the directory tree """
        path = PurePath(self.basename)
        parent = self.parent_dir
        while parent is not None:
            path = PurePath.joinpath(PurePath(parent.basename), path)
            parent = parent.parent_dir
        
        return path

class Directory():
    def __init__(self, path):
        """ Initialize a Directory object with a root path """
        if not os.path.isdir(path):
            raise Exception(path + " is not a directory")
        self.root_path = os.path.abspath(path)
        
        # Set up the data structures
        self.file_list = []
        self.directory_map = {}
        self.directory_map_file = {}
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
                    
                    # A negative file size tells the renderer to ignore it
                    dirfile = File(path=os.path.join(path_shortened, subdir),
                                   size=-1,
                                   modified=mdate,
                                   isdir=True)
                    
                    # Add to data structures
                    file_index = len(self.file_list)
                    self.file_list.append(dirfile)
                    self.directory_map[path_shortened].append(file_index)
                    
                    this_rel_path = os.path.relpath(os.path.join(path_shortened, subdir), start=".")
                    self.directory_map_file[this_rel_path] = dirfile
                    
                    # Increment number of files left to match for the parent directory
                    if path_shortened in self.directory_map_file:
                        self.directory_map_file[path_shortened].to_match += 1
                        self.directory_map_file[path_shortened].to_match_total += 1
                    else:
                        print("Failed to find path_shortened for {}".format(path_shortened))
                except (FileNotFoundError, PermissionError):
                    pass
                
                if entries_done % 1000 == 0 and update_function is not None:
                    update_function(entries_done, entries_total, dirfile.path)
            
            # Add files
            for filename in files:
                try:
                    stat_info = os.stat(os.path.join(path, filename))
                    mdate = datetime.datetime.fromtimestamp(stat_info.st_mtime)
                    _file = File(path=os.path.join(path_shortened, filename),
                                 size=stat_info.st_size,
                                 modified=mdate,
                                 isdir=False)
                    
                    # Add to data structures
                    file_index = len(self.file_list)
                    self.file_list.append(_file)
                    self.directory_map[path_shortened].append(file_index)
                    self.filename_map[_file.basename] = file_index
                    if _file.size not in self.size_map:
                        self.size_map[_file.size] = []
                    self.size_map[_file.size].append(file_index)
                    
                    # Increment number of files left to match
                    if path_shortened in self.directory_map_file:
                        self.directory_map_file[path_shortened].to_match += 1
                        self.directory_map_file[path_shortened].to_match_total += 1
                    else:
                        print("Failed to find path_shortened for {}".format(path_shortened))
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
