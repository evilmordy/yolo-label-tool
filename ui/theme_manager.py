from pathlib import Path

from PyQt5.QtCore import QSettings

THEME_IDS = ("light_blue", "light_pink", "deep_blue")
DEFAULT_THEME = "deep_blue"
SETTINGS_KEY = "theme"

THEMES = {
    "light_blue": {
        "name": "淡蓝",
        "bg_main": "#f4f7fb",
        "bg_panel": "#ffffff",
        "bg_canvas": "#e2e8f0",
        "text": "#1e293b",
        "text_muted": "#64748b",
        "text_on_accent": "#ffffff",
        "border": "#cbd5e1",
        "accent": "#3b82f6",
        "accent_hover": "#2563eb",
        "accent_soft": "#dbeafe",
        "btn_bg": "#f1f5f9",
        "btn_hover": "#e2e8f0",
        "btn_pressed": "#cbd5e1",
        "btn_border": "#cbd5e1",
        "input_bg": "#ffffff",
        "list_hover": "#f1f5f9",
        "menubar_hover": "#e2e8f0",
        "scrollbar_handle": "#cbd5e1",
        "scrollbar_handle_hover": "#94a3b8",
        "handle_hover": "#60a5fa",
    },
    "light_pink": {
        "name": "淡粉",
        "bg_main": "#fdf2f8",
        "bg_panel": "#ffffff",
        "bg_canvas": "#f1f5f9",
        "text": "#374151",
        "text_muted": "#9ca3af",
        "text_on_accent": "#ffffff",
        "border": "#fbcfe8",
        "accent": "#ec4899",
        "accent_hover": "#db2777",
        "accent_soft": "#fce7f3",
        "btn_bg": "#fdf4ff",
        "btn_hover": "#fce7f3",
        "btn_pressed": "#fbcfe8",
        "btn_border": "#fbcfe8",
        "input_bg": "#ffffff",
        "list_hover": "#fdf4ff",
        "menubar_hover": "#fce7f3",
        "scrollbar_handle": "#fbcfe8",
        "scrollbar_handle_hover": "#f9a8d4",
        "handle_hover": "#f472b6",
    },
    "deep_blue": {
        "name": "深蓝",
        "bg_main": "#1a1a2e",
        "bg_panel": "#16213e",
        "bg_canvas": "#243447",
        "text": "#e0e0e0",
        "text_muted": "#94a3b8",
        "text_on_accent": "#ffffff",
        "border": "#2a4a6b",
        "accent": "#16a085",
        "accent_hover": "#1a9c8a",
        "accent_soft": "#0f3460",
        "btn_bg": "#0f3460",
        "btn_hover": "#1a4d6d",
        "btn_pressed": "#0d6f5c",
        "btn_border": "#2a4a6b",
        "input_bg": "#1a1a2e",
        "list_hover": "#1a4d6d",
        "menubar_hover": "#1a4d6d",
        "scrollbar_handle": "#2a4a6b",
        "scrollbar_handle_hover": "#3d5a7a",
        "handle_hover": "#1a9c8a",
    },
}

_current_theme_id = DEFAULT_THEME
_template_cache = None


def _resources_dir():
    return Path(__file__).resolve().parent.parent / "resources"


def _load_template():
    global _template_cache
    if _template_cache is None:
        template_path = _resources_dir() / "style.qss"
        _template_cache = template_path.read_text(encoding="utf-8")
    return _template_cache


def get_theme_ids():
    return THEME_IDS


def get_theme_name(theme_id):
    from i18n.translator import tr
    key_map = {
        "light_blue": "theme.light_blue",
        "light_pink": "theme.light_pink",
        "deep_blue": "theme.deep_blue",
    }
    return tr(key_map.get(theme_id, "theme.deep_blue"))


def get_current_theme_id():
    return _current_theme_id


def get_palette(theme_id=None):
    if theme_id is None:
        theme_id = _current_theme_id
    return THEMES[theme_id]


def load_saved_theme_id():
    settings = QSettings("YOLOTxtMaker", "YOLOTxtMaker")
    theme_id = str(settings.value(SETTINGS_KEY, DEFAULT_THEME))
    if theme_id not in THEMES:
        theme_id = DEFAULT_THEME
    return theme_id


def init_saved_theme():
    global _current_theme_id
    _current_theme_id = load_saved_theme_id()
    return _current_theme_id


def save_theme_id(theme_id):
    settings = QSettings("YOLOTxtMaker", "YOLOTxtMaker")
    settings.setValue(SETTINGS_KEY, theme_id)


def build_stylesheet(theme_id=None):
    palette = get_palette(theme_id)
    return _load_template().format(**palette)


def get_annotation_colors(theme_id=None):
    palette = get_palette(theme_id)
    return {
        "selected": palette["accent"],
        "unselected": "#64748b",
        "handle": "#ffffff",
        "handle_border": palette["accent"],
        "handle_hover": palette["handle_hover"],
        "rotate": palette["accent"],
    }


def apply_theme(app, window, theme_id):
    global _current_theme_id
    if theme_id not in THEMES:
        theme_id = DEFAULT_THEME

    _current_theme_id = theme_id
    save_theme_id(theme_id)

    app.setStyleSheet(build_stylesheet(theme_id))

    palette = get_palette(theme_id)
    window.image_view.set_canvas_color(palette["bg_canvas"])

    for item in window.bbox_items.values():
        item.refresh_theme_colors()
