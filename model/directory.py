"""Includes the necessary classes for storing information about files and
    directories."""

import os
import datetime
import hashlib

from pathlib import PurePath

class File():
    def __init__(self, path, size, modified, isdir, parent=None):
        self.path = path
        self.basename = os.path.basename(path)
        # TODO: Make this constructor calculate some of these parameters
        self.size = size
        self.modified = modified
        self.isdir = isdir
        self.hash_1k = None
        self.hash_full = None
        self.matched = False
        
        # For a directory, the number of files (not necessarily subdirectories)
        # left to match
        self.to_match = 0
        self.to_match_total = 0
        
        self.parent_dir = parent
    
    def get_path(self):
        """ Returns a complete PurePath of this object.
            Runtime: O(d), where d = depth in the directory tree """
        path = PurePath(self.basename)
        parent = self.parent_dir
        while parent is not None:
            path = PurePath.joinpath(PurePath(parent.basename), path)
            parent = parent.parent_dir
        
        return path
    
    def set_match(self, amount, affect_total=False):
        """ Changes the match amount of a file's parent directories. """
        parent = self.parent_dir
        while parent is not None:
            parent.to_match += amount
            if affect_total:
                parent.to_match_total += amount
            parent = parent.parent_dir
    
    def find_hash_1k(self, root_dir):
        """ Finds a hash using the first 1KiB of data in the file """
        if self.hash_1k is not None:
            return self.hash_1k
        
        try:
            with open(root_dir.joinpath(self.get_path()), "rb") as f:
                first_kib = f.read(1024)
                
                # Hash it
                h = hashlib.sha256()
                h.update(first_kib)
                self.hash_1k = h.digest()
        except (FileNotFoundError, PermissionError):
            # TODO: Find a better way to solve this
            return None
        
        return self.hash_1k
    
    def find_hash_full(self, root_dir):
        """ Finds the complete hash of a file """
        if self.size <= 1024:
            # Skip reading the file again if we already have the full hash
            self.hash_full = self.find_hash_1k(root_dir)
            return self.hash_full
        
        # TODO: Error handling
        try:
            with open(root_dir.joinpath(self.get_path()), "rb") as f:
                # Read the file in chunks to keep memory usage low
                buffer_size = 2 ** 16
                h = hashlib.sha256()
                
                while True:
                    data = f.read(buffer_size)
                    if not data:
                        break
                    h.update(data)
                
                self.hash_full = h.digest()
        
        except (FileNotFoundError, PermissionError):
            # TODO: Find a better way to solve this
            return None
            
        return self.hash_full
    
    @staticmethod
    def equals(file1, file1_root_dir, file2, file2_root_dir):
        """ Compares two files to see if they are equal """
        if file1.size != file2.size:
            return False
        
        if (file1.find_hash_1k(file1_root_dir) !=
            file2.find_hash_1k(file2_root_dir)):
            return False
        
        return (file1.find_hash_full(file1_root_dir) ==
            file2.find_hash_full(file2_root_dir))

class Directory():
    """ A class representing all the files in a directory and all its
        subdirectories.
        Main goals of this class:
        * Be able to store files
        * Be able to list files by directory
        * Be able to look up files by size """
    def __init__(self, path):
        """ Initialize a Directory object with a root path """
        self.root_path = PurePath(path)
        
        # Set up the data structures
        self.file_list = []
        self.directory_map = {}
        self.directory_map_file = {}
        self.filename_map = {}
        self.size_map = {}
    
    def add_file(self, file_):
        """ Adds a file to the directory structure """
        self.file_list.append(file_)
        
        if file_.isdir:
            # Create directory mapping
            self.directory_map_file[file_.get_path()] = file_
            self.directory_map[file_.get_path()] = []
        else:
            # Add to size map
            if file_.size not in self.size_map:
                self.size_map[file_.size] = []
            self.size_map[file_.size].append(file_)
        
            # Increment the number of matches required for all parent directories
            file_.set_match(1, True)
            
            # TODO: Add to filename map, if necessary
        
        # Add to parent directory's directory_map entry
        if file_.parent_dir is not None:
            self.directory_map[file_.parent_dir.get_path()].append(file_)
    
    def scan(self, update_function=None, finish_function=None):
        """ Scan the directory and all subdirectories for files and folders,
            periodically sending updates with update_function """
        # Files and folders left to read (initialized to 1 to read the root
        # directory)
        entries_total = 1
        # Files and folders read so far
        entries_done = 0
        
        # Add root folder
        root_stat_info = os.stat(self.root_path)
        root_folder = File(path=".",
            size=-1,
            modified=datetime.datetime.fromtimestamp(root_stat_info.st_mtime),
            isdir=True,
            parent=None)
        self.add_file(root_folder)
        
        for path, subdirs, files in os.walk(self.root_path):
            entries_done += 1
            entries_total += len(subdirs) + len(files)
            
            this_parent_dir = self.directory_map_file[PurePath(path).relative_to(self.root_path)]
            
            # Add subdirectories
            for subdir in subdirs:
                try:
                    stat_info = os.stat(os.path.join(path, subdir))
                    mdate = datetime.datetime.fromtimestamp(stat_info.st_mtime)
                    
                    # A negative file size tells the renderer to ignore it
                    dirfile = File(path=os.path.join(path, subdir),
                                   size=-1,
                                   modified=mdate,
                                   isdir=True,
                                   parent=this_parent_dir)
                    self.add_file(dirfile)
                except (FileNotFoundError, PermissionError):
                    pass
                
                if entries_done % 100 == 0 and update_function is not None:
                    update_function(entries_done, entries_total, dirfile.path)
            
            # Add files
            for filename in files:
                try:
                    stat_info = os.stat(os.path.join(path, filename))
                    mdate = datetime.datetime.fromtimestamp(stat_info.st_mtime)
                    _file = File(path=os.path.join(path, filename),
                                 size=stat_info.st_size,
                                 modified=mdate,
                                 isdir=False,
                                 parent=this_parent_dir)
                    self.add_file(_file)
                except (FileNotFoundError, PermissionError):
                    pass
                
                entries_done += 1
                
                if entries_done % 100 == 0 and update_function is not None:
                    update_function(entries_done, entries_total, _file.path)
            
            # Reset some of these
            entries_done -= len(files) + 1
            entries_total -= len(files) + 1
        
        if update_function is not None:
            update_function(1, 1, None)
        
        if finish_function is not None:
            finish_function()
