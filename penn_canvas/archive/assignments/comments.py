from os import remove
from pathlib import Path
from typing import Optional

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
    extract_file,
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
        print_item(index, total, color(assignment))
    submissions = get_assignment_submissions(assignment)
    submission_total = len(submissions)
    submissions = [
        get_comments(submission, verbose, submission_index, submission_total)
        for submission_index, submission in enumerate(submissions)
    ]
    submissions = flatten(submissions)
    submission_rows = [submission for submission in submissions if submission]
    return [
        prepend_assignment_data(submission, assignment)
        for submission in submission_rows
    ]


def unpack_submission_comments(
    compress_path: Path, archive_tar_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    if verbose:
        echo(") Unpacking assignment submission comments...")
    if not archive_tar_path.is_file():
        return None
    extract_file(
        f"./{SUBMISSION_COMMENTS_COMPRESSED_FILE}", archive_tar_path, compress_path
    )
    extracted_path = compress_path / SUBMISSION_COMMENTS_COMPRESSED_FILE
    comments = read_csv(extracted_path)
    comments.fillna("", inplace=True)
    assignment_ids = comments[ASSIGNMENT_ID].unique()
    assignments = [
        comments[comments[ASSIGNMENT_ID] == assignment_id]
        for assignment_id in assignment_ids
    ]
    total = len(assignments)
    for index, assignment in enumerate(assignments):
        assignment_name = next(iter(assignment[ASSIGNMENT_NAME].tolist()), "")
        assignment_name = format_name(assignment_name)
        assignment_path = create_directory(unpack_path / assignment_name)
        comments_path = create_directory(assignment_path / UNPACK_COMMENTS_DIRECTORY)
        assignment = assignment.drop(columns=ASSIGNMENT_ID)
        user_names = assignment[USER_NAME].unique()
        user_comments = [
            assignment[assignment[USER_NAME] == user_name] for user_name in user_names
        ]
        for comments in user_comments:
            user_name = next(iter(comments[USER_NAME].tolist()), "")
            comments = comments.drop(columns=USER_NAME)
            comments_text = [f'"{assignment_name}"\n{user_name}\n']
            total_comments = len(comments.index)
            for (
                comments_index,
                assignment_name,
                author,
                created_at,
                edited_at,
                comment,
                media_comment,
            ) in comments.itertuples():
                comment = (
                    f"{author}\nCreated at: {created_at}\nEdited at:"
                    f" {edited_at}\n\n{comment}\n\n{media_comment}"
                )
                comments_text.append(comment)
                if verbose:
                    print_item(
                        comments_index, total_comments, format_display_text(comment)
                    )
            comments_file = comments_path / f"{user_name}.txt"
            write_file(comments_file, "\n".join(comments_text))
        if verbose:
            print_item(index, total, color(assignment_name))
    if verbose:
        print_task_complete_message(unpack_path)
    remove(extracted_path)
    return unpack_path


def fetch_submission_comments(
    assignments: list[Assignment], assignments_path: Path, verbose: bool, total: int
):
    echo(") Exporting assignment submission comments...")
    comments_rows = [
        get_submission_comments(assignment, verbose, index, total)
        for index, assignment in enumerate(assignments)
    ]
    comments_rows = flatten([submission for submission in comments_rows if submission])
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
    comments = DataFrame(comments_rows, columns=columns)
    comments_path = assignments_path / SUBMISSION_COMMENTS_COMPRESSED_FILE
    comments.to_csv(comments_path, index=False)
