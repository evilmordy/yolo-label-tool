import os
import sys
import unittest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils.natural_sort import natural_sorted


class NaturalSortTests(unittest.TestCase):
    def test_numbers_inside_names(self):
        names = ["img10.png", "img2.png", "img1.png", "IMG100.PNG", "img02.png"]
        ordered = [path.name for path in natural_sorted(Path(name) for name in names)]
        self.assertEqual(
            ordered,
            ["img1.png", "img02.png", "img2.png", "img10.png", "IMG100.PNG"],
        )

    def test_casefold_text_and_plain_names(self):
        ordered = [path.name for path in natural_sorted([
            Path("b.png"),
            Path("A.png"),
            Path("a2.png"),
            Path("a10.png"),
        ])]
        self.assertEqual(ordered, ["a2.png", "a10.png", "A.png", "b.png"])


if __name__ == "__main__":
    unittest.main()
