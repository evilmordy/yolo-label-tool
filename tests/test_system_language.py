import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALE_VARS = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")


def detect(**env_vars):
    """Run system_language() in a fresh process with only the given locale vars."""
    env = {k: v for k, v in os.environ.items() if k not in LOCALE_VARS}
    env.update(env_vars)
    out = subprocess.run(
        [sys.executable, "-c",
         "from core.settings_manager import system_language; print(system_language())"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


@unittest.skipUnless(sys.platform.startswith("linux"), "locale env vars are a Linux thing")
class SystemLanguageTest(unittest.TestCase):
    def test_chinese_locale(self):
        self.assertEqual(detect(LANG="zh_CN.UTF-8"), "zh")
        self.assertEqual(detect(LANG="zh_TW.UTF-8"), "zh")

    def test_japanese_locale(self):
        self.assertEqual(detect(LANG="ja_JP.UTF-8"), "ja")

    def test_other_locales_fall_back_to_english(self):
        self.assertEqual(detect(LANG="en_US.UTF-8"), "en")
        self.assertEqual(detect(LANG="de_DE.UTF-8"), "en")
        self.assertEqual(detect(LANG="C"), "en")
        self.assertEqual(detect(), "en")

    def test_lc_all_overrides_lang(self):
        self.assertEqual(detect(LANG="zh_CN.UTF-8", LC_ALL="en_US.UTF-8"), "en")

    def test_clean_settings_follow_c_locale(self):
        self.assertEqual(load_language_in_env(LANG="C", LC_ALL="C"), "en")

    def test_saved_language_overrides_c_locale(self):
        self.assertEqual(load_language_in_env(LANG="C", LC_ALL="C", preset="zh"), "zh")


def load_language_in_env(preset=None, **env_vars):
    home = tempfile.mkdtemp()
    env = {k: v for k, v in os.environ.items() if k not in LOCALE_VARS}
    env.update(env_vars)
    env["HOME"] = home
    env["XDG_CONFIG_HOME"] = home
    if preset:
        env["PRESET_LANG"] = preset
    script = textwrap.dedent(
        """
        import os
        from PyQt5.QtCore import QSettings
        preset = os.environ.get("PRESET_LANG", "")
        if preset:
            settings = QSettings("YOLOTxtMaker", "YOLOTxtMaker")
            settings.setValue("language", preset)
            settings.sync()
        from core.settings_manager import load_language
        print(load_language())
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
    return out.stdout.strip()


if __name__ == "__main__":
    unittest.main()
