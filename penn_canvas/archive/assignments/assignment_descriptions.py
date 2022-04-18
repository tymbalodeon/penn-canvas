from os import remove
from pathlib import Path
from typing import Optional

from canvasapi.assignment import Assignment
from pandas import DataFrame, read_csv
from typer import echo

from penn_canvas.archive.helpers import (
    CSV_COMPRESSION_TYPE,
    extract_file,
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


def get_quiz_id(assignment: Assignment) -> str:
    try:
        return str(assignment.quiz_id)
    except Exception:
        return ""


def get_description(
    assignment: Assignment, verbose: bool, index: int, total: int
) -> list[str]:
    assignment_id = str(assignment.id)
    is_quiz_assignment = str(assignment.is_quiz_assignment)
    quiz_id = get_quiz_id(assignment)
    name = assignment.name
    description = format_text(assignment.description)
    if verbose:
        print_description(index, total, assignment.name, description)
    return [assignment_id, is_quiz_assignment, quiz_id, name, description]


def unpack_descriptions(
    compress_path: Path, archive_tar_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    if verbose:
        echo(") Unpacking assignment descriptions...")
    if not archive_tar_path.is_file():
        return None
    extract_file(f"./{DESCRIPTIONS_COMPRESSED_FILE}", archive_tar_path, compress_path)
    extracted_path = compress_path / DESCRIPTIONS_COMPRESSED_FILE
    descriptions = read_csv(extracted_path)
    columns = [ASSIGNMENT_ID, QUIZ_ASSIGNMENT, QUIZ_ID]
    descriptions = descriptions.drop(columns, axis="columns")
    descriptions.fillna("", inplace=True)
    total = len(descriptions.index)
    for index, assignment_name, description in descriptions.itertuples():
        assignment_name = format_name(assignment_name)
        descriptions_path = create_directory(unpack_path / assignment_name)
        description_file = descriptions_path / "Description.txt"
        text = f'"{assignment_name}"\n\n{description}'
        write_file(description_file, text)
        if verbose:
            print_description(index, total, assignment_name, description)
    if verbose:
        print_task_complete_message(unpack_path)
    remove(extracted_path)
    return unpack_path


def fetch_descriptions(
    assignments: list[Assignment], compress_path: Path, verbose: bool, total: int
):
    echo(") Exporting assignment descriptions...")
    description_rows = [
        get_description(assignment, verbose, index, total)
        for index, assignment in enumerate(assignments)
    ]
    columns = [ASSIGNMENT_ID, QUIZ_ASSIGNMENT, QUIZ_ID, ASSIGNMENT_NAME, DESCRIPTION]
    descriptions = DataFrame(description_rows, columns=columns)
    descriptions_path = compress_path / DESCRIPTIONS_COMPRESSED_FILE
    descriptions.to_csv(descriptions_path, index=False)
