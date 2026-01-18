from PyQt5.QtGui import QPixmap

def load_image(path):

    pixmap = QPixmap(str(path))
    return pixmap