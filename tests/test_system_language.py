import os
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
