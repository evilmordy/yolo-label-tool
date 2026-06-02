from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, QLabel,
    QComboBox, QSpinBox, QKeySequenceEdit, QPushButton, QMessageBox,
    QDialogButtonBox,
)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QKeySequence

from core.settings_manager import (
    AppSettings, ShortcutKey, load_all, save_settings,
    default_shortcuts, shortcuts_conflict, DEFAULT_SHORTCUTS,
)
from i18n.translator import tr


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = load_all()
        self._shortcut_edits = {}
        self._labels = {}
        self._init_ui()
        self._load_values()
        self.retranslate()

    def _init_ui(self):
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)

        behavior_group = QGroupBox()
        behavior_group.setObjectName("behaviorGroup")
        behavior_layout = QVBoxLayout(behavior_group)

        self.chk_auto_save_nav = QCheckBox()
        behavior_layout.addWidget(self.chk_auto_save_nav)

        self.lbl_nav_hint = QLabel()
        self.lbl_nav_hint.setWordWrap(True)
        self.lbl_nav_hint.setObjectName("secondaryLabel")
        behavior_layout.addWidget(self.lbl_nav_hint)

        self.chk_periodic = QCheckBox()
        behavior_layout.addWidget(self.chk_periodic)

        interval_row = QHBoxLayout()
        self.lbl_interval = QLabel()
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 60)
        self.spin_interval.setValue(5)
        interval_row.addWidget(self.lbl_interval)
        interval_row.addWidget(self.spin_interval)
        interval_row.addStretch()
        behavior_layout.addLayout(interval_row)

        self.chk_periodic.toggled.connect(self.spin_interval.setEnabled)
        layout.addWidget(behavior_group)

        lang_group = QGroupBox()
        lang_group.setObjectName("langGroup")
        lang_layout = QHBoxLayout(lang_group)
        self.lbl_language = QLabel()
        self.combo_language = QComboBox()
        self.combo_language.addItem("", "zh")
        self.combo_language.addItem("", "en")
        self.combo_language.addItem("", "ja")
        lang_layout.addWidget(self.lbl_language)
        lang_layout.addWidget(self.combo_language)
        lang_layout.addStretch()
        layout.addWidget(lang_group)

        shortcut_group = QGroupBox()
        shortcut_group.setObjectName("shortcutGroup")
        shortcut_layout = QVBoxLayout(shortcut_group)

        shortcut_defs = [
            (ShortcutKey.SAVE, "settings.shortcut_save"),
            (ShortcutKey.UNDO, "settings.shortcut_undo"),
            (ShortcutKey.ADD, "settings.shortcut_add"),
            (ShortcutKey.DELETE, "settings.shortcut_delete"),
            (ShortcutKey.RECT, "settings.shortcut_rect"),
            (ShortcutKey.OBB, "settings.shortcut_obb"),
            (ShortcutKey.POLYGON, "settings.shortcut_polygon"),
            (ShortcutKey.POLYGON_FINISH, "settings.shortcut_finish"),
            (ShortcutKey.POLYGON_CANCEL, "settings.shortcut_cancel"),
            (ShortcutKey.PREV_IMAGE, "settings.shortcut_prev_image"),
            (ShortcutKey.NEXT_IMAGE, "settings.shortcut_next_image"),
        ]
        for key, label_key in shortcut_defs:
            row = QHBoxLayout()
            lbl = QLabel()
            lbl.setMinimumWidth(160)
            edit = QKeySequenceEdit()
            self._labels[label_key] = lbl
            self._shortcut_edits[key] = edit
            row.addWidget(lbl)
            row.addWidget(edit)
            shortcut_layout.addLayout(row)

        self.btn_reset_shortcuts = QPushButton()
        self.btn_reset_shortcuts.clicked.connect(self._reset_shortcuts)
        shortcut_layout.addWidget(self.btn_reset_shortcuts)
        layout.addWidget(shortcut_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._btn_ok = buttons.button(QDialogButtonBox.Ok)
        self._btn_cancel = buttons.button(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._behavior_group = behavior_group
        self._lang_group = lang_group
        self._shortcut_group = shortcut_group

    def _load_values(self):
        s = self._settings
        self.chk_auto_save_nav.setChecked(s.auto_save_on_nav)
        self.chk_periodic.setChecked(s.periodic_auto_save)
        self.spin_interval.setValue(s.periodic_interval_min)
        self.spin_interval.setEnabled(s.periodic_auto_save)

        idx = self.combo_language.findData(s.language)
        if idx >= 0:
            self.combo_language.setCurrentIndex(idx)

        for key, edit in self._shortcut_edits.items():
            seq = s.shortcuts.get(key.value, DEFAULT_SHORTCUTS[key])
            edit.setKeySequence(QKeySequence(seq))

    def _reset_shortcuts(self):
        defaults = default_shortcuts()
        for key, edit in self._shortcut_edits.items():
            edit.setKeySequence(QKeySequence(defaults[key.value]))

    def _collect_settings(self) -> AppSettings:
        shortcuts = {}
        for key, edit in self._shortcut_edits.items():
            seq = edit.keySequence().toString()
            shortcuts[key.value] = seq if seq else DEFAULT_SHORTCUTS[key]

        language = self.combo_language.currentData() or "zh"

        return AppSettings(
            auto_save_on_nav=self.chk_auto_save_nav.isChecked(),
            language=language,
            periodic_auto_save=self.chk_periodic.isChecked(),
            periodic_interval_min=self.spin_interval.value(),
            shortcuts=shortcuts,
        )

    def _on_accept(self):
        new_settings = self._collect_settings()
        if shortcuts_conflict(new_settings.shortcuts):
            QMessageBox.warning(
                self, tr("msg.warning"), tr("settings.shortcut_conflict")
            )
            return
        save_settings(new_settings)
        self.settings_changed.emit(new_settings)
        self.accept()

    def retranslate(self):
        self.setWindowTitle(tr("settings.title"))
        self._behavior_group.setTitle(tr("settings.behavior"))
        self.chk_auto_save_nav.setText(tr("settings.auto_save_on_nav"))
        self.lbl_nav_hint.setText(tr("settings.nav_save_hint"))
        self.chk_periodic.setText(tr("settings.periodic_auto_save"))
        self.lbl_interval.setText(tr("settings.periodic_interval"))
        self._lang_group.setTitle(tr("settings.language"))
        self.lbl_language.setText(tr("settings.language"))
        self._shortcut_group.setTitle(tr("settings.shortcuts"))
        self.btn_reset_shortcuts.setText(tr("settings.reset_shortcuts"))
        self._btn_ok.setText(tr("settings.ok"))
        self._btn_cancel.setText(tr("settings.cancel"))

        label_keys = {
            "settings.shortcut_save": "settings.shortcut_save",
            "settings.shortcut_undo": "settings.shortcut_undo",
            "settings.shortcut_add": "settings.shortcut_add",
            "settings.shortcut_delete": "settings.shortcut_delete",
            "settings.shortcut_rect": "settings.shortcut_rect",
            "settings.shortcut_obb": "settings.shortcut_obb",
            "settings.shortcut_polygon": "settings.shortcut_polygon",
            "settings.shortcut_finish": "settings.shortcut_finish",
            "settings.shortcut_cancel": "settings.shortcut_cancel",
            "settings.shortcut_prev_image": "settings.shortcut_prev_image",
            "settings.shortcut_next_image": "settings.shortcut_next_image",
        }
        for key, lbl in self._labels.items():
            lbl.setText(tr(key))

        lang_items = [
            ("settings.lang_zh", "zh"),
            ("settings.lang_en", "en"),
            ("settings.lang_ja", "ja"),
        ]
        for i, (text_key, _) in enumerate(lang_items):
            self.combo_language.setItemText(i, tr(text_key))
