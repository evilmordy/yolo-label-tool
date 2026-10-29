import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from appimage.linux_qt_libs import REQUIRED_SONAMES, qt_platform_binaries, want_bundled


class QtPlatformLibsTest(unittest.TestCase):
    def test_filter_keeps_xcb_util_and_skips_driver_libs(self):
        self.assertTrue(want_bundled("libxcb-icccm.so.4"))
        self.assertTrue(want_bundled("libxkbcommon-x11.so.0"))
        self.assertFalse(want_bundled("libxcb.so.1"))
        self.assertFalse(want_bundled("libxcb-dri3.so.0"))
        self.assertFalse(want_bundled("libGL.so.1"))
        self.assertFalse(want_bundled("libX11.so.6"))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Qt xcb plugins are Linux-only")
    def test_collects_required_sonames_when_pyqt_is_installed(self):
        try:
            import PyQt5  # noqa: F401
        except ImportError:
            self.skipTest("PyQt5 is not installed")
        binaries = qt_platform_binaries()
        names = {os.path.basename(src) for src, _dest in binaries}
        self.assertTrue(all(dest == "." for _src, dest in binaries))
        for soname in REQUIRED_SONAMES:
            self.assertIn(soname, names)
        self.assertNotIn("libxcb.so.1", names)
        self.assertFalse(any(name.startswith("libxcb-dri") for name in names))


if __name__ == "__main__":
    unittest.main()
