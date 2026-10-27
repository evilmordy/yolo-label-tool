"""Navigation auto-save must not create txt files for untouched images."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from core.settings_manager import ShortcutKey
from core.yolo_io import (
    STATUS_BACKGROUND,
    STATUS_LABELED,
    STATUS_UNLABELED,
    annotation_signature,
    read_label_file_status,
)
from core.bbox import BBox
from i18n.locales import en, ja, zh
from i18n.translator import tr
from ui.bbox_item import BBoxItem
from ui.main_window import MainWindow


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _write_png(path: Path, color=Qt.red):
    image = QImage(16, 12, QImage.Format_RGB32)
    image.fill(color)
    if not image.save(str(path)):
        raise RuntimeError(f"failed to write {path}")


class LabelStatusTests(unittest.TestCase):
    def test_file_status_and_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            missing = folder / "missing.txt"
            empty = folder / "empty.txt"
            empty.write_text("", encoding="utf-8")
            labeled = folder / "labeled.txt"
            labeled.write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
            self.assertEqual(read_label_file_status(missing), STATUS_UNLABELED)
            self.assertEqual(read_label_file_status(empty), STATUS_BACKGROUND)
            self.assertEqual(read_label_file_status(labeled), STATUS_LABELED)

        base = [BBox(0, 1, type="rect", x_center=0.5, y_center=0.5, width=0.2, height=0.2)]
        same = [BBox(9, 1, type="rect", x_center=0.5, y_center=0.5, width=0.2, height=0.2)]
        changed = [BBox(0, 2, type="rect", x_center=0.5, y_center=0.5, width=0.2, height=0.2)]
        self.assertEqual(annotation_signature(base), annotation_signature(same))
        self.assertNotEqual(annotation_signature(base), annotation_signature(changed))
        self.assertNotEqual(annotation_signature(base), annotation_signature([]))

    def test_locales_include_background_strings(self):
        keys = [
            "menu.mark_background",
            "btn.mark_background",
            "list.background",
            "list.tip_background",
            "toast.marked_background",
            "settings.shortcut_mark_background",
        ]
        for strings in (zh.STRINGS, en.STRINGS, ja.STRINGS):
            for key in keys:
                self.assertIn(key, strings)
                self.assertTrue(strings[key].strip())


class NavSaveTests(unittest.TestCase):
    def setUp(self):
        self.app = _app()
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.images = self.folder / "images"
        self.labels = self.folder / "labels"
        self.images.mkdir()
        self.labels.mkdir()
        self.window = MainWindow()
        self.window._app_settings.auto_save_on_nav = True
        self.window.save_folder_path = self.labels

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def _png(self, name, color=Qt.red):
        path = self.images / name
        _write_png(path, color)
        return path

    def _open(self, paths, index=0):
        self.window.image_list = list(paths)
        self.window.current_image_index = index
        self.window.current_folder_path = self.images
        self.window._refresh_image_list()
        self.window._load_image(self.window.image_list[index])
        self.window._update_nav_label()

    def _txt(self, image_path: Path) -> Path:
        return self.labels / image_path.with_suffix(".txt").name

    def test_browsing_does_not_create_txt(self):
        first = self._png("a.png", Qt.red)
        second = self._png("b.png", Qt.blue)
        self._open([first, second])
        self.window.show_next_image()
        self.window.show_next_image()
        self.assertFalse(self._txt(first).exists())
        self.assertFalse(self._txt(second).exists())

    def test_browsing_does_not_rewrite_existing_txt(self):
        first = self._png("a.png")
        second = self._png("b.png")
        raw = "0  0.10 0.20 0.30 0.40\nnot-a-label\n"
        txt = self._txt(first)
        txt.write_text(raw, encoding="utf-8")
        self._open([first, second])
        self.window.show_next_image()
        self.assertEqual(txt.read_text(encoding="utf-8"), raw)
        self.assertFalse(self._txt(second).exists())

    def test_deleting_all_boxes_writes_empty_txt(self):
        first = self._png("a.png")
        second = self._png("b.png")
        txt = self._txt(first)
        txt.write_text("0 0.500000 0.500000 0.200000 0.200000\n", encoding="utf-8")
        self._open([first, second])
        self.assertEqual(len(self.window.label_manager.bboxes), 1)
        self.window._select_bbox_by_id(self.window.label_manager.bboxes[0].id)
        self.window.delete_bbox()
        self.assertEqual(self.window.label_manager.bboxes, [])
        self.window.show_next_image()
        self.assertTrue(txt.is_file())
        self.assertEqual(txt.read_text(encoding="utf-8"), "")
        self.assertEqual(
            self.window.image_list_widget.item(0).text(),
            tr("list.background", name=first.name),
        )

    def test_add_then_undo_does_not_create_background_file(self):
        first = self._png("a.png")
        second = self._png("b.png")
        self._open([first, second])
        self.window.add_bbox()
        self.assertEqual(len(self.window.label_manager.bboxes), 1)
        self.window._undo()
        self.assertEqual(self.window.label_manager.bboxes, [])
        self.window.show_next_image()
        self.assertFalse(self._txt(first).exists())

    def test_mark_background_writes_empty_txt_and_list_state(self):
        labeled = self._png("labeled.png", Qt.red)
        background = self._png("background.png", Qt.green)
        unlabeled = self._png("unlabeled.png", Qt.blue)
        labeled_txt = self._txt(labeled)
        labeled_txt.write_text("1 0.500000 0.500000 0.100000 0.100000\n", encoding="utf-8")
        background_txt = self._txt(background)
        background_txt.write_text("", encoding="utf-8")
        self._open([labeled, background, unlabeled], index=2)
        colors = [
            self.window.image_list_widget.item(i).foreground().color().name()
            for i in range(3)
        ]
        self.assertEqual(len(set(colors)), 3)
        self.window.mark_as_background()
        unmarked = self._txt(unlabeled)
        self.assertTrue(unmarked.is_file())
        self.assertEqual(unmarked.stat().st_size, 0)
        self.assertEqual(
            self.window.image_list_widget.item(2).text(),
            tr("list.background", name=unlabeled.name),
        )
        self.assertEqual(
            self.window.image_list_widget.item(0).text(),
            tr("list.labeled", name=labeled.name),
        )
        self.assertEqual(
            self.window.image_list_widget.item(1).text(),
            tr("list.background", name=background.name),
        )
        self.assertEqual(
            self.window.image_list_widget.item(0).toolTip(),
            tr("list.tip_labeled"),
        )
        self.assertEqual(
            self.window.image_list_widget.item(2).toolTip(),
            tr("list.tip_background"),
        )

    def test_mark_background_clears_boxes_and_undo_restores_on_nav(self):
        first = self._png("a.png")
        second = self._png("b.png")
        txt = self._txt(first)
        txt.write_text("0 0.500000 0.500000 0.200000 0.100000\n", encoding="utf-8")
        self._open([first, second])
        self.window.mark_as_background()
        self.assertEqual(txt.read_text(encoding="utf-8"), "")
        self.assertEqual(self.window.label_manager.bboxes, [])
        self.window._undo()
        self.assertEqual(len(self.window.label_manager.bboxes), 1)
        self.window.show_next_image()
        body = txt.read_text(encoding="utf-8").strip()
        self.assertTrue(body.startswith("0 "))
        self.assertNotEqual(body, "")

    def test_save_all_writes_only_unsaved_image(self):
        current = self._png("current.png")
        other = self._png("other.png")
        untouched = "0 0.123456789 0.2 0.3 0.4 extra\nnot a label\n"
        other_txt = self._txt(other)
        other_txt.write_text(untouched, encoding="utf-8")
        self._open([current, other])
        before = other_txt.read_bytes()
        self.window.save_all_in_folder(show_toast=True)
        self.assertEqual(other_txt.read_bytes(), before)
        self.assertFalse(self._txt(current).exists())

        self.window.add_bbox()
        self.window.save_all_in_folder(show_toast=True)
        self.assertTrue(self._txt(current).is_file())
        self.assertGreater(self._txt(current).stat().st_size, 0)
        self.assertEqual(other_txt.read_bytes(), before)

        rewritten = other_txt.read_bytes()
        self.window.save_all_in_folder(show_toast=True)
        self.assertEqual(other_txt.read_bytes(), rewritten)
        current_bytes = self._txt(current).read_bytes()
        self.window.save_all_in_folder(show_toast=True)
        self.assertEqual(self._txt(current).read_bytes(), current_bytes)

    def test_load_image_does_not_rebuild_the_scene_twice(self):
        image = self._png("box.png")
        txt = self._txt(image)
        txt.write_text("0 0.500000 0.500000 0.250000 0.250000\n", encoding="utf-8")
        clears = {"n": 0}
        fits = {"n": 0}
        scene = self.window.image_view.scene
        original_clear = scene.clear
        original_fit = self.window.image_view.fit_to_view

        def wrapped_clear():
            clears["n"] += 1
            return original_clear()

        def wrapped_fit():
            fits["n"] += 1
            return original_fit()

        scene.clear = wrapped_clear
        self.window.image_view.fit_to_view = wrapped_fit
        try:
            self._open([image])
        finally:
            scene.clear = original_clear
            self.window.image_view.fit_to_view = original_fit

        self.assertEqual(clears["n"], 1)
        self.assertGreaterEqual(fits["n"], 1)
        pixmaps = [
            item for item in scene.items()
            if type(item).__name__ == "QGraphicsPixmapItem"
        ]
        boxes = [item for item in scene.items() if isinstance(item, BBoxItem)]
        self.assertEqual(len(pixmaps), 1)
        self.assertEqual(len(boxes), 1)
        self.assertEqual(pixmaps[0].zValue(), -1)
        self.assertEqual(
            self.window.image_view.sceneRect().width(),
            pixmaps[0].pixmap().width(),
        )
        self.assertAlmostEqual(self.window.label_manager.bboxes[0].width, 0.25)
        self.assertAlmostEqual(self.window.label_manager.bboxes[0].height, 0.25)
        self.assertGreater(self.window.image_view.zoom_level, 0)
        self.window.fit_image_to_view()
        self.assertEqual(
            len([
                item for item in scene.items()
                if type(item).__name__ == "QGraphicsPixmapItem"
            ]),
            1,
        )
        self.assertAlmostEqual(self.window.label_manager.bboxes[0].width, 0.25)

    def test_label_status_cache_skips_repeat_stats(self):
        labeled = self._png("labeled.png")
        background = self._png("background.png")
        unlabeled = self._png("plain.png")
        self._txt(labeled).write_text("0 0.500000 0.500000 0.200000 0.200000\n", encoding="utf-8")
        self._txt(background).write_text("", encoding="utf-8")
        with patch(
            "ui.main_window.read_label_file_status",
            wraps=read_label_file_status,
        ) as mocked:
            self._open([labeled, background, unlabeled])
            warmed = mocked.call_count
            self.assertGreaterEqual(warmed, 3)
            self.window._refresh_image_list()
            self.window.retranslate_ui()
            self.assertEqual(mocked.call_count, warmed)
            self.window.mark_as_background()
            self._txt(labeled).unlink()
            self.assertEqual(self.window._file_label_status(labeled), STATUS_BACKGROUND)
            self.assertEqual(mocked.call_count, warmed)

    def test_open_folder_saves_previous_list_and_uses_natural_order(self):
        old_a = self._png("old_a.png", Qt.red)
        old_b = self._png("old_b.png", Qt.blue)
        self._open([old_a, old_b], index=1)
        self.window.add_bbox()

        new_folder = self.folder / "new_images"
        empty = self.folder / "empty_images"
        new_folder.mkdir()
        empty.mkdir()
        for name, color in (
            ("img10.png", Qt.red),
            ("img2.png", Qt.blue),
            ("img1.png", Qt.green),
        ):
            _write_png(new_folder / name, color)

        with patch("ui.main_window.QMessageBox.warning"):
            self.window._open_folder_path(empty)
        self.assertEqual(
            [path.name for path in self.window.image_list],
            ["old_a.png", "old_b.png"],
        )
        self.assertEqual(self.window.current_image_path, old_b)
        self.assertFalse(self._txt(old_b).exists())

        logged = []
        original = self.window._refresh_image_list_item

        def spy(index):
            if 0 <= index < len(self.window.image_list):
                logged.append(self.window.image_list[index].name)
            return original(index)

        self.window._refresh_image_list_item = spy
        self.window._open_folder_path(new_folder)
        self.assertEqual(logged[0], "old_b.png")
        self.assertEqual(
            [path.name for path in self.window.image_list],
            ["img1.png", "img2.png", "img10.png"],
        )
        self.assertGreater(self._txt(old_b).stat().st_size, 0)
        self.assertEqual(self.window.image_list_widget.count(), 3)
        self.assertTrue(self.window.image_list_widget.item(0).text().endswith("img1.png"))

    def test_shortcut_marks_background(self):
        image = self._png("a.png")
        self._open([image])
        self.window._shortcut_actions[ShortcutKey.MARK_BACKGROUND].trigger()
        txt = self._txt(image)
        self.assertTrue(txt.is_file())
        self.assertEqual(txt.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
