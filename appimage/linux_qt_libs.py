"""Bundle the Qt xcb plugin's system libraries into a PyInstaller binary.

PyInstaller ships ``libqxcb.so`` but drops ``libxcb.so.*`` and ``libxcb-dri*``
(they follow the graphics driver) and never packages a dependency the build
machine does not have. AppImageHub's Ubuntu image has no xcb-util split
packages, so the plugin dies with ``libxcb-icccm.so.4: cannot open shared
object file`` before a window exists. Installing those packages on the runner
is not enough: firejail only sees what is inside the AppImage.

Walk ``ldd`` from the platform plugin and stage every ``libxcb-*`` (except
dri*) and ``libxkbcommon*`` under its SONAME, at the top of the one-file
archive, where the bootloader's ``LD_LIBRARY_PATH`` can see it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Fail the build if any of these are absent, instead of discovering the gap
# on the next Hub retest. Transitive (libxcb-util via libxcb-image, libxcb-glx
# via the GLX integration plugin) are included on purpose.
REQUIRED_SONAMES = (
    "libxcb-glx.so.0",
    "libxcb-icccm.so.4",
    "libxcb-image.so.0",
    "libxcb-keysyms.so.1",
    "libxcb-randr.so.0",
    "libxcb-render-util.so.0",
    "libxcb-render.so.0",
    "libxcb-shape.so.0",
    "libxcb-shm.so.0",
    "libxcb-sync.so.1",
    "libxcb-util.so.1",
    "libxcb-xfixes.so.0",
    "libxcb-xinerama.so.0",
    "libxcb-xkb.so.1",
    "libxkbcommon-x11.so.0",
    "libxkbcommon.so.0",
)

_SKIP_EXACT = {"libxcb.so.1"}
_SKIP_PREFIXES = ("libxcb-dri",)


def want_bundled(soname: str) -> bool:
    """True for xcb/xkb libraries that are safe to ship and easy to miss."""
    if soname in _SKIP_EXACT or soname.startswith(_SKIP_PREFIXES):
        return False
    return soname.startswith("libxcb-") or soname.startswith("libxkbcommon")


def _plugin_seeds() -> list[Path]:
    try:
        import PyQt5
    except ImportError as exc:
        raise SystemExit("PyQt5 is not installed; cannot locate libqxcb.so") from exc

    base = Path(PyQt5.__file__).resolve().parent
    roots = [base / "Qt5" / "plugins", base / "Qt" / "plugins"]
    root = next((path for path in roots if path.is_dir()), None)
    if root is None:
        raise SystemExit(f"Qt plugins directory not found under {base}")

    seeds: list[Path] = []
    for name in ("platforms", "xcbglintegrations", "platforminputcontexts"):
        directory = root / name
        if directory.is_dir():
            seeds.extend(sorted(directory.glob("*.so")))
    qxcb = [path for path in seeds if path.name == "libqxcb.so"]
    if not qxcb:
        raise SystemExit(f"libqxcb.so not found under {root}")
    return seeds


def _ldd(path: Path) -> list[tuple[str, Path]]:
    try:
        proc = subprocess.run(
            ["ldd", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise SystemExit("ldd is required to collect Qt platform libraries") from None

    found = []
    for line in proc.stdout.splitlines():
        if "=>" not in line:
            continue
        soname, rest = line.split("=>", 1)
        soname = soname.strip()
        rest = rest.strip()
        if not soname or rest.startswith("not found"):
            continue
        libpath = rest.split()[0]
        if libpath.startswith("/"):
            found.append((soname, Path(libpath)))
    return found


def qt_platform_binaries() -> list[tuple[str, str]]:
    """PyInstaller ``binaries`` entries ``(source, dest_dir)`` for this platform."""
    if not sys.platform.startswith("linux"):
        return []

    chosen: dict[str, Path] = {}
    queue = _plugin_seeds()
    seen: set[Path] = set()
    while queue:
        current = queue.pop()
        try:
            key = current.resolve()
        except OSError:
            key = current
        if key in seen or not current.exists():
            continue
        seen.add(key)
        for soname, libpath in _ldd(current):
            queue.append(libpath)
            if want_bundled(soname):
                chosen.setdefault(soname, libpath)

    missing = [name for name in REQUIRED_SONAMES if name not in chosen]
    if missing:
        raise SystemExit(
            "Qt xcb libraries missing on this build machine. Install the matching "
            "libxcb / libxkbcommon packages and rebuild: " + ", ".join(missing)
        )

    # ldd may print either the SONAME symlink or libfoo.so.N.N.N. The loader
    # asks for the SONAME, so the archived basename has to be that name.
    stage = Path(tempfile.mkdtemp(prefix="yolo-qt-xcb-"))
    binaries = []
    for soname in sorted(chosen):
        src = chosen[soname]
        dest = stage / soname
        shutil.copyfile(src, dest)
        binaries.append((str(dest), "."))
    print("Bundling Qt platform libraries: " + ", ".join(sorted(chosen)), flush=True)
    return binaries
