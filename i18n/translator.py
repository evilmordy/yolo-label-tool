from i18n.locales import zh, en, ja

_LOCALES = {
    "zh": zh.STRINGS,
    "en": en.STRINGS,
    "ja": ja.STRINGS,
}

_current_language = "zh"
_callbacks = []


def init_language(lang: str):
    set_language(lang)


def get_language() -> str:
    return _current_language


def set_language(lang: str):
    global _current_language
    if lang not in _LOCALES:
        lang = "zh"
    if lang == _current_language:
        return
    _current_language = lang
    for cb in _callbacks:
        cb(lang)


def on_language_changed(callback):
    _callbacks.append(callback)


def tr(key: str, **kwargs) -> str:
    strings = _LOCALES.get(_current_language, _LOCALES["zh"])
    text = strings.get(key, _LOCALES["zh"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
