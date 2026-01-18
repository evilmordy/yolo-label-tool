import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # 加载样式
    style_path = Path(__file__).parent / "resources" / "style.qss"
    if style_path.exists():
        with open(style_path, "r", encoding="utf-8") as f:
            style_sheet = f.read()
            app.setStyleSheet(style_sheet)
    
    window = MainWindow()
    window.setWindowTitle("YOLO 标注工具 - YOLOTxtMaker")
    
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

