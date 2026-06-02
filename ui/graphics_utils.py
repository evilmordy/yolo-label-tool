"""Shared helpers for QGraphicsItem selection."""

BBOX_ROOT_TYPES = None


def _bbox_root_types():
    global BBOX_ROOT_TYPES
    if BBOX_ROOT_TYPES is None:
        from ui.bbox_item import BBoxItem
        from ui.obb_item import OBBItem
        from ui.polygon_item import PolygonItem
        BBOX_ROOT_TYPES = (BBoxItem, OBBItem, PolygonItem)
    return BBOX_ROOT_TYPES


def resolve_bbox_root(item):
    """Walk up parent chain to BBoxItem/OBBItem/PolygonItem."""
    if item is None:
        return None
    bbox_roots = _bbox_root_types()
    current = item
    while current is not None:
        if isinstance(current, bbox_roots):
            return current
        current = current.parentItem()
    return None


def pick_preferred_bbox_root(selected_items):
    """When multiple items are selected, prefer highest z then largest bbox id."""
    roots = []
    seen = set()
    for item in selected_items:
        root = resolve_bbox_root(item)
        if root is not None and id(root) not in seen:
            seen.add(id(root))
            roots.append(root)
    if not roots:
        return None
    if len(roots) == 1:
        return roots[0]
    return max(
        roots,
        key=lambda r: (r.zValue(), r.bbox_data.id if r.bbox_data else -1),
    )


def select_only(item):
    """Clear scene selection then select this item (or its parent for handles)."""
    scene = item.scene()
    if scene is not None:
        scene.clearSelection()
    item.setSelected(True)


def select_only_parent(parent_item):
    """Clear scene selection then select the parent bbox item."""
    scene = parent_item.scene()
    if scene is not None:
        scene.clearSelection()
    parent_item.setSelected(True)
