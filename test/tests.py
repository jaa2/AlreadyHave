import unittest
import datetime

import os
import shutil
import pathlib
from pathlib import PurePath

from model.directory import Directory, File

def create_test_folder(self):
    """ Set up a hypothetical configuration """
    date = datetime.datetime.fromtimestamp(1600000000)
    self.root_file1 = File("./file1", 50, date, False)
    self.root_dir1 = File("./dir1", -1, date, True)
    self.root_dir2 = File("./dir2", -1, date, True)
    self.dir2_file1 = File("./dir2/file1", 100, date, False, self.root_dir2)
    self.dir2_dir = File("./dir2/dir", -1, date, True, self.root_dir2)
    self.dir2_dir_file = File("./dir2/dir/file", 200, date, False,
        self.dir2_dir)

class TestDirectory(unittest.TestCase):
    def setUp(self):
        create_test_folder(self)
        self.dir_ = Directory(".")
    
    def test_add_file_trivial(self):
        # Checks add_file to the root directory
        f = self.root_file1
        self.dir_.add_file(f)
        
        # Check that the file list contains this file
        self.assertEqual([f], self.dir_.file_list)
        
        # Check the size map for this file
        self.assertEqual([f], self.dir_.size_map[f.size])
    
    def test_add_file_multiple(self):
        # Checks for adding multiple files in multiple directories
        self.dir_.add_file(self.root_file1)
        self.dir_.add_file(self.root_dir1)
        self.dir_.add_file(self.root_dir2)
        self.dir_.add_file(self.dir2_file1)
        
        # File list is accurate
        self.assertEqual(set([self.root_file1, self.root_dir1, self.root_dir2,
            self.dir2_file1]),
            set(self.dir_.file_list))
        
        # Size map for both files, and not directories
        self.assertEqual([self.root_file1],
            self.dir_.size_map[self.root_file1.size])
        self.assertEqual([self.dir2_file1],
            self.dir_.size_map[self.dir2_file1.size])
        self.assertFalse(-1 in self.dir_.size_map)
        
        # Accurate matching
        self.assertEqual(self.root_dir1.to_match, 0)
        self.assertEqual(self.root_dir1.to_match_total, 0)
        
        self.assertEqual(self.root_dir2.to_match, 1)
        self.assertEqual(self.root_dir2.to_match_total, 1)
        
        # Directory map accurate
        self.assertEqual([self.dir2_file1],
            self.dir_.directory_map[PurePath("dir2")])

def make_small_file(path, size=100, char='a'):
    with open(str(path), "w") as f:
        f.write(char * size)

class TestDirectoryScan(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # Make the testing directory with some sample files
        self.test_path = PurePath("./test/testdir_1")
        # Delete testing directory, if it exists
        shutil.rmtree(self.test_path, ignore_errors=True)
        # Re-make it
        os.makedirs(str(self.test_path), exist_ok=True)
        
        """
        Directory tree (* indicates file):
        root_file1*
        root_file2*
        dir1
            dir1_file1*
            sub
                dir1_sub_file*
                dir1_sub_file2*
            sub2
        dir2
            dir
                dir
        """
        
        # Add testing directories and files
        make_small_file(self.test_path.joinpath("root_file1"), size=100)
        make_small_file(self.test_path.joinpath("root_file2"), size=100)
        
        dir1 = self.test_path.joinpath("dir1")
        os.makedirs(str(dir1))
        make_small_file(dir1.joinpath("dir1_file1"), size=50, char='b')
        
        dir1_sub = dir1.joinpath("sub")
        os.makedirs(str(dir1_sub))
        make_small_file(dir1_sub.joinpath("dir1_sub_file"), size=75)
        make_small_file(dir1_sub.joinpath("dir1_sub_file2"), size=100, char='c')
        
        dir1_sub2 = dir1.joinpath("sub2")
        os.makedirs(str(dir1_sub2))
        
        dir2 = self.test_path.joinpath("dir2")
        os.makedirs(str(dir2))
        
        dir2_e1 = dir2.joinpath("dir")
        os.makedirs(str(dir2_e1))
        dir2_e2 = dir2_e1.joinpath("dir")
        os.makedirs(str(dir2_e2))
        
        self.dir_ = Directory(str(self.test_path))
        # Scan!
        self.dir_.scan()
        
    def test_paths_exist(self):
        # Check that the scan paths are as expected
        self.assertEqual(PurePath(".") in self.dir_.directory_map, True)
        self.assertEqual(PurePath("dir1") in self.dir_.directory_map, True)
        self.assertEqual(PurePath("dir2/dir/dir") in self.dir_.directory_map, True)
    
    def test_size_map(self):
        # Find 100-byte files
        self.assertTrue(100 in self.dir_.size_map)
        size_files = self.dir_.size_map[100]
        self.assertEqual(len(size_files), 3)
        size_files_exp = set([PurePath("root_file1"), PurePath("root_file2"),
            PurePath("dir1/sub/dir1_sub_file2")])
        size_files_real = set([file_.get_path() for file_ in size_files])
        self.assertEqual(size_files_exp, size_files_real)
    
    def test_files_in_root(self):
        # Find files in root directory
        dir_files_exp = set([PurePath("dir1"), PurePath("dir2"),
            PurePath("root_file1"), PurePath("root_file2")])
        dir_files_real = set([file_.get_path() for file_ in
            self.dir_.directory_map[PurePath(".")]])
        self.assertEqual(dir_files_exp, dir_files_real)
    
    def test_files_in_subdir(self):
        # Find files in subdirectory
        dir_files_exp = set([PurePath("dir1/dir1_file1"), PurePath("dir1/sub"),
            PurePath("dir1/sub2")])
        dir_files_real = set([file_.get_path() for file_ in
            self.dir_.directory_map[PurePath("dir1")]])
        self.assertEqual(dir_files_exp, dir_files_real)
        
    def test_match_count_empty(self):
        # Test counts (to match)
        empty_dir = self.dir_.directory_map_file[PurePath("dir1/sub2")]
        self.assertEqual(empty_dir.to_match, 0)
        self.assertEqual(empty_dir.to_match_total, 0)
    
    def test_match_count_root(self):
        root_folder = self.dir_.directory_map_file[PurePath(".")]
        self.assertEqual(root_folder.to_match, 5)
        self.assertEqual(root_folder.to_match_total, 5)
    
    def test_match_count_multiple_empty(self):
        folder = self.dir_.directory_map_file[PurePath("dir2")]
        self.assertEqual(folder.to_match, 0)
        self.assertEqual(folder.to_match_total, 0)
    
    @classmethod
    def tearDownClass(self):
        # Delete testing directory
        shutil.rmtree(self.test_path, ignore_errors=True)

class TestFile(unittest.TestCase):
    def setUp(self):
        create_test_folder(self)
    
    def test_get_path_root_path_is_same(self):
        # Checks file.get_path() for dir2/file1
        self.assertEqual(self.dir2_file1.get_path(),
            PurePath.joinpath(PurePath("dir2"), PurePath("file1")))
    
    def test_get_path_trivial(self):
        # Checks file.get_path() for file1
        self.assertEqual(self.root_file1.get_path(),
            PurePath("file1"))
    
    def test_set_match_path(self):
        # Checks file.set_match on a file's parent
        self.dir2_file1.set_match(1, True)
        self.dir2_file1.set_match(-1, False)
        
        self.assertEqual(self.root_dir2.to_match, 0)
        self.assertEqual(self.root_dir2.to_match_total, 1)
    
    def test_set_match_multiple_parents(self):
        # Checks file.set_match on a file with multiple parents
        self.dir2_dir_file.set_match(1, True)
        
        self.assertEqual(self.dir2_dir.to_match, 1)
        self.assertEqual(self.dir2_dir.to_match_total, 1)
        
        self.assertEqual(self.root_dir2.to_match, 1)
        self.assertEqual(self.root_dir2.to_match_total, 1)
    
    def test_set_match_multiple_calls(self):
        self.dir2_dir_file.set_match(1, True)
        self.dir2_dir_file.set_match(-1, False)
        
        self.assertEqual(self.dir2_dir.to_match, 0)
        self.assertEqual(self.dir2_dir.to_match_total, 1)
        
        self.assertEqual(self.root_dir2.to_match, 0)
        self.assertEqual(self.root_dir2.to_match_total, 1)

if __name__ == "__main__":
    unittest.main()
