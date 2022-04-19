from os import remove
from pathlib import Path
from tarfile import open as open_tarfile

from canvasapi.quiz import Quiz
from pandas import DataFrame, read_csv
from pandas.core.reshape.concat import concat
from typer import echo

from penn_canvas.archive.assignments.assignment_descriptions import (
    ASSIGNMENT_ID,
    ASSIGNMENT_NAME,
    DESCRIPTION,
    DESCRIPTIONS_COMPRESSED_FILE,
    QUIZ_ASSIGNMENT,
)
from penn_canvas.archive.assignments.assignments import ASSIGNMENTS_TAR_NAME
from penn_canvas.archive.helpers import (
    COMPRESSION_TYPE,
    format_name,
    format_text,
    print_description,
)
from penn_canvas.helpers import create_directory, write_file
from penn_canvas.style import color, print_item

QUIZ_ID = "Quiz ID"
QUIZ_TITLE = "Quiz Title"


def get_assignment_descriptions(
    assignments_tar_path: Path, compress_path: Path, descriptions_path: Path
) -> DataFrame:
    assignments_tar_file = open_tarfile(assignments_tar_path)
    assignments_tar_file.extract(f"./{DESCRIPTIONS_COMPRESSED_FILE}", compress_path)
    descriptions = read_csv(descriptions_path, dtype={QUIZ_ID: str})
    descriptions = descriptions[descriptions[QUIZ_ASSIGNMENT] == True]  # noqa
    descriptions = descriptions.reset_index(drop=True)
    descriptions = descriptions.drop([ASSIGNMENT_ID, QUIZ_ASSIGNMENT], axis="columns")
    return descriptions.rename(columns={ASSIGNMENT_NAME: QUIZ_TITLE})


def get_description(quiz: Quiz, verbose: bool, index: int, total: int):
    description = format_text(quiz.description)
    title = quiz.title
    if verbose:
        print_description(index, total, title, description)
    return [quiz.id, title, description]


def unpack_descriptions(
    compress_path: Path, quizzes_tar_name: str, unpack_path: Path, verbose: bool
):
    if verbose:
        echo(") Unpacking quiz descriptions...")
    archive_tar_path = compress_path / quizzes_tar_name
    if not archive_tar_path.is_file():
        return None
    quizzes_tar_file = open_tarfile(archive_tar_path)
    quizzes_tar_file.extract(f"./descriptions.csv.{COMPRESSION_TYPE}", compress_path)
    descriptions = read_csv(compress_path / f"descriptions.csv.{COMPRESSION_TYPE}")
    descriptions = descriptions.drop(QUIZ_ID, axis="columns")
    descriptions = descriptions.fillna("")
    total = len(descriptions.index)
    for index, quiz_title, description in descriptions.itertuples():
        quiz_path = create_directory(unpack_path / format_name(quiz_title))
        description_file = quiz_path / "Description.txt"
        write_file(description_file, f'"{quiz_title}"\n\n{description}')
        if verbose:
            print_item(index, total, color(quiz_title))
    remove(compress_path / f"descriptions.csv.{COMPRESSION_TYPE}")
    return unpack_path


def fetch_descriptions(
    quiz_path: Path,
    quizzes: list[Quiz],
    verbose: bool,
):
    assignments_tar_path = quiz_path / ASSIGNMENTS_TAR_NAME
    descriptions_path = quiz_path / DESCRIPTIONS_COMPRESSED_FILE
    fetched_descriptions = list()
    descriptions = DataFrame()
    if assignments_tar_path.exists():
        descriptions = get_assignment_descriptions(
            assignments_tar_path, quiz_path, descriptions_path
        )
        fetched_descriptions = descriptions[QUIZ_ID].tolist()
    fetched_descriptions_count = len(fetched_descriptions)
    if verbose and fetched_descriptions_count:
        count = color(fetched_descriptions_count, "cyan")
        echo(f"Skipping {count} descriptions previously fetched from assignments...")
    quizzes = [quiz for quiz in quizzes if str(quiz.id) not in fetched_descriptions]
    total = len(quizzes)
    quiz_descriptions = [
        get_description(quiz, verbose, index, total)
        for index, quiz in enumerate(quizzes)
    ]
    columns = [QUIZ_ID, QUIZ_TITLE, DESCRIPTION]
    quiz_descriptions_data_frame = DataFrame(quiz_descriptions, columns=columns)
    descriptions = concat([descriptions, quiz_descriptions_data_frame])
    descriptions.to_csv(descriptions_path, index=False)
