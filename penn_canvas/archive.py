from datetime import datetime
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

from pandas import DataFrame
from typer import echo, progressbar

from .helpers import get_canvas, get_command_paths
from .style import color


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


def get_assignments(course):
    echo(") Finding assignments...")
    assignments = [assignment for assignment in course.get_assignments()]
    return assignments, len(assignments)


def get_quizzes(course):
    echo(") Finding quizzes...")
    quizzes = [quiz for quiz in course.get_quizzes()]
    return quizzes, len(quizzes)


def process_submission(
    submission,
    verbose,
    assignment_index,
    total_assignments,
    submission_index,
    total_submissions,
    assignment,
    canvas,
):
    canvas_user = canvas.get_user(submission.user_id)
    if verbose:
        user_display = color(canvas_user, "cyan")
        assignment_display = color(assignment, "magenta")
        if submission_index == 0:
            echo(f"==== ASSIGNMENT {assignment_index + 1} ====")
        echo(
            f"- [{assignment_index + 1}/{total_assignments}]"
            f" ({submission_index + 1}/{total_submissions}) {assignment_display}"
            f" {user_display}"
            f" {submission.grade}..."
            f" {submission.body}..."
        )

    return [canvas_user.name, assignment, submission.grade, submission.body]


def process_entry(
    entry,
    verbose,
    discussion_index,
    total_discussions,
    entry_index,
    total_entries,
    discussion,
    canvas,
    use_timestamp,
):
    user = " ".join(entry.user["display_name"].split())
    user_id = entry.user["id"]
    canvas_user = canvas.get_user(user_id)
    email = canvas_user.email
    message = " ".join(strip_tags(entry.message.replace("\n", " ")).strip().split())
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

    return (
        [user, email, timestamp, message] if use_timestamp else [user, email, message]
    )


def archive_main(course_id, instance, verbose, use_timestamp, exclude_quizzes):
    def archive_assignment(canvas, assignment, index, total):
        submissions_path = (
            ASSIGNMENT_DIRECTORY
            / f"{assignment.name.replace(' ', '_').replace('/', '-')}_SUBMISSIONS.csv"
        )
        assignment_path = (
            ASSIGNMENT_DIRECTORY
            / f"{assignment.name.replace(' ', '_').replace('/', '-')}.md"
        )
        submissions = [submission for submission in assignment.get_submissions()]
        submissions = [
            process_submission(
                submission,
                verbose,
                index,
                total,
                submission_index,
                len(submissions),
                assignment,
                canvas,
            )
            for submission_index, submission in enumerate(submissions)
        ]
        columns = ["User", "Assignment", "Grade", "Body"]
        submissions = DataFrame(submissions, columns=columns)
        submissions.to_csv(submissions_path, index=False)
        with open(assignment_path, "w") as assignment_file:
            assignment_file.write(
                assignment.description if assignment.description else ""
            )

    def archive_discussion(canvas, discussion, verbose=False, index=0, total=0):
        discussion_path = (
            DISCUSSION_DIRECTORY
            / f"{discussion.title.replace(' ', '_').replace('/', '-')}_POSTS.csv"
        )
        description_path = (
            DISCUSSION_DIRECTORY
            / f"{discussion.title.replace(' ', '_').replace('/', '-')}.md"
        )
        entries = [entry for entry in discussion.get_topic_entries()]
        if verbose and not entries:
            echo(f"==== DISCUSSION {index + 1} ====")
            echo("- NO ENTRIES")
        entries = [
            process_entry(
                entry,
                verbose,
                index,
                total,
                entry_index,
                len(entries),
                discussion,
                canvas,
                use_timestamp,
            )
            for entry_index, entry in enumerate(entries)
        ]
        columns = ["User", "Email", "Timestamp", "Post"]
        if not use_timestamp:
            columns.remove("Timestamp")
        entries = DataFrame(entries, columns=columns)
        entries.to_csv(discussion_path, index=False)
        with open(description_path, "w") as description_file:
            description_file.write(discussion.message if discussion.message else "")

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
    assignments, assignment_total = get_assignments(course)
    discussions, discussion_total = get_discussions(course)
    quizzes = []
    quiz_total = 0
    COURSE = RESULTS / f"{course.name}"
    DISCUSSION_DIRECTORY = COURSE / "Discussions"
    ASSIGNMENT_DIRECTORY = COURSE / "Assignments"
    QUIZ_DIRECTORY = COURSE / "Quizzes"
    PATHS = [COURSE, DISCUSSION_DIRECTORY, ASSIGNMENT_DIRECTORY]
    if not exclude_quizzes:
        PATHS.append(QUIZ_DIRECTORY)
    for path in PATHS:
        if not path.exists():
            Path.mkdir(path)
    echo(") Processing discussions...")
    if verbose:
        for index, discussion in enumerate(discussions):
            archive_discussion(CANVAS, discussion, True, index, discussion_total)
        for index, assignment in enumerate(assignments):
            archive_assignment(CANVAS, assignment, index, assignment_total)
    else:
        with progressbar(discussions, length=discussion_total) as progress:
            for discussion in progress:
                archive_discussion(CANVAS, discussion)
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
        f"- Archived {color(discussion_total, 'magenta')} DISCUSSIONS for"
        f" {color(course.name, 'blue')}."
    )
    if not exclude_quizzes:
        echo(
            f"- Archived {color(quiz_total, 'magenta')} QUIZZES for"
            f" {color(course.name, 'blue')}."
        )
    color("FINISHED", "yellow", True)
