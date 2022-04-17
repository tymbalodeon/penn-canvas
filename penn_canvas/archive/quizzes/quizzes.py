from os import remove
from pathlib import Path
from shutil import make_archive, rmtree
from tarfile import open as open_tarfile
from typing import Optional

from canvasapi.course import Course
from pandas.io.parsers.readers import read_csv
from typer import echo

from penn_canvas.api import Instance
from penn_canvas.archive.assignments.assignment_descriptions import QUIZ_ID
from penn_canvas.archive.helpers import TAR_COMPRESSION_TYPE, TAR_EXTENSION, format_name
from penn_canvas.helpers import create_directory, write_file
from penn_canvas.style import color, print_item

from .questions import get_all_quiz_questions
from .quiz_descriptions import get_descriptions
from .responses import get_all_quiz_responses
from .scores import get_all_submission_scores

QUIZZES_TAR_STEM = "quizzes"
UNPACK_QUIZZES_DIRECTORY = QUIZZES_TAR_STEM.title()
QUIZZES_TAR_NAME = f"{QUIZZES_TAR_STEM}.{TAR_EXTENSION}"


def unpack_quizzes(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking quizzes...")
    archive_tar_path = compress_path / QUIZZES_TAR_NAME
    if not archive_tar_path.is_file():
        return None
    unpack_path = create_directory(unpack_path / UNPACK_QUIZZES_DIRECTORY)
    quizzes_tar_file = open_tarfile(archive_tar_path)
    quizzes_tar_file.extract("./descriptions.csv.gz", compress_path)
    descriptions = read_csv(compress_path / "descriptions.csv.gz")
    descriptions = descriptions.drop(QUIZ_ID, axis="columns")
    descriptions = descriptions.fillna("")
    description_path = create_directory(unpack_path / "Descriptions")
    total = len(descriptions.index)
    for index, quiz_title, description in descriptions.itertuples():
        description_file = description_path / f"{format_name(quiz_title)}.txt"
        write_file(description_file, f'"{quiz_title}"\n\n{description}')
        if verbose:
            print_item(index, total, color(quiz_title))
    remove(compress_path / "descriptions.csv.gz")
    return unpack_path


def fetch_quizzes(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Fetching quizzes...")
    quizzes_path = create_directory(compress_path / QUIZZES_TAR_STEM)
    unpack_path = create_directory(unpack_path / UNPACK_QUIZZES_DIRECTORY)
    quizzes = list(course.get_quizzes())
    quiz_path = create_directory(compress_path / "Quizzes")
    get_descriptions(quiz_path, quizzes, verbose)
    get_all_quiz_questions(quizzes, quiz_path)
    get_all_submission_scores(quizzes, quiz_path, instance)
    get_all_quiz_responses(course, quiz_path, instance, verbose)
    quizzes_directory = str(quizzes_path)
    make_archive(quizzes_directory, TAR_COMPRESSION_TYPE, root_dir=quizzes_directory)
    rmtree(quizzes_path)
