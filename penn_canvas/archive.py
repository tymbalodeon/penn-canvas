from datetime import datetime
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

from pandas import DataFrame
from typer import echo, progressbar

from .helpers import color, get_canvas, get_command_paths


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


COMMAND = "Archive"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]


def get_discussions(course):
    echo(") Finding discussions...")

    discussions = [discussion for discussion in course.get_discussion_topics()]

    return discussions, len(discussions)


def get_quizzes(course):
    echo(") Finding quizzes...")

    quizzes = [quiz for quiz in course.get_quizzes()]

    return quizzes, len(quizzes)


def archive_main(course_id, instance, verbose, use_timestamp, exclude_quizzes):
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
                user_display = color(user, "cyan")
                timestamp_display = color(timestamp, "yellow") if use_timestamp else ""
                email_display = color(email, "yellow") if not use_timestamp else ""
                discussion_display = color(discussion.title.upper(), "magenta")

                if entry_index == 0:
                    echo(f"==== DISCUSSION {discussion_index + 1} ====")

                echo(
                    f"- [{discussion_index + 1}/{total_discussions}]"
                    f" ({entry_index + 1}/{total_entries}) {discussion_display}"
                    f" {user_display}"
                    f" {timestamp_display if use_timestamp else email_display}"
                    f" {message[:40]}..."
                )

            if use_timestamp:
                return [user, email, timestamp, message]
            else:
                return [user, email, message]

        discussion_path = (
            DISCUSSION_DIRECTORY
            / f"{discussion.title.replace('- ', '').replace(' ', '_')}.csv"
        )
        entries = [entry for entry in discussion.get_topic_entries()]

        if verbose and not entries:
            echo(f"==== DISCUSSION {index + 1} ====")
            echo("- NO ENTRIES")

        entries = [
            process_entry(entry, verbose, index, total, entry_index, len(entries))
            for entry_index, entry in enumerate(entries)
        ]

        columns = ["User", "Email", "Timestamp", "Post"]

        if not use_timestamp:
            columns.remove("Timestamp")

        entries = DataFrame(entries, columns=columns)
        entries.to_csv(discussion_path, index=False)

    def archive_quizzes(quiz, verbose=False, quiz_index=0):
        quiz_path = (
            QUIZ_DIRECTORY / f"{quiz.title.replace('- ', '').replace(' ', '_')}.csv"
        )
        users = [
            CANVAS.get_user(submission.user_id).name
            for submission in quiz.get_submissions()
        ]

        if verbose:
            echo(f"==== QUIZ {quiz_index + 1} ====")

            for index, user in enumerate(users):
                user_display = color(user, "cyan")
                echo(f"- ({index + 1}/{len(users)}) {user_display}")

        if verbose and not users:
            echo(f"==== QUIZ {quiz_index + 1} ====")
            echo("- NO SUBMISSIONS")

        users = DataFrame(users, columns=["User"])
        users.to_csv(quiz_path, index=False)

    CANVAS = get_canvas(instance)
    course = CANVAS.get_course(course_id)
    discussions, total = get_discussions(course)
    quizzes = []
    quiz_total = 0

    COURSE = RESULTS / f"{course.name}"
    DISCUSSION_DIRECTORY = COURSE / "Discussions"
    QUIZ_DIRECTORY = COURSE / "Quizzes"
    PATHS = [COURSE, DISCUSSION_DIRECTORY]

    if not exclude_quizzes:
        PATHS.append(QUIZ_DIRECTORY)

    for path in PATHS:
        if not path.exists():
            Path.mkdir(path)

    echo(") Processing discussions...")

    if verbose:
        for index, discussion in enumerate(discussions):
            archive_discussion(discussion, True, index, total)
    else:
        with progressbar(discussions, length=total) as progress:
            for discussion in progress:
                archive_discussion(discussion)

    if not exclude_quizzes:
        quizzes, quiz_total = get_quizzes(course)

        echo(") Processing quizzes...")

        if verbose:
            for index, quiz in enumerate(quizzes):
                archive_quizzes(quiz, True, index)
        else:
            with progressbar(quizzes, length=quiz_total) as progress:
                for quiz in progress:
                    archive_quizzes(quiz)

    color("SUMMARY", "yellow", True)
    echo(
        f"- Archived {color(total, 'magenta')} DISCUSSIONS for"
        f" {color(course.name, 'blue')}."
    )

    if not exclude_quizzes:
        echo(
            f"- Archived {color(quiz_total, 'magenta')} QUIZZES for"
            f" {color(course.name, 'blue')}."
        )
    color("FINISHED", "yellow", True)
