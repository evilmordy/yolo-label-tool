"""Load images for the canvas, with a small background prefetch cache.

QPixmap objects are only created on the GUI thread. A worker thread decodes
QImage files; the main thread turns those into pixmaps. That keeps Windows
high-DPI pixmap handling on the same thread as a direct QPixmap(path) load.
"""
from collections import OrderedDict
from typing import Optional, Sequence

from PyQt5.QtCore import QMutex, QObject, QThread, QWaitCondition, Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap


def neighbor_paths(image_list, index, radius=2, direction=1):
    """Next/previous paths, nearest first, wrapping like the image list."""
    count = len(image_list)
    if count <= 1 or not (0 <= index < count):
        return []
    step = 1 if direction >= 0 else -1
    ordered = []
    seen = set()
    for distance in range(1, radius + 1):
        for delta in (step * distance, -step * distance):
            other = (index + delta) % count
            if other == index:
                continue
            path = image_list[other]
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(path)
    return ordered


def _read_image(path: str):
    try:
        image = QImage()
        if not image.load(path):
            return None
        # Deep copy so the queued signal does not share pixels with this thread.
        return image.copy()
    except Exception:
        return None


class _DecodeWorker(QThread):
    image_ready = pyqtSignal(int, str, QImage)

    def __init__(self):
        super().__init__()
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._queue = []
        self._generation = 0
        self._running = True

    def submit(self, generation: int, paths):
        self._mutex.lock()
        try:
            self._generation = generation
            self._queue = [(generation, str(path)) for path in paths]
            self._cond.wakeAll()
        finally:
            self._mutex.unlock()

    def reset(self, generation: int):
        self.submit(generation, [])

    def stop(self):
        self._mutex.lock()
        try:
            self._running = False
            self._queue.clear()
            self._cond.wakeAll()
        finally:
            self._mutex.unlock()
        self.wait()

    def run(self):
        while True:
            self._mutex.lock()
            while self._running and not self._queue:
                self._cond.wait(self._mutex)
            if not self._running:
                self._mutex.unlock()
                return
            generation, path = self._queue.pop(0)
            active = self._generation
            self._mutex.unlock()
            if generation != active:
                continue
            image = _read_image(path)
            self._mutex.lock()
            still_valid = self._running and generation == self._generation
            self._mutex.unlock()
            if not still_valid or image is None or image.isNull():
                continue
            self.image_ready.emit(generation, path, image)


class ImageCache(QObject):
    """LRU of QPixmaps. Folder changes bump the generation and drop results."""

    def __init__(self, capacity: int = 5, parent=None):
        super().__init__(parent)
        self._capacity = max(1, int(capacity))
        self._items = OrderedDict()
        self._wanted = set()
        self._generation = 0
        self._alive = True
        self._worker = _DecodeWorker()
        self._worker.image_ready.connect(self._on_image_ready, Qt.QueuedConnection)
        self._worker.start()

    def pixmap(self, path) -> Optional[QPixmap]:
        key = str(path)
        found = self._items.get(key)
        if found is None:
            return None
        self._items.move_to_end(key)
        return found

    def insert(self, path, pixmap: QPixmap):
        if pixmap is None or pixmap.isNull():
            return
        key = str(path)
        self._items[key] = pixmap
        self._items.move_to_end(key)
        self._trim()

    def prefetch(self, paths: Sequence):
        if not self._alive:
            return
        missing = []
        wanted = set()
        for path in paths:
            key = str(path)
            wanted.add(key)
            if key in self._items:
                self._items.move_to_end(key)
                continue
            missing.append(key)
        self._wanted = wanted
        self._worker.submit(self._generation, missing)

    def invalidate(self):
        self._generation += 1
        self._items.clear()
        self._wanted = set()
        if self._alive:
            self._worker.reset(self._generation)

    def shutdown(self):
        if not self._alive:
            return
        self._alive = False
        self._generation += 1
        self._wanted = set()
        self._worker.stop()
        self._items.clear()

    def _trim(self):
        while len(self._items) > self._capacity:
            self._items.popitem(last=False)

    def _on_image_ready(self, generation: int, path: str, image: QImage):
        if not self._alive or generation != self._generation:
            return
        if path not in self._wanted:
            return
        if image is None or image.isNull():
            return
        self.insert(path, QPixmap.fromImage(image))


def load_image(path, cache: Optional[ImageCache] = None):
    if cache is not None:
        cached = cache.pixmap(path)
        if cached is not None and not cached.isNull():
            return cached
    pixmap = QPixmap(str(path))
    if cache is not None:
        cache.insert(path, pixmap)
    return pixmap
