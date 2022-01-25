from typer import colors, echo, secho, style

COLORS = {
    "blue": colors.BLUE,
    "cyan": colors.CYAN,
    "green": colors.GREEN,
    "magenta": colors.MAGENTA,
    "red": colors.RED,
    "yellow": colors.YELLOW,
    "white": colors.WHITE,
}


def color(text, color="magenta", echo=False, bold=False):
    text = f"{text:,}" if isinstance(text, int) else str(text)
    return (
        secho(text, fg=COLORS[color], bold=bold)
        if echo
        else style(text, fg=COLORS[color], bold=bold)
    )


def print_item(index, total, message, prefix="- "):
    echo(f"{prefix} ({(index + 1):,}/{total}) {message}")
