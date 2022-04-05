from os import remove
from pathlib import Path

from canvasapi.assignment import Assignment
from pandas import DataFrame, read_csv
from typer import echo

from penn_canvas.archive.helpers import (
    CSV_COMPRESSION_TYPE,
    format_display_text,
    format_name,
    print_unpacked_file,
    strip_tags,
)
from penn_canvas.helpers import create_directory, print_task_complete_message, write
from penn_canvas.style import color, print_item

DESCRIPTIONS_COMPRESSED_FILE = f"descriptions.{CSV_COMPRESSION_TYPE}"
ASSIGNMENT_ID = "Assignment ID"
UNPACK_DESCRIPTIONS_DIRECTORY = "Descriptions"


def display_description(index, total, assignment_name, description):
    assignment_display = color(format_display_text(assignment_name))
    description_display = color(format_display_text(description), "yellow")
    message = f"{assignment_display}: {description_display}"
    print_item(index, total, message)


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
        display_description(index, total, assignment.name, description)
    return [assignment.id, name, format_description(assignment)]


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
        write(description_file, text)
        if verbose:
            display_description(index, total, assignment_name, description)
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
    columns = [ASSIGNMENT_ID, "Assignment Name", "Descriptions"]
    description_data = DataFrame(descriptions, columns=columns)
    description_path = compress_path / DESCRIPTIONS_COMPRESSED_FILE
    description_data.to_csv(description_path, index=False)
    if unpack:
        unpacked_path = unpack_descriptions(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
