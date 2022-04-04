from functools import lru_cache
from mimetypes import guess_extension
from pathlib import Path
from shutil import make_archive, rmtree
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.course import Course
from canvasapi.submission import Submission
from canvasapi.user import User
from magic.magic import from_file
from pandas import DataFrame
from requests import get
from typer import echo

from penn_canvas.api import Instance, get_user
from penn_canvas.helpers import create_directory, format_timestamp
from penn_canvas.report import flatten
from penn_canvas.style import color, print_item

from .helpers import (
    CSV_COMPRESSION_TYPE,
    TAR_COMPRESSION_TYPE,
    format_display_text,
    format_name,
    strip_tags,
)

DESCRIPTIONS_COMPRESSED_FILE = f"descriptions.{CSV_COMPRESSION_TYPE}"
SUBMISSION_COMMENTS_COMPRESSED_FILE = f"submission_comments.{CSV_COMPRESSION_TYPE}"
GRADES_COMPRESSED_FILE = f"grades.{CSV_COMPRESSION_TYPE}"
UNPACK_SUBMISSIONS_DIRECTORY = "Submission Files"


@lru_cache
def get_assignment_submissions(assignment: Assignment) -> list[Submission]:
    return list(assignment.get_submissions(include="submission_comments"))


def format_description(assignment: Assignment) -> str:
    try:
        description = assignment.description.replace("\n", " ")
        description = strip_tags(description).strip().split()
        return " ".join(description)
    except Exception:
        return ""


def get_description(assignment: Assignment, verbose: bool, index: int, total: int):
    description = format_description(assignment)
    name = assignment.name
    if verbose:
        assignment_display = color(format_display_text(assignment.name))
        description_display = color(format_display_text(description), "yellow")
        message = f"{assignment_display}: {description_display}"
        print_item(index, total, message)
    return [assignment.id, name, format_description(assignment)]


def archive_descriptions(
    assignments: list[Assignment], assignments_path: Path, verbose: bool, total: int
):
    echo(") Exporting assignment descriptions...")
    descriptions = [
        get_description(assignment, verbose, index, total)
        for index, assignment in enumerate(assignments)
    ]
    columns = ["Assignment ID", "Assignment Name", "Descriptions"]
    description_data = DataFrame(descriptions, columns=columns)
    description_path = assignments_path / DESCRIPTIONS_COMPRESSED_FILE
    description_data.to_csv(description_path, index=False)


def get_grader(submission: Submission, instance: Instance) -> Optional[User]:
    try:
        return get_user(submission.grader_id, instance=instance).name
    except Exception:
        return None


def get_grade(submission: Submission) -> str:
    try:
        return str(round(float(submission.grade), 2))
    except Exception:
        return submission.grade


def get_score(submission: Submission) -> str:
    try:
        return str(round(submission.score, 2))
    except Exception:
        return submission.score


def get_body(submission: Submission) -> str:
    try:
        return strip_tags(submission.body.replace("\n", " ")).strip()
    except Exception:
        return ""


def get_attachment_url_and_filename(attachment: dict):
    url = attachment["url"] if "url" in attachment else ""
    file_name = attachment["filename"] if "filename" in attachment else ""
    return url, file_name


def get_attachments(submission: Submission) -> Optional[list[tuple]]:
    try:
        return [
            get_attachment_url_and_filename(attachment)
            for attachment in submission.attachments
        ]
    except Exception:
        return None


def download_submission_files(
    submission: Submission, user_name: str, submissions_path: Path
):
    attachments = get_attachments(submission)
    if not attachments:
        return
    for url, filename in attachments:
        try:
            name, extension = filename.split(".")
        except Exception:
            name = filename
            extension = ""
        name = f"{format_name(name)} ({user_name})"
        file_name = f"{name} ({user_name}).{extension.lower()}" if extension else name
        submission_file_path = submissions_path / file_name
        with open(submission_file_path, "wb") as stream:
            response = get(url, stream=True)
            for chunk in response.iter_content(chunk_size=128):
                stream.write(chunk)
        if not extension:
            mime_type = from_file(str(submission_file_path), mime=True)
            submission_file_path.rename(
                f"{submission_file_path}{guess_extension(mime_type)}"
            )


def get_submission_grades(
    submission: Submission,
    instance: Instance,
    verbose: bool,
    index: int,
    total: int,
) -> list[User | str | int]:
    user = get_user(submission.user_id, instance=instance)
    grader = get_grader(submission, instance)
    grade = get_grade(submission)
    score = get_score(submission)
    body = get_body(submission)
    user_id = user.id
    user_name = user.name
    submission_type = (
        submission.submission_type.replace("_", " ")
        if submission.submission_type
        else submission.submission_type
    )
    grader_id = grader.id if grader else ""
    grader_name = grader.name if grader else ""
    if verbose:
        user_display = color(user_name, "cyan")
        grade_display = color(grade, "yellow")
        message = f"{user_display}: {grade_display}"
        print_item(index, total, message, prefix="\t*")
    return [
        user_id,
        user_name,
        submission_type,
        grade,
        score,
        grader_id,
        grader_name,
        body,
    ]


def get_assignment_grades(
    assignment: Assignment,
    instance: Instance,
    verbose: bool,
    index: int,
    total: int,
):
    if verbose:
        assignment_display = color(format_display_text(assignment.name))
        print_item(index, total, assignment_display)
    submissions = get_assignment_submissions(assignment)
    submissions_total = len(submissions)
    return [
        get_submission_grades(
            submission,
            instance,
            verbose,
            submission_index,
            submissions_total,
        )
        for submission_index, submission in enumerate(submissions)
    ]


def archive_submissions(
    assignments: list[Assignment],
    instance: Instance,
    assignments_path: Path,
    unpack_path: Path,
    unpack: bool,
    verbose: bool,
    total: int,
):
    echo(") Exporting assignment grades...")
    grades = [
        get_assignment_grades(assignment, instance, verbose, index, total)
        for index, assignment in enumerate(assignments)
    ]
    grades = list(flatten(grades))
    columns = [
        "User ID",
        "User Name",
        "Submission type",
        "Grade",
        "Score",
        "Grader ID",
        "Grader Name",
        "Body",
    ]
    grades_data = DataFrame(grades, columns=columns)
    grades_path = assignments_path / GRADES_COMPRESSED_FILE
    grades_data.to_csv(grades_path, index=False)
    echo(") Exporting submission files...")
    submissions_path = create_directory(assignments_path / "submission_files")
    for index, assignment in enumerate(assignments):
        if verbose:
            assignment_display = color(format_display_text(assignment.name))
            print_item(index, total, color(assignment_display))
        submissions = get_assignment_submissions(assignment)
        submissions_total = len(submissions)
        for submission_index, submission in enumerate(submissions):
            if verbose:
                submission_display = get_submission_display(submission)
                print_item(
                    submission_index,
                    submissions_total,
                    submission_display,
                    prefix="\t*",
                )
            user_name = get_user(submission.user_id, instance=instance).name
            download_submission_files(submission, user_name, submissions_path)
    submission_files = str(submissions_path)
    make_archive(submission_files, TAR_COMPRESSION_TYPE, root_dir=submission_files)
    if unpack:
        unpack_submissions_path = create_directory(
            unpack_path / UNPACK_SUBMISSIONS_DIRECTORY, clear=True
        )
        submissions_path.replace(unpack_submissions_path)
    else:
        rmtree(submissions_path)


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
        comment_display = format_display_text(color(comment_display, "yellow"))
        message = f"{author_display}: {comment_display}"
        print_item(index, total, message, prefix="\t\t-")
    return [author, created_at, edited_at, comment_text, media_comment]


def prepend_submission_data(
    comment_row: list[str], submission: Submission
) -> list[str]:
    return [submission.id] + comment_row


@lru_cache
def get_submission_display(submission):
    try:
        submission_display = next(iter(submission.attachments))["display_name"]
    except Exception:
        submission_display = submission
    return color(submission_display, "cyan")


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


def archive_submission_comments(
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


def archive_assignments(
    course: Course,
    course_path: Path,
    unpack_path: Path,
    unpack: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Exporting assignments...")
    assignments_path = create_directory(course_path / "assignments")
    assignments = list(course.get_assignments())
    total = len(assignments)
    archive_descriptions(assignments, assignments_path, verbose, total)
    archive_submissions(
        assignments, instance, assignments_path, unpack_path, unpack, verbose, total
    )
    archive_submission_comments(assignments, assignments_path, verbose, total)
    assignments_files = str(assignments_path)
    make_archive(assignments_files, TAR_COMPRESSION_TYPE, root_dir=assignments_files)
    rmtree(assignments_path)
    return assignments
