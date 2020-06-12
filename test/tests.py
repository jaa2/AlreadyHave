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
        self.root_file1 = File("./file1",
            50,
            datetime.datetime.fromtimestamp(1600000000),
            False)
        
        self.root_dir1 = File("./dir1",
            -1,
            datetime.datetime.fromtimestamp(1600000000),
            True)
        
        self.root_dir2 = File("./dir2",
            -1,
            datetime.datetime.fromtimestamp(1600000000),
            True)
        
        self.dir2_file1 = File("./dir2/file1",
            100,
            datetime.datetime.fromtimestamp(1600000000),
            False,
            self.root_dir2)
    
    def test_get_path_root_path_is_same(self):
        self.assertEqual(self.dir2_file1.get_path(),
            PurePath.joinpath(PurePath("dir2"), PurePath("file1")))
    
    def test_get_path_trivial(self):
        self.assertEqual(self.root_file1.get_path(),
            PurePath("file1"))

if __name__ == "__main__":
    unittest.main()
