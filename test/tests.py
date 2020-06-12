import unittest
import datetime

import pathlib
from pathlib import PurePath

from model.directory import Directory, File

class TestDirectory(unittest.TestCase):
    pass

class TestFile(unittest.TestCase):
    def setUp(self):
        """ Set up a hypothetical configuration """
        date = datetime.datetime.fromtimestamp(1600000000)
        self.root_file1 = File("./file1", 50, date, False)
        self.root_dir1 = File("./dir1", -1, date, True)
        self.root_dir2 = File("./dir2", -1, date, True)
        self.dir2_file1 = File("./dir2/file1", 100, date, False, self.root_dir2)
        self.dir2_dir = File("./dir2/dir", -1, date, True, self.root_dir2)
        self.dir2_dir_file = File("./dir2/dir/file", 200, date, False,
            self.dir2_dir)
    
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
        
    
    # TODO: Test for set_match when there is no parent
    # TODO: Test for set_match when there is one parent
    #   * Check for differences in to_match and to_match_total when
    #       affect_total is changed

if __name__ == "__main__":
    unittest.main()
