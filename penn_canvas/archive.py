from datetime import datetime
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

from pandas import DataFrame
from typer import echo, progressbar

from .helpers import colorize, get_canvas, get_command_paths


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


COMMAND = "Discussion Archive"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]


def get_discussions(course_id, canvas):
    echo(") Finding discussions...")

    course = canvas.get_course(course_id)
    discussions = [discussion for discussion in course.get_discussion_topics()]

    return course, discussions, len(discussions)


def archive_main(course_id, instance, verbose, use_timestamp):
    def archive_discussion(discussion, verbose=False, index=0, total=0):
        def process_entry(
            entry,
            verbose,
            discussion_index,
            total_discussions,
            entry_index,
            total_entries,
        ):
            user = " ".join(entry.user["display_name"].split())
            user_id = entry.user["id"]
            canvas_user = CANVAS.get_user(user_id)
            email = canvas_user.email
            message = " ".join(
                strip_tags(entry.message.replace("\n", " ")).strip().split()
            )
            timestamp = (
                datetime.strptime(entry.created_at, "%Y-%m-%dT%H:%M:%SZ").strftime(
                    "%m/%d/%Y, %H:%M:%S"
                )
                if use_timestamp
                else ""
            )

            if verbose:
                user_display = colorize(user, "cyan")
                timestamp_display = (
                    colorize(timestamp, "yellow") if use_timestamp else ""
                )
                email_display = colorize(email, "yellow") if not use_timestamp else ""
                discussion_display = colorize(discussion.title.upper(), "magenta")

                if entry_index == 0:
                    echo(f"==== DISCUSSION {discussion_index + 1} ====")

                echo(
                    f"- [{discussion_index + 1}/{total_discussions}]"
                    f" ({entry_index + 1}/{total_entries}) {discussion_display}"
                    f" {user_display} {timestamp_display if use_timestamp else email_display} {message[:40]}..."
                )

            if use_timestamp:
                return [user, email, timestamp, message]
            else:
                return [user, email, message]

        discussion_path = (
            COURSE / f"{discussion.title.replace('- ', '').replace(' ', '_')}.csv"
        )
        entries = [entry for entry in discussion.get_topic_entries()]

        if not entries:
            echo(f"==== DISCUSSION {index + 1} ====")
            echo("- NO ENTRIES")

        entries = [
            process_entry(entry, verbose, index, total, entry_index, len(entries))
            for entry_index, entry in enumerate(entries)
        ]

        columns = ["index", "User", "Email", "Timestamp", "Post"]
        columns.remove("index")

        if not use_timestamp:
            columns.remove("Timestamp")

        entries = DataFrame(entries, columns=columns)
        entries.to_csv(discussion_path, index=False)

    CANVAS = get_canvas(instance)
    course, discussions, total = get_discussions(course_id, CANVAS)

    COURSE = RESULTS / f"{course.name}"

    if not COURSE.exists():
        Path.mkdir(COURSE)

    echo(") Processing discussions...")

    if verbose:
        for index, discussion in enumerate(discussions):
            archive_discussion(discussion, True, index, total)
    else:
        with progressbar(discussions, length=total) as progress:
            for discussion in progress:
                archive_discussion(discussion)

    colorize("SUMMARY", "yellow", True)
    echo(
        f"- Archived {colorize(total, 'magenta')} discussions for"
        f" {colorize(course.name, 'blue')}."
    )
    colorize("FINISHED", "yellow", True)
