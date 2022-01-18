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


def color(text, color="magenta", echo=False):
    text = f"{text:,}" if isinstance(text, int) else str(text)
    return secho(text, fg=COLORS[color]) if echo else style(text, fg=COLORS[color])


def print_item(index, total, message):
    echo(f"- ({(index + 1):,}/{total}) {message}")
