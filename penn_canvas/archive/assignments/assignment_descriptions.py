from os import remove
from pathlib import Path
from tarfile import open as open_tarfile
from typing import Optional

from canvasapi.assignment import Assignment
from pandas import DataFrame, read_csv
from typer import echo

from penn_canvas.archive.helpers import (
    CSV_COMPRESSION_TYPE,
    format_name,
    format_text,
    print_description,
)
from penn_canvas.helpers import (
    create_directory,
    print_task_complete_message,
    write_file,
)

DESCRIPTIONS_COMPRESSED_FILE = f"descriptions.{CSV_COMPRESSION_TYPE}"
ASSIGNMENT_ID = "Assignment ID"
QUIZ_ASSIGNMENT = "Quiz Assignment"
QUIZ_ID = "Quiz ID"
ASSIGNMENT_NAME = "Assignment Name"
DESCRIPTION = "Description"


def get_quiz_id(assignment: Assignment) -> Optional[str]:
    try:
        return str(assignment.quiz_id)
    except Exception:
        return None


def get_description(assignment: Assignment, verbose: bool, index: int, total: int):
    description = format_text(assignment.description)
    name = assignment.name
    is_quiz_assignment = assignment.is_quiz_assignment
    quiz_id = get_quiz_id(assignment)
    description = format_text(assignment.description)
    if verbose:
        print_description(index, total, assignment.name, description)
    return [assignment.id, is_quiz_assignment, quiz_id, name, description]


def unpack_descriptions(
    compress_path: Path, archive_tar_path: Path, unpack_path: Path, verbose: bool
):
    assignments_tar_file = open_tarfile(archive_tar_path)
    assignments_tar_file.extract(f"./{DESCRIPTIONS_COMPRESSED_FILE}", compress_path)
    unpacked_descriptions_path = compress_path / DESCRIPTIONS_COMPRESSED_FILE
    descriptions_data = read_csv(unpacked_descriptions_path)
    columns = [ASSIGNMENT_ID, QUIZ_ASSIGNMENT, QUIZ_ID]
    descriptions_data = descriptions_data.drop(columns, axis=1)
    descriptions_data.fillna("", inplace=True)
    total = len(descriptions_data.index)
    for index, assignment_name, description in descriptions_data.itertuples():
        assignment_name = format_name(assignment_name)
        descriptions_path = create_directory(unpack_path / assignment_name)
        description_file = descriptions_path / "Description.txt"
        text = f'"{assignment_name}"\n\n{description}'
        write_file(description_file, text)
        if verbose:
            print_description(index, total, assignment_name, description)
    if verbose:
        print_task_complete_message(unpack_path)
    remove(unpacked_descriptions_path)
    return unpack_path


def fetch_descriptions(
    assignments: list[Assignment],
    compress_path: Path,
    verbose: bool,
    total: int,
):
    echo(") Exporting assignment descriptions...")
    descriptions = [
        get_description(assignment, verbose, index, total)
        for index, assignment in enumerate(assignments)
    ]
    columns = [ASSIGNMENT_ID, QUIZ_ASSIGNMENT, QUIZ_ID, ASSIGNMENT_NAME, DESCRIPTION]
    description_data = DataFrame(descriptions, columns=columns)
    description_path = compress_path / DESCRIPTIONS_COMPRESSED_FILE
    description_data.to_csv(description_path, index=False)
