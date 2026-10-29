import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_VARS = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")
THEME_VARS = ("GTK_THEME", "QT_STYLE_OVERRIDE", "GSETTINGS_BACKEND")


def _run(code, preset=None, gtk_ini=None, **env_vars):
    home = tempfile.mkdtemp()
    if gtk_ini:
        ini_dir = os.path.join(home, "gtk-3.0")
        os.makedirs(ini_dir)
        with open(os.path.join(ini_dir, "settings.ini"), "w", encoding="utf-8") as fh:
            fh.write(gtk_ini)
    env = {k: v for k, v in os.environ.items() if k not in LOCALE_VARS + THEME_VARS}
    env.update(env_vars)
    env["HOME"] = home
    env["XDG_CONFIG_HOME"] = home
    env["GSETTINGS_BACKEND"] = "memory"
    env.setdefault("LANG", "C")
    env.setdefault("LC_ALL", "C")
    if preset:
        env["PRESET_THEME"] = preset
    script = textwrap.dedent(
        """
        import os
        from PyQt5.QtCore import QSettings
        preset = os.environ.get("PRESET_THEME", "")
        if preset:
            settings = QSettings("YOLOTxtMaker", "YOLOTxtMaker")
            settings.setValue("theme", preset)
            settings.sync()
        from ui.theme_manager import init_saved_theme, load_saved_theme_id
        print(init_saved_theme())
        saved = load_saved_theme_id()
        print("SAVED=" + ("" if saved is None else saved))
        """
    )
    out = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
    chosen = lines[0]
    saved = ""
    for line in lines[1:]:
        if line.startswith("SAVED="):
            saved = line.split("=", 1)[1]
    return chosen, saved


class ThemeDefaultTest(unittest.TestCase):
    def test_unset_theme_is_light(self):
        chosen, saved = _run("")
        self.assertEqual(chosen, "light_blue")
        self.assertEqual(saved, "")

    def test_saved_dark_theme_is_kept(self):
        chosen, saved = _run("", preset="deep_blue")
        self.assertEqual(chosen, "deep_blue")
        self.assertEqual(saved, "deep_blue")

    def test_saved_choice_beats_dark_desktop(self):
        chosen, _saved = _run("", preset="light_pink", GTK_THEME="Adwaita:dark")
        self.assertEqual(chosen, "light_pink")

    def test_dark_desktop_is_used_when_unset(self):
        chosen, saved = _run("", GTK_THEME="Adwaita:dark")
        self.assertEqual(chosen, "deep_blue")
        self.assertEqual(saved, "")

    def test_gtk_settings_ini_requests_dark(self):
        chosen, _saved = _run("", gtk_ini="[Settings]\ngtk-application-prefer-dark-theme=1\n")
        self.assertEqual(chosen, "deep_blue")

    def test_invalid_saved_theme_falls_back_to_light(self):
        chosen, saved = _run("", preset="not-a-theme")
        self.assertEqual(chosen, "light_blue")
        self.assertEqual(saved, "")


if __name__ == "__main__":
    unittest.main()
