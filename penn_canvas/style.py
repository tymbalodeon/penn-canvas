from pprint import PrettyPrinter

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


def color(text, color="magenta", bold=False, use_comma=True) -> str:
    if use_comma:
        text = f"{text:,}" if isinstance(text, int) else str(text)
    return style(text, fg=COLORS[color], bold=bold)


def print_item(index, total, message, prefix="-"):
    echo(f"{prefix} ({(index + 1):,}/{total:,}) {message}")


def pprint(thing: object):
    if isinstance(thing, list):
        for item in thing[:5]:
            PrettyPrinter().pprint(vars(item))
    else:
        PrettyPrinter().pprint(vars(thing))


def pluralize(string: str, condition=None):
    return engine().plural(string, condition)
