from os import remove
from pathlib import Path
from typing import Optional

from canvasapi.assignment import Assignment
from pandas import DataFrame, read_csv
from typer import echo

from penn_canvas.archive.helpers import (
    CSV_COMPRESSION_TYPE,
    format_name,
    format_text,
    print_description,
    print_unpacked_file,
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
UNPACK_DESCRIPTIONS_DIRECTORY = "Descriptions"


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


def unpack_descriptions(compress_path: Path, unpack_path: Path, verbose: bool):
    compressed_file = compress_path / DESCRIPTIONS_COMPRESSED_FILE
    if not compressed_file.is_file():
        return None
    descriptions_data = read_csv(compressed_file)
    descriptions_data.drop(ASSIGNMENT_ID, axis=1, inplace=True)
    descriptions_data.fillna("", inplace=True)
    descriptions_path = create_directory(unpack_path / UNPACK_DESCRIPTIONS_DIRECTORY)
    total = len(descriptions_data.index)
    for index, assignment_name, description in descriptions_data.itertuples():
        description_file = descriptions_path / f"{format_name(assignment_name)}.txt"
        text = f'"{assignment_name}"\n\n{description}'
        write_file(description_file, text)
        if verbose:
            print_description(index, total, assignment_name, description)
    if verbose:
        print_task_complete_message(descriptions_path)
    remove(compressed_file)
    return descriptions_path


def fetch_descriptions(
    assignments: list[Assignment],
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
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
    if unpack:
        unpacked_path = unpack_descriptions(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
