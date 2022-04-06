from pprint import PrettyPrinter
from typing import Any

from inflect import engine
from typer import colors, echo, style

COLORS = {
    "blue": colors.BLUE,
    "cyan": colors.CYAN,
    "green": colors.GREEN,
    "magenta": colors.MAGENTA,
    "red": colors.RED,
    "yellow": colors.YELLOW,
    "white": colors.WHITE,
}


def color(text: Any, color="magenta", bold=False, use_comma=True) -> str:
    if use_comma:
        text = f"{text:,}" if isinstance(text, int) else str(text)
    return style(text, fg=COLORS[color], bold=bold)


def print_item(index: int, total: int, message: str, prefix=""):
    if not prefix:
        prefix = "-"
    echo(f"{prefix} ({(index + 1):,}/{total:,}) {message}")


def pprint(item: object):
    if isinstance(item, list):
        for item in item[:5]:
            PrettyPrinter().pprint(vars(item))
    else:
        PrettyPrinter().pprint(vars(item))


def pluralize(string: str, condition=None):
    return engine().plural(string, condition)
