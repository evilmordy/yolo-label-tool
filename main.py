import os
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QStyleFactory
from ui.main_window import MainWindow
from ui.theme_manager import apply_theme, init_saved_theme
from core.settings_manager import load_language
from i18n.translator import init_language, tr


def _configure_windows_dpi():
    """Keep mouse coordinates aligned on fractional Windows display scales.

    Linux main.py is unaffected: this runs only on win32. 125% and 150%
    scaling is the common Windows setup. Rounding that factor to an integer
    makes Qt's scene mapping disagree with the cursor, which shows up as the
    box jumping under the pointer. PassThrough keeps the real scale factor.
    Attributes must be set before QApplication is constructed.
    """
    if sys.platform != "win32":
        return
    # Honor an explicit opt-out. Otherwise fractional scaling stays exact.
    if os.environ.get("QT_ENABLE_HIGHDPI_SCALING") == "0":
        return
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )


def main():
    _configure_windows_dpi()
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))

    init_language(load_language())
    saved_theme = init_saved_theme()
    window = MainWindow()
    window.setWindowTitle(tr("app.title"))
    apply_theme(app, window, saved_theme)
    
    # 获取屏幕大小，设置合理的初始窗口大小
    screen = app.primaryScreen()
    screen_geometry = screen.availableGeometry()
    screen_width = screen_geometry.width()
    screen_height = screen_geometry.height()
    
    # 设置窗口大小为屏幕的80%，但不超过2560x1440
    window_width = min(int(screen_width * 0.8), 2560)
    window_height = min(int(screen_height * 0.85), 1440)
    window.resize(window_width, window_height)
    
    # 将窗口居中显示
    window.move(
        (screen_width - window_width) // 2,
        (screen_height - window_height) // 2
    )
    
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

