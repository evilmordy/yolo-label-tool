#!/usr/bin/env bash
# 构建后的启动检查，对齐 AppImageHub：C 语言、无深色桌面、xcb 插件依赖必须来自包内。
# 宿主上装过 libxcb-icccm 也不算通过，动态链接器得从 one-file 的解压目录加载它。
set -euo pipefail

# 调用方若开着 LD_DEBUG，dirname/cd 的调试输出会混进命令替换。
unset LD_DEBUG LD_DEBUG_OUTPUT || true

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export SMOKE_ROOT="$ROOT"
APPIMAGE="$(readlink -f "${1:-"$ROOT/YOLOTxtMaker.AppImage"}")"
SCRIPT="$(readlink -f "$0")"

if [[ ! -f "$APPIMAGE" ]]; then
  echo "AppImage not found: $APPIMAGE" >&2
  exit 1
fi

# Hub 用 runtime --appimage-updateinformation 读 ELF .upd_info，不启动界面。
# 下载文件名保持 YOLOTxtMaker.AppImage，zsync 必须放在它旁边。
# APPIMAGE_EXTRACT_AND_RUN 会让 runtime 直接跑程序，所以这里先关掉。
UPDATE_INFO=$(env -u APPIMAGE_EXTRACT_AND_RUN "$APPIMAGE" --appimage-updateinformation 2>/dev/null | tr -d '\000' | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' || true)
if [[ ! "$UPDATE_INFO" =~ ^gh-releases-zsync\|[^|]+\|[^|]+\|latest\|YOLOTxtMaker\.AppImage\.zsync$ ]]; then
  echo "AppImage update information is missing or unexpected: ${UPDATE_INFO:-<empty>}" >&2
  exit 1
fi
echo "Update information: $UPDATE_INFO"
ZSYNC="${APPIMAGE}.zsync"
if [[ ! -s "$ZSYNC" ]]; then
  echo "Missing zsync next to the AppImage: $ZSYNC" >&2
  exit 1
fi
if ! grep -a -q 'Filename: YOLOTxtMaker.AppImage' "$ZSYNC"; then
  echo "zsync file does not name YOLOTxtMaker.AppImage" >&2
  exit 1
fi

if [[ "${SMOKE_INNER:-}" != 1 ]]; then
  export SMOKE_INNER=1
  exec xvfb-run -a -s "-screen 0 1280x800x24" bash "$SCRIPT" "$APPIMAGE"
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# AppRun 解出来的才是 Hub 会跑的那份二进制。
EXTRACT="$WORK/extract"
mkdir -p "$EXTRACT"
(
  cd "$EXTRACT"
  APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGE" --appimage-extract >/dev/null
)
INNER="$EXTRACT/squashfs-root/usr/bin/YOLOTxtMaker"
META="$EXTRACT/squashfs-root/usr/share/metainfo/com.evilmordy.yolotxtmaker.appdata.xml"
test -x "$INNER"
test -L "$EXTRACT/squashfs-root/AppRun"
test "$(readlink "$EXTRACT/squashfs-root/AppRun")" = "usr/bin/YOLOTxtMaker"
test -f "$META"
test -e "$EXTRACT/squashfs-root/.DirIcon"

python3 - "$INNER" "$ROOT" <<'PY'
import sys
from pathlib import Path

binary = Path(sys.argv[1])
root = Path(sys.argv[2])
sys.path.insert(0, str(root))
from PyInstaller.archive.readers import CArchiveReader
from appimage.linux_qt_libs import REQUIRED_SONAMES

reader = CArchiveReader(str(binary))
names = {Path(name).name for name in reader.toc}
missing = [soname for soname in REQUIRED_SONAMES if soname not in names]
if missing:
    print("AppImage is missing Qt platform libraries:", ", ".join(missing))
    raise SystemExit(1)
banned = [name for name in names if name == "libxcb.so.1" or name.startswith("libxcb-dri")]
if banned:
    print("AppImage bundles driver-tied xcb libraries:", ", ".join(banned))
    raise SystemExit(1)
print("Archive contains Qt platform libraries:", ", ".join(REQUIRED_SONAMES))
PY

# 干净的家目录：没有保存过的语言/主题。memory 后端避免读到构建机自己的深色配置。
export HOME="$WORK/home"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_RUNTIME_DIR="$HOME/run"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
export LANG=C LC_ALL=C LANGUAGE=C
unset GTK_THEME QT_STYLE_OVERRIDE || true
export GSETTINGS_BACKEND=memory
export QT_DEBUG_PLUGINS=1
export QT_QPA_PLATFORM=xcb
export LIBGL_ALWAYS_SOFTWARE=1
export APPIMAGE_EXTRACT_AND_RUN=1

STDERR="$WORK/stderr.txt"
STDOUT="$WORK/stdout.txt"
LAUNCH=( "$APPIMAGE" )
if unshare -Urn true >/dev/null 2>&1; then
  # 无网络命名空间。X11 套接字仍在，不依赖联网才能出窗口。
  LAUNCH=( unshare -Urn "$APPIMAGE" )
  echo "Starting under unshare -Urn (no network)"
else
  echo "NOTE: unshare -Urn is unavailable; startup itself does not use the network"
fi

# 只让应用进程打加载日志，避免 xwininfo/convert 的系统库加载混进来。
env LD_DEBUG=libs LD_DEBUG_OUTPUT="$WORK/lddebug" "${LAUNCH[@]}" >"$STDOUT" 2>"$STDERR" &
PID=$!

cleanup_app() {
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
}
trap 'cleanup_app; rm -rf "$WORK"' EXIT

TREE="$WORK/tree.txt"
found=0
for _ in $(seq 1 25); do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "AppImage exited before showing a window" >&2
    cat "$STDERR" >&2 || true
    exit 1
  fi
  xwininfo -root -tree >"$TREE" 2>/dev/null || true
  if grep -q "YOLO Label Tool" "$TREE"; then
    found=1
    break
  fi
  sleep 1
done

if [[ "$found" != 1 ]]; then
  echo "English window title did not appear within 25s" >&2
  cat "$TREE" >&2 || true
  echo "----- stderr -----" >&2
  cat "$STDERR" >&2 || true
  exit 1
fi

# 窗口已经在了再停几秒，确认不是闪一下就退出。
sleep 5
if ! kill -0 "$PID" 2>/dev/null; then
  echo "AppImage exited shortly after showing a window" >&2
  cat "$STDERR" >&2 || true
  exit 1
fi

if grep -qE "标注|图片列表|保存路径|文件" "$TREE"; then
  echo "C locale showed Chinese UI:" >&2
  cat "$TREE" >&2
  exit 1
fi

if grep -F "Could not load the Qt platform plugin" "$STDERR" \
  || grep -F "This application failed to start" "$STDERR" \
  || grep -F "error while loading shared libraries" "$STDERR"; then
  echo "Qt platform / loader error on stderr" >&2
  cat "$STDERR" >&2
  exit 1
fi
# 可选插件（wayland 等）加载失败没关系；xcb 平台插件不行。
if grep -F "libqxcb.so" "$STDERR" | grep -E "cannot open shared object|Could not load|QLibraryPrivate::loadPlugin failed"; then
  echo "libqxcb.so failed to load" >&2
  cat "$STDERR" >&2
  exit 1
fi

xwd -root -silent -out "$WORK/root.xwd"
convert "$WORK/root.xwd" "$WORK/root.png"
MEAN="$(convert "$WORK/root.png" -format '%[fx:mean]' info:)"
python3 - "$MEAN" <<'PY'
import sys
mean = float(sys.argv[1])
print(f"Window luminance mean: {mean:.3f}")
# 浅色主题大约 0.6（窗口盖住大部分黑底）。深色主题停在 0.1 附近。
if mean < 0.35:
    raise SystemExit("window is mostly dark; expected the light default theme")
PY

python3 - "$WORK" <<'PY'
import os
import sys
from pathlib import Path

work = Path(sys.argv[1])
logs = sorted(work.glob("lddebug.*"))
if not logs:
    raise SystemExit("LD_DEBUG trace missing; cannot prove bundled xcb libraries were used")
text = "\n".join(path.read_text(errors="ignore") for path in logs)
root = Path(os.environ["SMOKE_ROOT"])
sys.path.insert(0, str(root))
from appimage.linux_qt_libs import REQUIRED_SONAMES

def bundled_init(soname: str):
    # xwininfo 等检查工具也会打出 LD_DEBUG，它们从系统目录加载同名库。
    # 只认应用自己 calling init 的 _MEI 路径。
    found = None
    for line in text.splitlines():
        marker = "calling init:"
        if marker not in line or "/_MEI" not in line:
            continue
        path = line.split(marker, 1)[1].strip().split()[0]
        if os.path.basename(path) == soname:
            found = path
    return found

bad = []
for soname in REQUIRED_SONAMES:
    used = bundled_init(soname)
    if not used:
        bad.append(soname)
    else:
        print(f"loaded {soname} from bundle ({used})")
if bad:
    print("These libraries were not loaded from the AppImage:")
    print("\n".join(bad))
    raise SystemExit(1)
PY

echo "Smoke test passed"
cleanup_app
trap 'rm -rf "$WORK"' EXIT
