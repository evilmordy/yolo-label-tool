"""OBB drag/rotation and handle hit-testing.

Linux main.py usually looks fine because fit-to-view scale is near 1 and the
display scale is 1, so mapToScene(event.pos()) on an
ItemIgnoresTransformations handle happens to match the cursor. Windows
laptops fit the image into a smaller logical viewport and often run at
125%/150% DPI, and the same mapping runs away from the pointer.

These tests drive a real QGraphicsView at scale 1 (Linux-like) and at
scale 0.2 (zoomed-out / high-DPI logical viewport).
"""
import math
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from PyQt5.QtWidgets import QApplication, QGraphicsScene, QGraphicsView
from PyQt5.QtCore import Qt, QPointF, QPoint, QRectF, QEvent
from PyQt5.QtGui import QMouseEvent

from core.bbox import BBox
from ui.obb_item import OBBItem, MIN_SIZE
from ui.bbox_item import BBoxItem
from ui.polygon_item import PolygonItem
from ui.screen_handle import HANDLE_HIT_SIZE, HANDLE_VISUAL_SIZE


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _send(view, etype, scene_point):
    view_pt = view.mapFromScene(scene_point)
    vp = QPoint(int(round(view_pt.x())), int(round(view_pt.y())))
    buttons = Qt.NoButton if etype == QEvent.MouseButtonRelease else Qt.LeftButton
    ev = QMouseEvent(
        etype,
        QPointF(vp),
        QPointF(view.viewport().mapToGlobal(vp)),
        Qt.LeftButton,
        buttons,
        Qt.NoModifier,
    )
    QApplication.sendEvent(view.viewport(), ev)
    QApplication.processEvents()


def _release_grab(view):
    scene = view.scene()
    if scene is None:
        return
    grabber = scene.mouseGrabberItem()
    if grabber is not None:
        grabber.ungrabMouse()


class _ScaledView:
    def __init__(self, scale):
        self.view = QGraphicsView()
        self.view.setScene(QGraphicsScene())
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.resize(1000, 800)
        self.view.scale(scale, scale)
        self.view.show()
        QApplication.processEvents()

    def center_and_send(self, etype, scene_point):
        if etype == QEvent.MouseButtonPress:
            self.view.centerOn(scene_point)
            QApplication.processEvents()
        _send(self.view, etype, scene_point)


class OBBGeometryTests(unittest.TestCase):
    def setUp(self):
        self.app = _app()

    def _item(self, angle=0.0, w=200.0, h=100.0):
        bbox = BBox(id=0, class_id=0, type="obb", points=[])
        item = OBBItem(QPointF(0, 0), w, h, angle, bbox)
        item.set_image_rect(QRectF(-2000, -2000, 4000, 4000))
        return item

    def test_resize_from_corner_follows_delta_not_click_offset(self):
        item = self._item()
        corner = QPointF(item.corners[2])
        # Grab 8px to the right of the corner (inside the hit pad, off the dot).
        press = QPointF(corner.x() + 8, corner.y())
        item.start_drag("br", press)
        item.do_drag("br", QPointF(press.x() + 30, press.y()))
        self.assertAlmostEqual(item.w, 230, places=4)
        self.assertAlmostEqual(item.h, 100, places=4)
        self.assertAlmostEqual(item.cx, 15, places=4)
        self.assertAlmostEqual(item.cy, 0, places=4)
        self.assertAlmostEqual(item.angle, 0, places=4)

    def test_resize_respects_rotation(self):
        item = self._item(angle=90, w=100, h=40)
        corner = QPointF(item.corners[2])
        item.start_drag("br", corner)
        # Local +x at angle 90 is scene +y.
        item.do_drag("br", QPointF(corner.x(), corner.y() + 10))
        self.assertAlmostEqual(item.w, 110, places=3)
        self.assertAlmostEqual(item.h, 40, places=3)
        self.assertAlmostEqual(item.cx, 0, places=3)
        self.assertAlmostEqual(item.cy, 5, places=3)
        self.assertAlmostEqual(item.angle, 90, places=3)

    def test_resize_min_size(self):
        item = self._item(w=100, h=40)
        corner = QPointF(item.corners[2])
        item.start_drag("br", corner)
        item.do_drag("br", QPointF(corner.x() - 1000, corner.y() - 1000))
        self.assertAlmostEqual(item.w, MIN_SIZE, places=4)
        self.assertAlmostEqual(item.h, MIN_SIZE, places=4)

    def test_rotation_uses_short_delta_across_wrap(self):
        item = self._item()
        press = QPointF(math.cos(math.radians(170)) * 80, math.sin(math.radians(170)) * 80)
        item.start_drag("rotate", press)
        current = QPointF(math.cos(math.radians(-170)) * 80, math.sin(math.radians(-170)) * 80)
        item.do_drag("rotate", current)
        self.assertAlmostEqual(item.angle, 20, places=3)

    def test_yolo_points_ignore_handle_size(self):
        bbox = BBox(id=0, class_id=0, type="obb", points=[])
        img = QRectF(0, 0, 1000, 800)
        item = OBBItem(QPointF(500, 400), 200, 100, 0, bbox)
        item.set_image_rect(img)
        item._sync_to_yolo()
        for _ in range(20):
            item.set_image_rect(img)
            item._sync_to_yolo()
        # Top edge length is width/image_width, not width+handle.
        p0, p1 = bbox.points[0], bbox.points[1]
        edge = math.hypot((p1[0] - p0[0]) * img.width(), (p1[1] - p0[1]) * img.height())
        self.assertAlmostEqual(edge, 200, places=3)
        self.assertLess(edge, 200 + HANDLE_VISUAL_SIZE / 2)
        inflated = item.sceneBoundingRect()
        self.assertGreater(inflated.width(), 200)


class OBBViewDragTests(unittest.TestCase):
    def setUp(self):
        self.app = _app()

    def tearDown(self):
        _release_grab(self.view.view)
        self.view.view.close()

    def _place(self, scale, angle=0.0):
        self.view = _ScaledView(scale)
        bbox = BBox(id=0, class_id=0, type="obb", points=[])
        self.bbox = bbox
        self.item = OBBItem(QPointF(400, 300), 200, 100, angle, bbox)
        self.item.set_image_rect(QRectF(0, 0, 2000, 1600))
        self.view.view.scene().addItem(self.item)
        QApplication.processEvents()

    def _drag(self, press_scene, move_scenes):
        self.view.center_and_send(QEvent.MouseButtonPress, press_scene)
        for point in move_scenes:
            self.view.center_and_send(QEvent.MouseMove, point)
        self.view.center_and_send(QEvent.MouseButtonRelease, move_scenes[-1])

    def test_scale1_body_drag_matches_cursor(self):
        self._place(1.0)
        center = QPointF(self.item.cx, self.item.cy)
        self._drag(center, [QPointF(center.x() + 40, center.y() + 15)])
        self.assertAlmostEqual(self.item.cx, 440, delta=2.0)
        self.assertAlmostEqual(self.item.cy, 315, delta=2.0)
        self.assertAlmostEqual(self.item.angle, 0, delta=0.1)
        self.assertAlmostEqual(self.item.w, 200, delta=0.1)

    def test_scale1_rotation_tracks_pointer(self):
        self._place(1.0)
        self._assert_rotation_tracks()

    def test_zoomed_out_rotation_does_not_jump(self):
        # 0.2 is what fit-to-view does to a large photo in a laptop window,
        # and it is where the old mapToScene path reversed direction.
        self._place(0.2)
        self._assert_rotation_tracks()

    def _assert_rotation_tracks(self):
        handle = self.item.handles["rotate"].pos()
        cx, cy = self.item.cx, self.item.cy
        radius = math.hypot(handle.x() - cx, handle.y() - cy)
        start = math.atan2(handle.y() - cy, handle.x() - cx)
        points = []
        for step in range(1, 7):
            a = start + math.radians(15 * step)
            points.append(QPointF(cx + radius * math.cos(a), cy + radius * math.sin(a)))
        self._drag(QPointF(handle), points)
        # Recompute expected from the same arc. 6 steps * 15° = 90°.
        self.assertAlmostEqual(self.item.angle, 90, delta=6.0)
        self.assertAlmostEqual(self.item.cx, cx, delta=2.0)
        self.assertAlmostEqual(self.item.cy, cy, delta=2.0)
        self.assertAlmostEqual(self.item.w, 200, delta=0.5)
        # The broken mapping swung the angle the wrong way on the first moves.
        self.assertGreater(self.item.angle, 60)

    def test_zoomed_out_corner_resize_follows_scene_delta(self):
        self._place(0.2)
        corner = QPointF(self.item.handles["br"].pos())
        self._drag(corner, [
            QPointF(corner.x() + 20, corner.y()),
            QPointF(corner.x() + 40, corner.y()),
        ])
        self.assertAlmostEqual(self.item.w, 240, delta=8.0)
        self.assertAlmostEqual(self.item.h, 100, delta=8.0)
        self.assertAlmostEqual(self.item.angle, 0, delta=1.0)
        edge = _edge_px(self.bbox, self.item.image_rect, 0, 1)
        self.assertAlmostEqual(edge, self.item.w, delta=1.0)

    def test_handle_hit_pad_is_usable_at_low_zoom(self):
        self._place(0.2)
        handle = self.item.handles["br"]
        base = self.view.view.mapFromScene(handle.pos())
        view = self.view.view
        self.assertIs(view.itemAt(QPoint(int(base.x()) + 10, int(base.y()))), handle)
        self.assertIs(view.itemAt(QPoint(int(base.x()), int(base.y()) + 10)), handle)
        self.assertIsNot(view.itemAt(QPoint(int(base.x()) + 18, int(base.y()))), handle)
        self.assertGreater(HANDLE_HIT_SIZE, HANDLE_VISUAL_SIZE)
        # shape() is the grab target; it must extend past the painted dot.
        self.assertTrue(handle.shape().contains(QPointF(HANDLE_VISUAL_SIZE, 0)))
        self.assertFalse(handle.shape().contains(QPointF(HANDLE_HIT_SIZE, 0)))


class RectAndPolygonDragTests(unittest.TestCase):
    def setUp(self):
        self.app = _app()
        self.view = _ScaledView(0.2)

    def tearDown(self):
        _release_grab(self.view.view)
        self.view.view.close()

    def test_rect_resize_at_low_zoom_does_not_use_handle_size(self):
        bbox = BBox(id=0, class_id=0, type="rect", x_center=0.5, y_center=0.5, width=0.2, height=0.1)
        img = QRectF(0, 0, 1000, 800)
        pixel_w = 200
        pixel_h = 80
        item = BBoxItem(QRectF(0, 0, pixel_w, pixel_h), bbox)
        item.setPos(400, 300)
        item.set_image_rect(img)
        self.view.view.scene().addItem(item)
        QApplication.processEvents()
        right = item.handles["r"].pos()
        press = item.mapToScene(right)
        self.view.center_and_send(QEvent.MouseButtonPress, press)
        self.view.center_and_send(QEvent.MouseMove, QPointF(press.x() + 50, press.y()))
        self.view.center_and_send(QEvent.MouseButtonRelease, QPointF(press.x() + 50, press.y()))
        item._sync_to_yolo()
        self.assertAlmostEqual(item.rect().width(), 250, delta=8.0)
        self.assertAlmostEqual(bbox.width * img.width(), item.rect().width(), delta=1.0)
        self.assertAlmostEqual(bbox.height * img.height(), pixel_h, delta=1.0)
        self.assertGreater(item.sceneBoundingRect().width(), item.rect().width())

    def test_polygon_vertex_follows_scene_delta_at_low_zoom(self):
        bbox = BBox(id=0, class_id=0, type="polygon", points=[])
        img = QRectF(0, 0, 1000, 800)
        points = [QPointF(100, 100), QPointF(300, 120), QPointF(200, 280)]
        item = PolygonItem(points, bbox)
        item.set_image_rect(img)
        self.view.view.scene().addItem(item)
        QApplication.processEvents()
        origin = QPointF(item.vertices[1])
        self.view.center_and_send(QEvent.MouseButtonPress, origin)
        target = QPointF(origin.x() + 40, origin.y() - 25)
        self.view.center_and_send(QEvent.MouseMove, target)
        self.view.center_and_send(QEvent.MouseButtonRelease, target)
        self.assertAlmostEqual(item.vertices[1].x(), origin.x() + 40, delta=8.0)
        self.assertAlmostEqual(item.vertices[1].y(), origin.y() - 25, delta=8.0)
        self.assertAlmostEqual(item.vertices[0].x(), 100, delta=0.5)
        nx = bbox.points[1][0] * img.width() + img.left()
        self.assertAlmostEqual(nx, item.vertices[1].x(), delta=0.5)


def _edge_px(bbox, img, i, j):
    p0, p1 = bbox.points[i], bbox.points[j]
    return math.hypot((p1[0] - p0[0]) * img.width(), (p1[1] - p0[1]) * img.height())


if __name__ == "__main__":
    unittest.main()
