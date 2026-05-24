import sys
from PyQt5.QtWidgets import QApplication, QStyleFactory
from ui.main_window import MainWindow
from ui.theme_manager import apply_theme, init_saved_theme

def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))

    saved_theme = init_saved_theme()
    window = MainWindow()
    window.setWindowTitle("YOLO 标注工具 - YOLOTxtMaker")
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

