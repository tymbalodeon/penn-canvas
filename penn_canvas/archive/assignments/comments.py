from pathlib import Path

from canvasapi.assignment import Assignment
from canvasapi.submission import Submission
from pandas import DataFrame
from typer import echo

from penn_canvas.archive.helpers import (
    CSV_COMPRESSION_TYPE,
    format_display_text,
    get_assignment_submissions,
    get_submission_display,
)
from penn_canvas.helpers import format_timestamp
from penn_canvas.report import flatten
from penn_canvas.style import color, print_item

SUBMISSION_COMMENTS_COMPRESSED_FILE = f"submission_comments.{CSV_COMPRESSION_TYPE}"


def format_comment(comment: dict, verbose: bool, index: int, total: int) -> list[str]:
    author = comment["author_name"]
    created_at = format_timestamp(comment["created_at"]) or ""
    edited_at = format_timestamp(comment["edited_at"]) or ""
    edited_at = edited_at if comment["edited_at"] else ""
    comment_text = comment["comment"]
    media_comment = (
        comment["media_comment"]["url"] if "media_comment" in comment else ""
    )
    if verbose:
        author_display = color(author)
        comment_display = comment_text if comment_text else media_comment
        comment_display = color(format_display_text(comment_display), "yellow")
        message = f"{author_display}: {comment_display}"
        print_item(index, total, message, prefix="\t\t-")
    return [author, created_at, edited_at, comment_text, media_comment]


def prepend_submission_data(
    comment_row: list[str], submission: Submission
) -> list[str]:
    return [submission.id] + comment_row


def get_comments(
    submission: Submission, verbose: bool, index: int, total: int
) -> list[list[str]]:
    if verbose:
        submission_display = get_submission_display(submission)
        print_item(index, total, submission_display, prefix="\t*")
    comments = submission.submission_comments
    comments_total = len(comments)
    comment_rows = [
        format_comment(comment, verbose, comment_index, comments_total)
        for comment_index, comment in enumerate(comments)
    ]
    return [prepend_submission_data(comment, submission) for comment in comment_rows]


def prepend_assignment_data(
    submission_row: list[str], assignment: Assignment
) -> list[str]:
    return [assignment.id, assignment.name] + submission_row


def get_submission_comments(
    assignment: Assignment, verbose: bool, index: int, total: int
) -> list[list[str]]:
    if verbose:
        message = color(assignment)
        print_item(index, total, message)
    submissions = get_assignment_submissions(assignment)
    submission_total = len(submissions)
    submissions = [
        get_comments(submission, verbose, submission_index, submission_total)
        for submission_index, submission in enumerate(submissions)
    ]
    submissions = list(flatten(submissions))
    submission_rows = [submission for submission in submissions if submission]
    return [
        prepend_assignment_data(submission, assignment)
        for submission in submission_rows
    ]


def fetch_submission_comments(
    assignments: list[Assignment], assignments_path: Path, verbose: bool, total: int
):
    echo(") Exporting assignment submission comments...")
    submission_comments = [
        get_submission_comments(assignment, verbose, index, total)
        for index, assignment in enumerate(assignments)
    ]
    submission_comments = [
        submission for submission in submission_comments if submission
    ]
    submission_comments = list(flatten(submission_comments))
    columns = [
        "Assignment ID",
        "Assignment Name",
        "Submission ID",
        "Author",
        "Created At",
        "Edited At",
        "Comment",
        "Media Comment",
    ]
    submission_comments_data = DataFrame(submission_comments, columns=columns)
    submission_comments_path = assignments_path / SUBMISSION_COMMENTS_COMPRESSED_FILE
    submission_comments_data.to_csv(submission_comments_path, index=False)
