"""Filename ordering where numeric runs compare as integers."""
import re
from pathlib import Path

_TOKEN = re.compile(r"(\d+)")


def natural_sort_key(name: str):
    parts = _TOKEN.split(str(name))
    key = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part.casefold()))
    return tuple(key)


def natural_sorted(paths):
    def sort_key(path):
        name = Path(path).name
        # Name breaks ties (img2 vs img02) so folder order does not depend on
        # filesystem iteration order.
        return (natural_sort_key(name), name.casefold())

    return sorted(paths, key=sort_key)
