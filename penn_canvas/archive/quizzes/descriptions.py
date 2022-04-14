from pathlib import Path
from tarfile import open as open_tarfile

from canvasapi.quiz import Quiz
from pandas import DataFrame, read_csv
from pandas.core.reshape.concat import concat
from typer import echo

from penn_canvas.archive.assignments.assignments import ASSIGNMENTS_TAR_NAME
from penn_canvas.archive.assignments.descriptions import (
    ASSIGNMENT_ID,
    ASSIGNMENT_NAME,
    DESCRIPTIONS_COMPRESSED_FILE,
    QUIZ_ASSIGNMENT,
)
from penn_canvas.archive.helpers import format_text, print_description
from penn_canvas.style import color

QUIZ_ID = "Quiz ID"
QUIZ_TITLE = "Quiz Title"


def get_description(quiz: Quiz, verbose: bool, index: int, total: int):
    description = format_text(quiz.description)
    title = quiz.title
    if verbose:
        print_description(index, total, title, description)
    return [quiz.id, title, description]


def get_descriptions(compress_path: Path, quizzes: list[Quiz], verbose: bool):
    assignments_tar_path = compress_path / ASSIGNMENTS_TAR_NAME
    descriptions_path = compress_path / DESCRIPTIONS_COMPRESSED_FILE
    fetched_descriptions = list()
    descriptions = DataFrame()
    if assignments_tar_path.exists():
        assignments_tar_file = open_tarfile(assignments_tar_path)
        assignments_tar_file.extract(f"./{DESCRIPTIONS_COMPRESSED_FILE}", compress_path)
        descriptions = read_csv(descriptions_path, dtype={QUIZ_ID: str})
        descriptions = descriptions[descriptions[QUIZ_ASSIGNMENT] == True]  # noqa
        descriptions = descriptions.reset_index(drop=True)
        descriptions = descriptions.drop(
            [ASSIGNMENT_ID, QUIZ_ASSIGNMENT], axis="columns"
        )
        descriptions = descriptions.rename(columns={ASSIGNMENT_NAME: QUIZ_TITLE})
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
    columns = [QUIZ_ID, QUIZ_TITLE, "Description"]
    quiz_descriptions_data_frame = DataFrame(quiz_descriptions, columns=columns)
    descriptions = concat([descriptions, quiz_descriptions_data_frame])
    descriptions.to_csv(descriptions_path, index=False)
