"""Screen-sized grab handles shared by rect, OBB, and polygon items.

ItemIgnoresTransformations keeps the dot a constant size on screen, which is
what stops handle pixels from being written into YOLO boxes. In that mode the
item's local coordinates are viewport pixels, not scene units.
QGraphicsItem.mapToScene() does not apply the view (or the Windows display
scale), so mapToScene(event.pos()) only matches the cursor when the view
scale is 1 and the screen scale is 1 — the usual Linux main.py case. On a
Windows laptop the image is fit into a smaller logical viewport and the
display is often at 125% or 150%, and that mismatch feeds back into the drag
and the box jumps.

event.scenePos() is the scene position QGraphicsView already computed from
the viewport mouse position. It stays aligned with the cursor on both
platforms.
"""
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsItem

# Drawn size, in viewport pixels. Kept at the historical 8px so the Linux UI
# does not change.
HANDLE_VISUAL_SIZE = 8
# Invisible grab diameter, in viewport pixels. The old 8px ellipse had a
# radius of 4px, which is very hard to hit on a high-DPI Windows display.
HANDLE_HIT_SIZE = 24


class ScreenHandle(QGraphicsEllipseItem):
    def __init__(self, parent=None):
        size = float(HANDLE_HIT_SIZE)
        super().__init__(-size / 2, -size / 2, size, size, parent)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setZValue(10)

    def paint(self, painter, option, widget=None):
        # Paint only the visual dot. The item rect stays at HANDLE_HIT_SIZE,
        # and QGraphicsEllipseItem.shape() uses that rect, so the grab target
        # is larger than the dot. Parents must keep syncing YOLO from their
        # own geometry, never from sceneBoundingRect(), which includes this.
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        visual = float(HANDLE_VISUAL_SIZE)
        painter.drawEllipse(QRectF(-visual / 2, -visual / 2, visual, visual))


def event_scene_pos(event):
    """Cursor position in scene coordinates, independent of item transforms."""
    return event.scenePos()
