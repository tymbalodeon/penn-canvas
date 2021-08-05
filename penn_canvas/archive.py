from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

from pandas import DataFrame
from typer import echo, progressbar

from .helpers import (
    TODAY_AS_Y_M_D,
    colorize,
    get_canvas,
    get_start_index,
    make_csv_paths,
    make_skip_message,
    toggle_progress_bar,
)


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    stripper = HTMLStripper()
    stripper.feed(html)

    return stripper.get_data()


COMMAND_DIRECTORY = Path.home() / f"penn-canvas/archive"
RESULTS = COMMAND_DIRECTORY / "results"
HEADERS = ["index", "user", "timestamp", "post"]


def get_discussions(course_id, instance):
    canvas = get_canvas(instance)

    echo(") Finding discussions...")

    course = canvas.get_course(course_id)
    discussions = course.get_discussion_topics()
    total = 0

    for discussion in discussions:
        total += 1

    return discussions, total


def archive_main(course_id, instance, verbose, force):
    def archive_discussion(discussion, verbose=False):
        discussion_path = RESULTS / f"{discussion.title.strip().replace(' ', '_')}.csv"
        entries = discussion.get_topic_entries()

        def process_entry(entry, verbose):
            user = " ".join(entry.user["display_name"].split())
            timestamp = entry.created_at
            message = strip_tags(entry.message.replace("\n", " ")).strip()

            if verbose:
                user_display = colorize(user, "cyan")
                timestamp_display = colorize(timestamp, "yellow")
                discussion_display = colorize(discussion.title.upper(), "magenta")
                echo(
                    f"- {discussion_display} {user_display} {timestamp_display} {message[:88]}"
                )

            return [user, timestamp, message]

        entries = [process_entry(entry, verbose) for entry in entries]
        entries = DataFrame(entries, columns=["user", "timestamp", "post"])
        entries.to_csv(discussion_path, index=False)

    discussions, total = get_discussions(course_id, instance)

    if not COMMAND_DIRECTORY.exists():
        Path.mkdir(COMMAND_DIRECTORY)

        if not RESULTS.exists():
            Path.mkdir(RESULTS)

    echo(") Processing discussions...")

    if verbose:
        for discussion in discussions:
            archive_discussion(discussion, True)
    else:
        with progressbar(discussions, length=total) as progress:
            for discussion in progress:
                archive_discussion(discussion)
