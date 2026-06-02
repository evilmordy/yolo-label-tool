from PyQt5.QtWidgets import (
    QMainWindow, QFileDialog, QListWidget, QMessageBox,
    QAction, QDockWidget, QPushButton, QWidget, QActionGroup,
    QVBoxLayout, QHBoxLayout, QListWidgetItem, QSpinBox, QLabel, QDialog, QRadioButton, QButtonGroup, QFrame
)
from PyQt5.QtCore import QRectF, pyqtSignal, Qt, QTimer, QPointF
from PyQt5.QtGui import QFont, QKeySequence
from pathlib import Path
import math

from ui.image_view import ImageView
from ui.bbox_item import BBoxItem
from ui.obb_item import OBBItem
from ui.polygon_item import PolygonItem
from ui.polygon_draw_controller import PolygonDrawController
from ui.settings_dialog import SettingsDialog
from core.label_manager import LabelManager
from core.bbox import BBox
from core.yolo_io import load_yolo_txt, save_yolo_txt
from core.settings_manager import (
    load_all, ShortcutKey, get_shortcut, key_event_matches,
    load_path_prefs, save_path_pref,
    KEY_SAVE_FOLDER, KEY_LAST_IMAGE_DIR, KEY_LAST_FOLDER,
)
from core.undo_stack import UndoStack
from core.bbox_clone import clone_bboxes
from ui.graphics_utils import pick_preferred_bbox_root, resolve_bbox_root
from utils.image_loader import load_image
from ui.theme_manager import apply_theme, get_theme_ids, get_theme_name, get_current_theme_id
from i18n.translator import tr, set_language, on_language_changed
from PyQt5.QtWidgets import QApplication


class MainWindow(QMainWindow):

    item_selected = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._app_settings = load_all()
        self.setWindowTitle(tr("app.title"))

        self.image_view = ImageView()
        self.setCentralWidget(self.image_view)

        self.label_manager = LabelManager()
        self.current_image_path = None
        self.current_folder_path = None
        self.image_list = []
        self.current_image_index = 0
        self.save_folder_path = None
        self.bbox_items = {}
        self.theme_actions = {}
        self._shortcut_actions = {}
        self.polygon_draw_controller = PolygonDrawController()
        self._current_img_rect = QRectF(0, 0, 640, 480)

        self._periodic_save_timer = QTimer(self)
        self._periodic_save_timer.timeout.connect(self._on_periodic_save)

        self._ui_refs = {}
        self._syncing_selection = False
        self._undo_stack = UndoStack()
        self._image_dirty = False

        self._create_left_panel()
        self._create_right_panel()
        self._create_menu()
        self._setup_shortcuts()
        self._update_periodic_timer()

        self.image_view.set_draw_controller(self.polygon_draw_controller)
        self.polygon_draw_controller.finished.connect(self._on_polygon_draw_finished)
        self.polygon_draw_controller.cancelled.connect(self._on_polygon_draw_cancelled)
        self.image_view.bbox_selected.connect(self._on_scene_selection_changed)
        self.bbox_list.currentRowChanged.connect(self._on_bbox_list_row_changed)

        on_language_changed(self._on_language_changed)

        self._restore_path_prefs()

    def _restore_path_prefs(self):
        prefs = load_path_prefs()
        save_folder = prefs.get("save_folder")
        if save_folder:
            self.save_folder_path = Path(save_folder)
            self._update_save_path_label()

    def _dialog_start_dir(self, pref_key: str) -> str:
        prefs = load_path_prefs()
        pref_map = {
            KEY_LAST_IMAGE_DIR: "last_image_dir",
            KEY_LAST_FOLDER: "last_folder",
            KEY_SAVE_FOLDER: "save_folder",
        }
        pref_name = pref_map.get(pref_key)
        if pref_name:
            path = prefs.get(pref_name)
            if path:
                return path
        if self.save_folder_path and self.save_folder_path.is_dir():
            return str(self.save_folder_path)
        return ""

    def _on_language_changed(self, _lang):
        self.retranslate_ui()

    def _setup_shortcuts(self):
        self._shortcut_actions.clear()
        bindings = [
            (ShortcutKey.RECT, lambda: self.radio_rect.setChecked(True)),
            (ShortcutKey.OBB, lambda: self.radio_obb.setChecked(True)),
            (ShortcutKey.POLYGON, lambda: self.radio_polygon.setChecked(True)),
            (ShortcutKey.SAVE, lambda: self.save_txt(show_toast=True)),
            (ShortcutKey.UNDO, self._undo),
            (ShortcutKey.ADD, self._shortcut_add_bbox),
            (ShortcutKey.DELETE, self._shortcut_delete),
            (ShortcutKey.PREV_IMAGE, self._shortcut_prev_image),
            (ShortcutKey.NEXT_IMAGE, self._shortcut_next_image),
        ]
        for key, handler in bindings:
            action = QAction(self)
            seq = get_shortcut(self._app_settings, key)
            action.setShortcut(QKeySequence(seq))
            action.triggered.connect(handler)
            self.addAction(action)
            self._shortcut_actions[key] = action

    def _shortcut_add_bbox(self):
        if self.polygon_draw_controller.is_active():
            return
        self.add_bbox()

    def _shortcut_delete(self):
        if self.polygon_draw_controller.is_active():
            self.polygon_draw_controller.cancel()
            return
        self.delete_bbox()

    def _shortcut_prev_image(self):
        if self.polygon_draw_controller.is_active():
            return
        if self.image_list:
            self.show_prev_image()

    def _shortcut_next_image(self):
        if self.polygon_draw_controller.is_active():
            return
        if self.image_list:
            self.show_next_image()

    def _apply_shortcuts(self):
        for key, action in self._shortcut_actions.items():
            seq = get_shortcut(self._app_settings, key)
            action.setShortcut(QKeySequence(seq))

    def keyPressEvent(self, event):
        if self.polygon_draw_controller.is_active():
            if event.key() == Qt.Key_Backspace and not event.modifiers():
                if self.polygon_draw_controller.remove_last_point():
                    event.accept()
                    return
            if key_event_matches(
                event, get_shortcut(self._app_settings, ShortcutKey.POLYGON_FINISH)
            ):
                self.polygon_draw_controller.finish()
                event.accept()
                return
            if key_event_matches(
                event, get_shortcut(self._app_settings, ShortcutKey.POLYGON_CANCEL)
            ):
                self.polygon_draw_controller.cancel()
                event.accept()
                return
        super().keyPressEvent(event)

    def _create_left_panel(self):
        dock = QDockWidget(tr("dock.image_list"), self)
        dock.setMinimumWidth(240)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.image_list_widget = QListWidget()
        self.image_list_widget.currentRowChanged.connect(self.on_image_list_row_changed)
        layout.addWidget(self.image_list_widget)

        dock.setWidget(panel)
        self.addDockWidget(0x1, dock)
        self.left_dock = dock

    def _create_right_panel(self):
        dock = QDockWidget(tr("dock.annotation_list"), self)
        dock.setMinimumWidth(240)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.save_path_label = QLabel(tr("label.save_path_none"))
        self.save_path_label.setObjectName("secondaryLabel")
        self.save_path_label.setWordWrap(True)
        layout.addWidget(self.save_path_label)

        btn_set_save_path = QPushButton(tr("btn.set_save_path"))
        btn_set_save_path.clicked.connect(self.set_save_folder)
        layout.addWidget(btn_set_save_path)

        layout.addWidget(self._make_separator())

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        btn_prev = QPushButton(tr("btn.prev_image"))
        btn_next = QPushButton(tr("btn.next_image"))
        self.img_counter_label = QLabel("0/0")
        btn_prev.clicked.connect(self.show_prev_image)
        btn_next.clicked.connect(self.show_next_image)
        nav_layout.addWidget(btn_prev)
        nav_layout.addWidget(self.img_counter_label)
        nav_layout.addWidget(btn_next)
        layout.addLayout(nav_layout)

        zoom_layout = QHBoxLayout()
        btn_fit_view = QPushButton(tr("btn.fit_view"))
        btn_fit_view.clicked.connect(self.fit_image_to_view)
        zoom_layout.addWidget(btn_fit_view)
        layout.addLayout(zoom_layout)

        layout.addWidget(self._make_separator())

        self.bbox_list = QListWidget()
        self.bbox_list_label = QLabel(tr("label.bbox_list"))
        layout.addWidget(self.bbox_list_label)
        layout.addWidget(self.bbox_list)

        layout.addWidget(self._make_separator())

        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(4)
        self.mode_group = QButtonGroup(self)
        self.radio_rect = QRadioButton(tr("mode.rect"))
        self.radio_obb = QRadioButton(tr("mode.obb"))
        self.radio_polygon = QRadioButton(tr("mode.polygon"))
        self.radio_rect.setChecked(True)
        self.mode_group.addButton(self.radio_rect, 0)
        self.mode_group.addButton(self.radio_obb, 1)
        self.mode_group.addButton(self.radio_polygon, 2)
        mode_layout.addWidget(self.radio_rect)
        mode_layout.addWidget(self.radio_obb)
        mode_layout.addWidget(self.radio_polygon)
        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        layout.addLayout(mode_layout)

        bbox_btn_layout = QHBoxLayout()
        bbox_btn_layout.setSpacing(8)
        btn_add = QPushButton(tr("btn.add"))
        btn_del = QPushButton(tr("btn.delete"))
        btn_add.clicked.connect(self.add_bbox)
        btn_del.clicked.connect(self.delete_bbox)
        bbox_btn_layout.addWidget(btn_add)
        bbox_btn_layout.addWidget(btn_del)
        layout.addLayout(bbox_btn_layout)

        class_layout = QHBoxLayout()
        self.class_id_label = QLabel(tr("label.class_id"))
        class_layout.addWidget(self.class_id_label)
        self.class_id_spinbox = QSpinBox()
        self.class_id_spinbox.setMinimum(0)
        self.class_id_spinbox.setMaximum(999)
        self.class_id_spinbox.valueChanged.connect(self.on_class_id_changed)
        class_layout.addWidget(self.class_id_spinbox)
        layout.addLayout(class_layout)

        layout.addWidget(self._make_separator())

        btn_save = QPushButton(tr("btn.save_yolo"))
        btn_save.setObjectName("btnSave")
        btn_save.clicked.connect(lambda: self.save_txt(show_toast=True))
        layout.addWidget(btn_save)

        layout.addStretch()

        dock.setWidget(panel)
        self.addDockWidget(0x2, dock)
        self.right_dock = dock

        self._ui_refs = {
            "btn_set_save_path": btn_set_save_path,
            "btn_prev": btn_prev,
            "btn_next": btn_next,
            "btn_fit_view": btn_fit_view,
            "btn_add": btn_add,
            "btn_del": btn_del,
            "btn_save": btn_save,
        }

    def _make_separator(self):
        line = QFrame()
        line.setObjectName("panelSeparator")
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        return line

    def _create_menu(self):
        menu = self.menuBar()

        self.file_menu = menu.addMenu(tr("menu.file"))

        self.action_open_img = QAction(tr("menu.open_image"), self)
        self.action_open_img.triggered.connect(self.open_image)
        self.file_menu.addAction(self.action_open_img)

        self.action_open_folder = QAction(tr("menu.open_folder"), self)
        self.action_open_folder.triggered.connect(self.open_folder)
        self.file_menu.addAction(self.action_open_folder)

        self.theme_menu = menu.addMenu(tr("menu.theme"))
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        current_theme = get_current_theme_id()

        for theme_id in get_theme_ids():
            action = QAction(get_theme_name(theme_id), self)
            action.setCheckable(True)
            action.setChecked(theme_id == current_theme)
            action.triggered.connect(lambda checked, tid=theme_id: self._apply_theme(tid))
            theme_group.addAction(action)
            self.theme_menu.addAction(action)
            self.theme_actions[theme_id] = action

        self.action_settings = QAction(tr("menu.settings"), self)
        self.action_settings.triggered.connect(self._open_settings_dialog)
        menu.addAction(self.action_settings)

    def _open_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.settings_changed.connect(self._apply_settings)
        dlg.exec_()

    def _apply_settings(self, settings):
        lang_changed = settings.language != self._app_settings.language
        self._app_settings = settings
        if lang_changed:
            set_language(settings.language)
        else:
            self.retranslate_ui()
        self._apply_shortcuts()
        self._update_periodic_timer()

    def _update_periodic_timer(self):
        if self._app_settings.periodic_auto_save:
            ms = self._app_settings.periodic_interval_min * 60 * 1000
            self._periodic_save_timer.start(ms)
        else:
            self._periodic_save_timer.stop()

    def _on_periodic_save(self):
        self.save_all_in_folder(show_toast=True)

    def retranslate_ui(self):
        self.setWindowTitle(tr("app.title"))
        self.left_dock.setWindowTitle(tr("dock.image_list"))
        self.right_dock.setWindowTitle(tr("dock.annotation_list"))
        self._update_save_path_label()
        self.file_menu.setTitle(tr("menu.file"))
        self.action_open_img.setText(tr("menu.open_image"))
        self.action_open_folder.setText(tr("menu.open_folder"))
        self.theme_menu.setTitle(tr("menu.theme"))
        for theme_id, action in self.theme_actions.items():
            action.setText(get_theme_name(theme_id))
        self.action_settings.setText(tr("menu.settings"))
        self._ui_refs["btn_set_save_path"].setText(tr("btn.set_save_path"))
        self._ui_refs["btn_prev"].setText(tr("btn.prev_image"))
        self._ui_refs["btn_next"].setText(tr("btn.next_image"))
        self._ui_refs["btn_fit_view"].setText(tr("btn.fit_view"))
        self._ui_refs["btn_add"].setText(tr("btn.add"))
        self._ui_refs["btn_del"].setText(tr("btn.delete"))
        self._ui_refs["btn_save"].setText(tr("btn.save_yolo"))
        self.bbox_list_label.setText(tr("label.bbox_list"))
        self.radio_rect.setText(tr("mode.rect"))
        self.radio_obb.setText(tr("mode.obb"))
        self.radio_polygon.setText(tr("mode.polygon"))
        self.class_id_label.setText(tr("label.class_id"))
        if self.image_list:
            self._refresh_image_list()

    def _update_save_path_label(self):
        if self.save_folder_path:
            self.save_path_label.setText(
                tr("label.save_path", path=str(self.save_folder_path))
            )
        else:
            self.save_path_label.setText(tr("label.save_path_none"))

    def _on_mode_changed(self):
        if self.polygon_draw_controller.is_active():
            self.polygon_draw_controller.cancel()

    def _cancel_polygon_drawing(self):
        if self.polygon_draw_controller.is_active():
            self.polygon_draw_controller.cancel()

    def _get_image_rect(self):
        pixmap_items = [
            item for item in self.image_view.scene.items()
            if type(item).__name__ == 'QGraphicsPixmapItem'
        ]
        if pixmap_items:
            pixmap = pixmap_items[0].pixmap()
            return QRectF(0, 0, pixmap.width(), pixmap.height())
        return self._current_img_rect

    def _push_undo_snapshot(self):
        self._mark_dirty()
        self._undo_stack.push_snapshot(self.label_manager.bboxes)

    def _undo(self):
        snapshot = self._undo_stack.undo()
        if snapshot is None:
            return
        self.label_manager.bboxes = clone_bboxes(snapshot)
        self._rebuild_scene_from_bboxes()
        self.refresh_bbox_list()
        if self.label_manager.bboxes:
            self._select_bbox_by_id(self.label_manager.bboxes[0].id)
        else:
            self._clear_bbox_selection()

    def _register_bbox_item(self, item):
        item.on_edit_start = self._push_undo_snapshot

    def _bbox_item_for_scene_item(self, item):
        if item is None:
            return None
        root = resolve_bbox_root(item)
        if root is not None and root in self.bbox_items.values():
            return root
        return None

    def _selected_bbox_id(self):
        items = self.image_view.scene.selectedItems()
        if not items:
            return None
        gfx = pick_preferred_bbox_root(items)
        if gfx is not None and gfx.bbox_data is not None:
            return gfx.bbox_data.id
        return None

    def _row_for_bbox_id(self, bbox_id):
        for i, bbox in enumerate(self.label_manager.bboxes):
            if bbox.id == bbox_id:
                return i
        return -1

    def _select_bbox_by_id(self, bbox_id):
        if bbox_id not in self.bbox_items:
            return
        row = self._row_for_bbox_id(bbox_id)
        if row < 0:
            return

        self._syncing_selection = True
        try:
            gfx = self.bbox_items[bbox_id]
            self.image_view.scene.blockSignals(True)
            self.image_view.scene.clearSelection()
            gfx.setSelected(True)
            self.image_view.scene.blockSignals(False)

            self.bbox_list.blockSignals(True)
            self.bbox_list.setCurrentRow(row)
            self.bbox_list.blockSignals(False)

            bbox = self.label_manager.bboxes[row]
            self.class_id_spinbox.blockSignals(True)
            self.class_id_spinbox.setValue(bbox.class_id)
            self.class_id_spinbox.blockSignals(False)
        finally:
            self._syncing_selection = False

    def _clear_bbox_selection(self):
        self._syncing_selection = True
        try:
            self.image_view.scene.blockSignals(True)
            self.image_view.scene.clearSelection()
            self.image_view.scene.blockSignals(False)
            self.bbox_list.blockSignals(True)
            self.bbox_list.setCurrentRow(-1)
            self.bbox_list.blockSignals(False)
        finally:
            self._syncing_selection = False

    def _sync_list_from_scene(self):
        bbox_id = self._selected_bbox_id()
        if bbox_id is None:
            return
        row = self._row_for_bbox_id(bbox_id)
        if row >= 0 and self.bbox_list.currentRow() != row:
            self.bbox_list.blockSignals(True)
            self.bbox_list.setCurrentRow(row)
            self.bbox_list.blockSignals(False)

    def _on_scene_selection_changed(self, bbox_item):
        if self._syncing_selection:
            return
        if bbox_item is None:
            self._syncing_selection = True
            try:
                self.bbox_list.blockSignals(True)
                self.bbox_list.setCurrentRow(-1)
                self.bbox_list.blockSignals(False)
            finally:
                self._syncing_selection = False
            return
        gfx = self._bbox_item_for_scene_item(bbox_item)
        if gfx is None:
            return
        self._select_bbox_by_id(gfx.bbox_data.id)

    def _on_bbox_list_row_changed(self, row):
        if self._syncing_selection:
            return
        if row < 0 or row >= len(self.label_manager.bboxes):
            return
        bbox_id = self.label_manager.bboxes[row].id
        self._select_bbox_by_id(bbox_id)

    def _rebuild_scene_from_bboxes(self):
        pixmap_items = [
            item for item in self.image_view.scene.items()
            if type(item).__name__ == 'QGraphicsPixmapItem'
        ]
        if not pixmap_items:
            return

        pixmap = pixmap_items[0].pixmap()
        img_rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        self._current_img_rect = img_rect

        for gfx in list(self.bbox_items.values()):
            self.image_view.scene.removeItem(gfx)
        self.bbox_items.clear()

        for bbox in self.label_manager.bboxes:
            item = self._create_gfx_for_bbox(bbox, img_rect)
            if item is not None:
                self.image_view.scene.addItem(item)
                self.bbox_items[bbox.id] = item

    def _create_gfx_for_bbox(self, bbox, img_rect):
        if bbox.type == 'rect':
            pixel_x_center = bbox.x_center * img_rect.width()
            pixel_y_center = bbox.y_center * img_rect.height()
            pixel_w = bbox.width * img_rect.width()
            pixel_h = bbox.height * img_rect.height()
            x = pixel_x_center - pixel_w / 2
            y = pixel_y_center - pixel_h / 2
            rect = QRectF(0, 0, pixel_w, pixel_h)
            item = BBoxItem(rect, bbox)
            item.setPos(x, y)
            item.set_image_rect(img_rect)
            self._register_bbox_item(item)
            return item
        if bbox.type == 'obb':
            img_w = img_rect.width()
            img_h = img_rect.height()
            px = [p[0] * img_w for p in bbox.points]
            py = [p[1] * img_h for p in bbox.points]
            cx = sum(px) / 4
            cy = sum(py) / 4
            w = math.hypot(px[1] - px[0], py[1] - py[0])
            h = math.hypot(px[2] - px[1], py[2] - py[1])
            angle_rad = math.atan2(py[1] - py[0], px[1] - px[0])
            angle = math.degrees(angle_rad)
            item = OBBItem(QPointF(cx, cy), w, h, angle, bbox)
            item.set_image_rect(img_rect)
            self._register_bbox_item(item)
            return item
        if bbox.type == 'polygon':
            item = PolygonItem.from_bbox(bbox, img_rect)
            self._register_bbox_item(item)
            return item
        return None

    def _on_polygon_draw_finished(self, scene_points):
        self.image_view.set_drawing_mode(False)
        self._push_undo_snapshot()
        bbox_id = len(self.label_manager.bboxes)
        class_id = self.class_id_spinbox.value()
        bbox = BBox(bbox_id, class_id, type='polygon', points=[])
        self.label_manager.add(bbox)

        item = PolygonItem(scene_points, bbox)
        item.set_image_rect(self._current_img_rect)
        self._register_bbox_item(item)
        self.image_view.scene.addItem(item)
        self.bbox_items[bbox_id] = item

        self.refresh_bbox_list()
        self._select_bbox_by_id(bbox_id)

    def _on_polygon_draw_cancelled(self):
        self.image_view.set_drawing_mode(False)

    def _apply_theme(self, theme_id):
        apply_theme(QApplication.instance(), self, theme_id)
        for tid, action in self.theme_actions.items():
            action.setChecked(tid == theme_id)
        for tid, action in self.theme_actions.items():
            action.setText(get_theme_name(tid))

    def set_save_folder(self):
        start_dir = self._dialog_start_dir(KEY_SAVE_FOLDER)
        folder = QFileDialog.getExistingDirectory(
            self, tr("dialog.select_save_path"), start_dir
        )
        if folder:
            self.save_folder_path = Path(folder)
            save_path_pref(KEY_SAVE_FOLDER, folder)
            self._update_save_path_label()

    def open_image(self):
        if not self.save_folder_path:
            QMessageBox.warning(
                self, tr("msg.warning"), tr("msg.set_save_path_first")
            )
            return

        start_dir = self._dialog_start_dir(KEY_LAST_IMAGE_DIR)
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dialog.select_image"), start_dir,
            "Images(*.jpg *.png *.jpeg *.bmp)"
        )
        if not path:
            return

        if self.current_image_path:
            self._maybe_save_before_nav()

        self.current_image_path = Path(path)
        save_path_pref(KEY_LAST_IMAGE_DIR, str(self.current_image_path.parent))
        self.current_folder_path = None
        self.image_list = []
        self.current_image_index = 0
        self._load_image(self.current_image_path)
        self._update_nav_label()

    def open_folder(self):
        if not self.save_folder_path:
            QMessageBox.warning(
                self, tr("msg.warning"), tr("msg.set_save_path_first")
            )
            return

        start_dir = self._dialog_start_dir(KEY_LAST_FOLDER)
        folder = QFileDialog.getExistingDirectory(
            self, tr("dialog.select_folder"), start_dir
        )
        if not folder:
            return

        folder_path = Path(folder)
        save_path_pref(KEY_LAST_FOLDER, folder)
        image_exts = {".jpg", ".jpeg", ".png", ".bmp"}
        self.image_list = sorted([
            f for f in folder_path.iterdir()
            if f.suffix.lower() in image_exts
        ])

        if not self.image_list:
            QMessageBox.warning(self, tr("msg.warning"), tr("msg.no_images_in_folder"))
            return

        if self.current_image_path:
            self._maybe_save_before_nav()

        self.current_folder_path = folder_path
        self.current_image_index = 0
        self._load_image(self.image_list[0])
        self._update_nav_label()
        self._refresh_image_list()

    def _mark_dirty(self):
        if not self._image_dirty:
            self._image_dirty = True
        if self.image_list:
            self._refresh_image_list_item(self.current_image_index)

    def _clear_dirty(self):
        self._image_dirty = False
        if self.image_list:
            self._refresh_image_list_item(self.current_image_index)

    def _has_labeled_txt(self, img_path: Path) -> bool:
        if not self.save_folder_path:
            return False
        txt_path = self.save_folder_path / img_path.with_suffix(".txt").name
        return txt_path.is_file() and txt_path.stat().st_size > 0

    def _format_list_item_text(self, img_path: Path, index: int) -> str:
        name = img_path.name
        if index == self.current_image_index and self._image_dirty:
            return tr("list.modified", name=name)
        if self._has_labeled_txt(img_path):
            return tr("list.labeled", name=name)
        return tr("list.unlabeled", name=name)

    def _refresh_image_list_item(self, index: int):
        if index < 0 or index >= len(self.image_list):
            return
        item = self.image_list_widget.item(index)
        if item is None:
            return
        item.setText(self._format_list_item_text(self.image_list[index], index))

    def _refresh_image_list(self):
        self.image_list_widget.clear()
        for i, img_path in enumerate(self.image_list):
            self.image_list_widget.addItem(self._format_list_item_text(img_path, i))

    def _load_image(self, image_path: Path):
        self._cancel_polygon_drawing()
        self.image_view.set_drawing_mode(False)

        if not self.save_folder_path:
            QMessageBox.critical(self, tr("msg.error"), tr("msg.save_path_not_set"))
            return

        if not image_path.exists():
            QMessageBox.warning(
                self, tr("msg.error"), tr("msg.image_not_found", path=image_path)
            )
            return

        try:
            self.current_image_path = image_path
            pixmap = load_image(self.current_image_path)
            self.image_view.load_pixmap(pixmap)

            txt_path = self.save_folder_path / image_path.with_suffix(".txt").name
            self.label_manager.bboxes = load_yolo_txt(txt_path)
            self._undo_stack.clear()

            self.image_view.scene.clear()
            pixmap_item = self.image_view.scene.addPixmap(pixmap)
            pixmap_item.setZValue(-1)
            self.bbox_items = {}

            img_rect = QRectF(0, 0, pixmap.width(), pixmap.height())
            self._current_img_rect = img_rect
            self._rebuild_scene_from_bboxes()
            self.refresh_bbox_list()
            self._clear_bbox_selection()
            self._clear_dirty()
        except Exception as e:
            QMessageBox.critical(
                self, tr("msg.error"), tr("msg.load_image_failed", error=str(e))
            )

    def _update_nav_label(self):
        if self.image_list:
            total = len(self.image_list)
            current = self.current_image_index + 1
            self.img_counter_label.setText(f"{current}/{total}")
            self.image_list_widget.blockSignals(True)
            self.image_list_widget.setCurrentRow(self.current_image_index)
            self.image_list_widget.blockSignals(False)
            self._refresh_image_list_item(self.current_image_index)
        else:
            self.img_counter_label.setText("0/0")

    def _maybe_save_before_nav(self):
        if not self._app_settings.auto_save_on_nav:
            return
        if not self.save_txt(show_toast=False):
            self._show_toast(tr("toast.auto_save_skipped"))

    def on_image_list_row_changed(self, row):
        if row >= 0 and row < len(self.image_list) and row != self.current_image_index:
            self._maybe_save_before_nav()
            self.current_image_index = row
            self._load_image(self.image_list[self.current_image_index])
            self._update_nav_label()

    def show_prev_image(self):
        if not self.image_list:
            QMessageBox.information(self, tr("msg.info"), tr("msg.open_folder_first"))
            return

        self._maybe_save_before_nav()

        self.current_image_index = (self.current_image_index - 1) % len(self.image_list)
        self._load_image(self.image_list[self.current_image_index])
        self._update_nav_label()

    def show_next_image(self):
        if not self.image_list:
            QMessageBox.information(self, tr("msg.info"), tr("msg.open_folder_first"))
            return

        self._maybe_save_before_nav()

        self.current_image_index = (self.current_image_index + 1) % len(self.image_list)
        self._load_image(self.image_list[self.current_image_index])
        self._update_nav_label()

    def save_txt(self, show_toast=True):
        if not self.current_image_path or not self.save_folder_path:
            return False

        try:
            txt_path = self.save_folder_path / self.current_image_path.with_suffix(".txt").name
            save_yolo_txt(txt_path, self.label_manager.bboxes)
            self._clear_dirty()
            if show_toast:
                self._show_toast(tr("toast.save_success"))
            return True
        except Exception as e:
            QMessageBox.warning(
                self, tr("msg.save_failed"), tr("msg.save_txt_failed", error=str(e))
            )
            return False

    def save_all_in_folder(self, show_toast=False):
        if not self.save_folder_path or not self.image_list:
            return

        try:
            for i, img_path in enumerate(self.image_list):
                txt_path = self.save_folder_path / img_path.with_suffix(".txt").name
                if i == self.current_image_index:
                    bboxes = self.label_manager.bboxes
                else:
                    bboxes = load_yolo_txt(txt_path)
                save_yolo_txt(txt_path, bboxes)
            self._clear_dirty()
            if show_toast:
                self._show_toast(tr("toast.periodic_save_done"))
        except Exception as e:
            QMessageBox.warning(
                self, tr("msg.save_failed"), tr("msg.save_txt_failed", error=str(e))
            )

    def _show_toast(self, message):
        toast = QLabel(message)
        toast.setObjectName("toastLabel")
        toast.setFont(QFont("Arial", 12, QFont.Bold))
        toast.setParent(self)
        toast.adjustSize()

        geometry = self.geometry()
        toast.move(
            geometry.width() - toast.width() - 20,
            geometry.height() - toast.height() - 60
        )
        toast.show()

        QTimer.singleShot(1000, toast.deleteLater)

    def fit_image_to_view(self):
        self.image_view.fit_to_view()

    def refresh_bbox_list(self):
        self.bbox_list.clear()
        for bbox in self.label_manager.bboxes:
            if bbox.type == 'rect':
                prefix = "[Rect]"
                extra = ""
            elif bbox.type == 'obb':
                prefix = "[OBB]"
                extra = ""
            else:
                prefix = "[Poly]"
                extra = f" | {len(bbox.points or [])}pts"
            text = f"{prefix} ID{bbox.id} | Class: {bbox.class_id}{extra}"
            self.bbox_list.addItem(text)
        self._sync_list_from_scene()

    def add_bbox(self):
        if not self.current_image_path:
            QMessageBox.warning(self, tr("msg.info"), tr("msg.open_image_first"))
            return

        img_rect = self._get_image_rect()
        self._current_img_rect = img_rect

        if self.radio_polygon.isChecked():
            self.polygon_draw_controller.start(self.image_view.scene, img_rect)
            self.image_view.set_drawing_mode(True)
            return

        img_w = img_rect.width()
        img_h = img_rect.height()
        box_w = img_w * 0.2
        box_h = img_h * 0.2
        x = (img_w - box_w) / 2
        y = (img_h - box_h) / 2

        self._push_undo_snapshot()
        bbox_id = len(self.label_manager.bboxes)
        is_obb = self.radio_obb.isChecked()

        if is_obb:
            bbox = BBox(bbox_id, 0, type='obb', points=[])
            self.label_manager.add(bbox)

            cx = img_w / 2
            cy = img_h / 2
            angle = 15.0

            item = OBBItem(QPointF(cx, cy), box_w, box_h, angle, bbox)
            item.set_image_rect(img_rect)
            self._register_bbox_item(item)
            self.image_view.scene.addItem(item)
            self.bbox_items[bbox_id] = item
        else:
            bbox = BBox(bbox_id, 0, type='rect', x_center=0.5, y_center=0.5, width=0.2, height=0.2)
            self.label_manager.add(bbox)

            rect = QRectF(0, 0, box_w, box_h)
            item = BBoxItem(rect, bbox)
            item.setPos(x, y)
            item.set_image_rect(img_rect)
            self._register_bbox_item(item)
            self.image_view.scene.addItem(item)
            self.bbox_items[bbox_id] = item

        self.refresh_bbox_list()
        self._select_bbox_by_id(bbox_id)

    def _resolve_delete_row(self):
        bbox_id = self._selected_bbox_id()
        if bbox_id is not None:
            return self._row_for_bbox_id(bbox_id)
        row = self.bbox_list.currentRow()
        if 0 <= row < len(self.label_manager.bboxes):
            return row
        return None

    def delete_bbox(self):
        row = self._resolve_delete_row()
        if row is None:
            return

        self._push_undo_snapshot()
        bbox = self.label_manager.bboxes[row]
        bbox_id = bbox.id

        if bbox_id in self.bbox_items:
            gfx_item = self.bbox_items[bbox_id]
            self.image_view.scene.removeItem(gfx_item)
            del self.bbox_items[bbox_id]

        self.label_manager.remove(bbox_id)
        self.refresh_bbox_list()

        if self.label_manager.bboxes:
            new_row = min(row, len(self.label_manager.bboxes) - 1)
            self._select_bbox_by_id(self.label_manager.bboxes[new_row].id)
        else:
            self._clear_bbox_selection()

    def on_class_id_changed(self, value):
        bbox_id = self._selected_bbox_id()
        if bbox_id is None:
            return
        row = self._row_for_bbox_id(bbox_id)
        if row < 0:
            return

        self._push_undo_snapshot()
        self.label_manager.bboxes[row].class_id = value
        self.refresh_bbox_list()
        self._select_bbox_by_id(bbox_id)
