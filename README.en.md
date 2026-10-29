# YOLO Label Tool (YOLOTxtMaker)

YOLO Label Tool (download name `YOLOTxtMaker`; git repository `yolo-label-tool`) is a desktop tool for drawing YOLO labels: axis-aligned boxes, oriented boxes, and polygons. Releases ship as `YOLOTxtMaker` (Windows `.exe`, Linux `.AppImage`, macOS `.app`).

Labels are written into the save folder you pick. On first launch, or if that folder is gone, choose **Set Save Path** before opening an image or a folder. The choice is remembered.

## Install

- **Linux:** download `YOLOTxtMaker.AppImage` from the [releases](https://github.com/evilmordy/yolo-label-tool/releases), then `chmod +x YOLOTxtMaker.AppImage` and run it. The same release includes `YOLOTxtMaker.AppImage.zsync` for AppImageUpdate.
- **Windows:** download `YOLOTxtMaker.exe` and run it.
- **macOS:** download `YOLOTxtMaker-mac.zip`, unzip, and open `YOLOTxtMaker.app`.

From a checkout: install `PyQt5` and run `python main.py`.

## Language and theme

The interface follows the system language. Chinese and Japanese locales use those translations; every other locale, including the C locale, uses English. A language chosen in Settings is kept.

The window starts in a light theme, or in the dark theme when the system asks for dark mode. The Theme menu can still switch among Light Blue, Light Pink, and Deep Blue.

## Background images

A missing `.txt` means the image is not labeled yet. An empty `.txt` in the save folder means the image is a background (no objects) and can be used as a negative sample. Press **B**, or use **File → Mark as Background**, to write that empty file. **Ctrl+Z** undoes it.

## Shortcuts

| Key | Action |
|-----|--------|
| **R** / **O** / **P** | New box is a rectangle, an oriented box, or a polygon |
| **Enter** / **Esc** | Close the polygon (at least 3 points) / cancel it |
| **Ctrl+S** | Save the current image |
| **B** | Mark the current image as background |
| **Ctrl+Z** | Undo |
| **A** / **Delete** | Add a box / delete the selected box |
| **Left** / **Right** | Previous / next image |

Shortcuts can be changed under Settings.
