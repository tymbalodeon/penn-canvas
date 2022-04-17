from os import remove
from pathlib import Path
from tarfile import open as open_tarfile

from canvasapi.assignment import Assignment
from canvasapi.submission import Submission
from pandas import DataFrame, read_csv
from typer import echo

from penn_canvas.archive.assignments.assignment_descriptions import (
    ASSIGNMENT_ID,
    ASSIGNMENT_NAME,
)
from penn_canvas.archive.helpers import (
    CSV_COMPRESSION_TYPE,
    format_display_text,
    format_name,
    get_assignment_submissions,
    get_submission_display,
)
from penn_canvas.helpers import (
    create_directory,
    format_timestamp,
    print_task_complete_message,
    write_file,
)
from penn_canvas.report import flatten
from penn_canvas.style import color, print_item

SUBMISSION_COMMENTS_COMPRESSED_FILE = f"submission_comments.{CSV_COMPRESSION_TYPE}"
UNPACK_COMMENTS_DIRECTORY = "Comments"
USER_NAME = "User Name"


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
    return [submission.user["name"]] + comment_row


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


def unpack_submission_comments(
    compress_path: Path, archive_tar_path: Path, unpack_path: Path, verbose: bool
):
    assignments_tar_file = open_tarfile(archive_tar_path)
    assignments_tar_file.extract(
        f"./{SUBMISSION_COMMENTS_COMPRESSED_FILE}", compress_path
    )
    unpacked_comments_path = compress_path / SUBMISSION_COMMENTS_COMPRESSED_FILE
    comments_data = read_csv(unpacked_comments_path)
    comments_data.fillna("", inplace=True)
    assignment_ids = comments_data[ASSIGNMENT_ID].unique()
    assignments = [
        comments_data[comments_data[ASSIGNMENT_ID] == assignment_id]
        for assignment_id in assignment_ids
    ]
    total = len(assignments)
    for index, assignment in enumerate(assignments):
        assignment_name = next(iter(assignment[ASSIGNMENT_NAME].tolist()), "")
        assignment_name = format_name(assignment_name)
        assignment_path = create_directory(unpack_path / assignment_name)
        comments_path = create_directory(assignment_path / UNPACK_COMMENTS_DIRECTORY)
        assignment = assignment.drop(columns=ASSIGNMENT_ID)
        user_names = comments_data[USER_NAME].unique()
        user_comments = [
            assignment[assignment[USER_NAME] == user_name] for user_name in user_names
        ]
        for comments in user_comments:
            user_name = next(iter(comments[USER_NAME].tolist()), "")
            comments = comments.drop(columns=USER_NAME)
            header = f'"{assignment_name}"\n{user_name}\n'
            comments_text = [header]
            for (
                assignment_name,
                author,
                created_at,
                edited_at,
                comment,
                media_comment,
            ) in comments.itertuples(index=False):
                comment = (
                    f"{author}\nCreated at: {created_at}\nEdited at:"
                    f" {edited_at}\n\n{comment}\n\n{media_comment}"
                )
                comments_text.append(comment)
            comments_file = comments_path / f"{user_name}.txt"
            write_file(comments_file, "\n".join(comments_text))
        print_item(index, total, color(assignment_name))
    if verbose:
        print_task_complete_message(unpack_path)
    remove(unpacked_comments_path)
    return unpack_path


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
        ASSIGNMENT_ID,
        ASSIGNMENT_NAME,
        USER_NAME,
        "Author",
        "Created At",
        "Edited At",
        "Comment",
        "Media Comment",
    ]
    submission_comments_data = DataFrame(submission_comments, columns=columns)
    submission_comments_path = assignments_path / SUBMISSION_COMMENTS_COMPRESSED_FILE
    submission_comments_data.to_csv(submission_comments_path, index=False)
