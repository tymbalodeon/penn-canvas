from enum import Enum
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


class Color(Enum):
    BLACK = "black"
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    BLUE = "blue"
    MAGENTA = "magenta"
    CYAN = "cyan"
    WHITE = "white"
    RESET = "reset"
    BRIGHT_BLACK = "bright_black"
    BRIGHT_RED = "bright_red"
    BRIGHT_GREEN = "bright_green"
    BRIGHT_YELLOW = "bright_yellow"
    BRIGHT_BLUE = "bright_blue"
    BRIGHT_MAGENTA = "bright_magenta"
    BRIGHT_CYAN = "bright_cyan"
    BRIGHT_WHITE = "bright_white"


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


def pluralize(string: str, condition=None) -> str:
    return engine().plural(string, condition)
