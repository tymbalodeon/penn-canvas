from mimetypes import guess_extension
from os import remove
from pathlib import Path
from shutil import make_archive, rmtree, unpack_archive
from tarfile import open as open_tarfile
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.submission import Submission
from canvasapi.user import User
from click.utils import echo
from magic.magic import from_file
from pandas import DataFrame
from pandas.io.parsers.readers import read_csv

from penn_canvas.api import Instance, get_user
from penn_canvas.archive.assignments.assignment_descriptions import (
    ASSIGNMENT_ID,
    ASSIGNMENT_NAME,
)
from penn_canvas.archive.helpers import (
    CSV_COMPRESSION_TYPE,
    TAR_COMPRESSION_TYPE,
    format_display_text,
    format_name,
    get_assignment_submissions,
    get_submission_display,
    strip_tags,
)
from penn_canvas.helpers import (
    create_directory,
    download_file,
    print_task_complete_message,
    write_file,
)
from penn_canvas.report import flatten
from penn_canvas.style import color, print_item

GRADES_COMPRESSED_FILE = f"grades.{CSV_COMPRESSION_TYPE}"
USER_ID = "User ID"
GRADER_ID = "Grader ID"
BODY = "Body"
SUBMISSION_TYPE = "Submission type"
GRADE = "Grade"
SCORE = "Score"
GRADER_NAME = "Grader Name"
UNPACK_SUBMISSIONS_DIRECTORY = "Submissions"


def get_grader(submission: Submission, instance: Instance) -> Optional[User]:
    try:
        return get_user(submission.grader_id, instance=instance)
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
    submission: Submission, user_name: str, assignment_path: Path
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
        submission_file_path = create_directory(assignment_path) / file_name
        download_file(submission_file_path, url)
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
        [assignment.id, assignment.name]
        + get_submission_grades(
            submission,
            instance,
            verbose,
            submission_index,
            submissions_total,
        )
        for submission_index, submission in enumerate(submissions)
    ]


def unpack_submissions(
    compress_path: Path, archive_tar_path: Path, unpack_path: Path, verbose: bool
):
    assignments_tar_file = open_tarfile(archive_tar_path)
    assignments_tar_file.extract(f"./{GRADES_COMPRESSED_FILE}", compress_path)
    assignments_tar_file.extract("./submission_files.tar.gz", compress_path)
    unpacked_submissions_path = compress_path / GRADES_COMPRESSED_FILE
    unpacked_files_path = compress_path / "submission_files.tar.gz"
    unpack_archive(unpacked_files_path, unpack_path)
    submissions_data = read_csv(unpacked_submissions_path)
    columns = [USER_ID, GRADER_ID]
    submissions_data = submissions_data.drop(columns, axis=1)
    submissions_data.fillna("", inplace=True)
    assignment_ids = submissions_data[ASSIGNMENT_ID].unique()
    assignments = [
        submissions_data[submissions_data[ASSIGNMENT_ID] == assignment_id]
        for assignment_id in assignment_ids
    ]
    total = len(assignments)
    for index, assignment in enumerate(assignments):
        assignment_name = next(iter(assignment[ASSIGNMENT_NAME].tolist()), "")
        assignment_name = format_name(assignment_name)
        assignment_path = create_directory(unpack_path / assignment_name)
        submission_file = assignment_path / "Grades.csv"
        online_text_entries = assignment[
            assignment[SUBMISSION_TYPE] == "online text entry"
        ]
        online_text_entries = online_text_entries.drop(
            columns=[
                ASSIGNMENT_ID,
                ASSIGNMENT_NAME,
                SUBMISSION_TYPE,
                GRADE,
                SCORE,
                GRADER_NAME,
            ]
        )
        if not online_text_entries.empty:
            submission_files_path = create_directory(
                assignment_path / UNPACK_SUBMISSIONS_DIRECTORY
            )
            for user_name, body in online_text_entries.itertuples(index=False):
                entry_file = submission_files_path / f"{user_name}.txt"
                write_file(entry_file, f'"{assignment_name}"\n{user_name}\n\n{body}')
        assignment = assignment.drop(columns=[ASSIGNMENT_ID, SUBMISSION_TYPE, BODY])
        assignment.to_csv(submission_file, index=False)
        print_item(index, total, color(assignment_name))
    if verbose:
        print_task_complete_message(unpack_path)
    remove(unpacked_submissions_path)
    remove(compress_path / "submission_files.tar.gz")
    return unpack_path


def fetch_submissions(
    assignments: list[Assignment],
    assignments_path: Path,
    instance: Instance,
    verbose: bool,
    total: int,
):
    echo(") Exporting assignment grades...")
    grades = [
        get_assignment_grades(assignment, instance, verbose, index, total)
        for index, assignment in enumerate(assignments)
    ]
    grades = flatten(grades)
    columns = [
        ASSIGNMENT_ID,
        ASSIGNMENT_NAME,
        USER_ID,
        "User Name",
        SUBMISSION_TYPE,
        GRADE,
        SCORE,
        GRADER_ID,
        GRADER_NAME,
        BODY,
    ]
    grades_data = DataFrame(grades, columns=columns)
    grades_path = assignments_path / GRADES_COMPRESSED_FILE
    grades_data.to_csv(grades_path, index=False)
    echo(") Exporting submission files...")
    submissions_path = create_directory(assignments_path / "submission_files")
    for index, assignment in enumerate(assignments):
        assignment_name = format_name(assignment.name)
        if verbose:
            assignment_display = color(format_display_text(assignment_name))
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
            assignment_path = submissions_path / assignment_name / "Submissions"
            download_submission_files(submission, user_name, assignment_path)
    submission_files = str(submissions_path)
    make_archive(submission_files, TAR_COMPRESSION_TYPE, root_dir=submission_files)
    rmtree(submissions_path)
