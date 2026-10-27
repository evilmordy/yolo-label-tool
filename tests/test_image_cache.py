"""Background prefetch must not crash on fast navigation or folder changes."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt5.QtCore import Qt, QEventLoop, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QApplication

from ui.main_window import MainWindow
from utils.image_loader import ImageCache, load_image, neighbor_paths


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _write_png(path: Path, color):
    image = QImage(32, 24, QImage.Format_RGB32)
    image.fill(color)
    if not image.save(str(path)):
        raise RuntimeError(f"failed to write {path}")


def _wait_until(predicate, timeout_ms=3000):
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(20)

    def check():
        if predicate():
            loop.quit()

    timer.timeout.connect(check)
    QTimer.singleShot(timeout_ms, loop.quit)
    timer.start()
    loop.exec_()
    timer.stop()
    return bool(predicate())


class NeighborPathTests(unittest.TestCase):
    def test_order_prefers_travel_direction_and_dedupes(self):
        names = [f"img{i}.png" for i in range(6)]
        self.assertEqual(
            neighbor_paths(names, 0, radius=2, direction=1),
            ["img1.png", "img5.png", "img2.png", "img4.png"],
        )
        self.assertEqual(
            neighbor_paths(names, 0, radius=2, direction=-1),
            ["img5.png", "img1.png", "img4.png", "img2.png"],
        )
        self.assertEqual(
            neighbor_paths(names[:2], 0, radius=2, direction=1),
            ["img1.png"],
        )
        self.assertEqual(neighbor_paths(names[:1], 0), [])


class ImageCacheTests(unittest.TestCase):
    def setUp(self):
        self.app = _app()
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.cache = ImageCache(capacity=3)

    def tearDown(self):
        self.cache.shutdown()
        self.app.processEvents()
        self.tmp.cleanup()

    def _png(self, name, color):
        path = self.folder / name
        _write_png(path, color)
        return path

    def test_prefetch_matches_direct_pixmap_and_load_image_hits_cache(self):
        path = self._png("a.png", Qt.red)
        direct = QPixmap(str(path))
        self.cache.prefetch([path])
        self.assertTrue(_wait_until(lambda: self.cache.pixmap(path) is not None))
        cached = self.cache.pixmap(path)
        self.assertEqual(cached.width(), direct.width())
        self.assertEqual(cached.height(), direct.height())
        self.assertEqual(cached.devicePixelRatio(), direct.devicePixelRatio())

        marker = QPixmap(9, 9)
        marker.fill(Qt.blue)
        self.cache.insert(path, marker)
        loaded = load_image(path, self.cache)
        self.assertEqual(loaded.cacheKey(), marker.cacheKey())
        self.assertEqual(loaded.width(), 9)

    def test_invalidate_drops_cache_and_stale_decodes(self):
        path = self._png("a.png", Qt.green)
        self.cache.prefetch([path])
        self.assertTrue(_wait_until(lambda: self.cache.pixmap(path) is not None))
        stale_generation = self.cache._generation
        self.cache.invalidate()
        self.assertIsNone(self.cache.pixmap(path))
        image = QImage(str(path))
        self.cache._on_image_ready(stale_generation, str(path), image)
        self.app.processEvents()
        self.assertIsNone(self.cache.pixmap(path))

        self.cache.prefetch([path])
        self.assertTrue(_wait_until(lambda: self.cache.pixmap(path) is not None))

    def test_missing_file_and_shutdown_are_safe(self):
        missing = self.folder / "missing.png"
        self.cache.prefetch([missing, self._png("b.png", Qt.yellow)])
        self.app.processEvents()
        self.assertTrue(_wait_until(lambda: self.cache.pixmap(self.folder / "b.png") is not None))
        self.assertIsNone(self.cache.pixmap(missing))
        self.cache.prefetch([missing])
        self.cache.invalidate()
        self.cache.shutdown()
        self.cache.shutdown()
        self.app.processEvents()

    def test_lru_evicts_oldest(self):
        paths = [self._png(f"{i}.png", Qt.red) for i in range(4)]
        for path in paths:
            pix = QPixmap(4, 4)
            pix.fill(Qt.red)
            self.cache.insert(path, pix)
        self.assertIsNone(self.cache.pixmap(paths[0]))
        self.assertIsNotNone(self.cache.pixmap(paths[-1]))
        self.assertEqual(len(self.cache._items), 3)


class FastNavigationTests(unittest.TestCase):
    def setUp(self):
        self.app = _app()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.images = root / "images"
        self.labels = root / "labels"
        self.images.mkdir()
        self.labels.mkdir()
        self.window = MainWindow()
        self.window.save_folder_path = self.labels
        self.window._app_settings.auto_save_on_nav = True

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def test_fast_next_and_folder_switch_do_not_crash(self):
        paths = []
        for i, color in enumerate((Qt.red, Qt.green, Qt.blue, Qt.yellow, Qt.cyan, Qt.magenta)):
            path = self.images / f"img{i}.png"
            _write_png(path, color)
            paths.append(path)
        self.window.image_list = list(paths)
        self.window.current_image_index = 0
        self.window._refresh_image_list()
        self.window._load_image(paths[0])
        for _ in range(12):
            self.window.show_next_image()
            self.window.show_prev_image()
        self.window._image_cache.invalidate()
        self.window.image_list = list(reversed(paths))
        self.window.current_image_index = 0
        self.window._nav_direction = -1
        self.window._load_image(self.window.image_list[0])
        for _ in range(8):
            self.window.show_next_image()
        self.app.processEvents()
        current = self.window.current_image_path
        self.assertEqual(
            self.window.image_view.scene.itemsBoundingRect().width(),
            QPixmap(str(current)).width(),
        )
        self.assertGreater(len(self.window._image_cache._items), 0)


if __name__ == "__main__":
    unittest.main()
